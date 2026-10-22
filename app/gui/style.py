"""Look-and-feel pieces for the dark theme. Drop-in replacements for the plain Tk widgets:

  FlatButton  tk.Button with a hover glow (and an optional red 'danger' look)
  Toggle      tk.Checkbutton as a small on/off switch (same variable / command use)
  FlatEntry   tk.Entry with a thin outline that lights up while you type
  TabBar      the page switcher (replaces ttk.Notebook): add(frame, text) / select(frame)
  style_scrollbar(root)  a slim dark scrollbar for ttk.Scrollbar

Nothing here holds program logic."""
import tkinter as tk
from tkinter import ttk

from gui import theme

PAL = theme.PALETTE
FONT = "Segoe UI"


def _rgb(color):
    color = str(color).lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def mix(color, other, amount):
    """`color` moved `amount` (0..1) of the way toward `other`. Both are #rrggbb."""
    try:
        a, b = _rgb(color), _rgb(other)
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * amount) for x, y in zip(a, b))
    except (ValueError, IndexError):
        return color


class FlatButton(tk.Button):
    """Flat button that brightens under the pointer. `configure(bg=...)` still works (the intensity
    buttons use it to show which one is picked)."""

    def __init__(self, parent, hover=None, **kw):
        kw.setdefault("relief", "flat")
        kw.setdefault("bd", 0)
        kw.setdefault("cursor", "hand2")
        kw.setdefault("highlightthickness", 0)
        kw["padx"] = max(int(kw.get("padx", 0) or 0), 14)
        kw["pady"] = max(int(kw.get("pady", 0) or 0), 7)
        kw.setdefault("bg", PAL["panel3"])
        kw.setdefault("fg", PAL["white"])
        kw.setdefault("font", (FONT, 10, "bold"))
        kw.setdefault("disabledforeground", PAL["dim"])
        super().__init__(parent, **kw)
        self._base = str(kw["bg"])
        self._hover_fixed = hover
        self._over = False
        self._paint()
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _hover_color(self):
        return self._hover_fixed or mix(self._base, "#ffffff", 0.14)

    def _disabled(self):
        return str(tk.Button.cget(self, "state")) == "disabled"

    def _paint(self):
        shown = self._hover_color() if (self._over and not self._disabled()) else self._base
        tk.Button.configure(self, bg=shown, activebackground=mix(self._base, "#ffffff", 0.24))

    def _enter(self, _event=None):
        self._over = True
        self._paint()

    def _leave(self, _event=None):
        self._over = False
        self._paint()

    def configure(self, cnf=None, **kw):
        kw = {**(cnf or {}), **kw}
        for key in ("bg", "background"):
            if key in kw:
                self._base = str(kw.pop(key))
        tk.Button.configure(self, **kw)
        self._paint()

    config = configure


class DropMenu(FlatButton):
    """A drop-down: shows the picked value with a small arrow; click to choose. `["menu"]` is the pop-up menu."""

    def __init__(self, parent, variable, choices, command=None, **kw):
        kw.setdefault("anchor", "w")
        super().__init__(parent, text="", **kw)
        self._var, self._pick_cmd = variable, command
        self.menu = tk.Menu(self, tearoff=0, bg=PAL["panel3"], fg=PAL["white"], bd=0, relief="flat",
                            activebackground=PAL["accent2"], activeforeground=PAL["white"], font=(FONT, 10))
        self.set_choices(choices)
        self._trace = variable.trace_add("write", lambda *_a: self._show())
        tk.Button.configure(self, command=self._open)
        self._show()

    def __getitem__(self, key):
        return self.menu if key == "menu" else super().__getitem__(key)

    def set_choices(self, choices):
        self.menu.delete(0, "end")
        for choice in choices:
            self.menu.add_command(label=choice, command=lambda c=choice: self._pick(c))

    def _pick(self, choice):
        self._var.set(choice)
        if self._pick_cmd:
            self._pick_cmd(choice)

    def _show(self):
        try:
            tk.Button.configure(self, text=f"{self._var.get() or '(none)'}    \u25be")
        except tk.TclError:
            pass

    def _open(self):
        try:
            self.menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        finally:
            self.menu.grab_release()


class ColumnList(tk.Frame):
    """A fixed-size box that lists lines top to bottom, then continues in a new column to the right.
    Only the columns that fit inside the box are shown. `configure(text=...)` takes lines split by newlines."""

    ROW_H = 20
    COL_W = 290

    def __init__(self, parent, rows=5, bg=None, fg=None, font=None, text="", pad=10, **_ignored):
        bg = bg or PAL["panel2"]
        super().__init__(parent, bg=bg, height=rows * self.ROW_H + 2 * pad)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._rows, self._pad = rows, pad
        self._fg, self._font = fg or PAL["muted"], font or (FONT, 9)
        self._bg = bg
        self._lines = []
        self._labels = []
        self.bind("<Configure>", lambda _e: self._layout())
        self.configure(text=text)

    def configure(self, cnf=None, **kw):
        kw = {**(cnf or {}), **kw}
        if "text" in kw:
            text = kw.pop("text") or ""
            self._lines = [ln for ln in str(text).split("\n") if ln.strip()]
            self._layout()
        if kw:
            tk.Frame.configure(self, **kw)

    config = configure

    @staticmethod
    def fit(line, width_px):
        """Shorten a line with an ellipsis so it stays inside its column."""
        room = max(8, (width_px - 12) // 6)
        return line if len(line) <= room else line[:room - 1].rstrip() + "\u2026"

    def columns_that_fit(self, width_px):
        return max(1, int(width_px) // self.COL_W)

    def _layout(self):
        for lab in self._labels:
            lab.destroy()
        self._labels = []
        width = self.winfo_width()
        if width <= 1:
            width = self.COL_W * 2          # not on screen yet: the real width arrives with <Configure>
        cols = self.columns_that_fit(width - 2 * self._pad)
        col_w = (width - 2 * self._pad) // cols
        for i, line in enumerate(self._lines[: self._rows * cols]):
            lab = tk.Label(self, text=self.fit(line, col_w), bg=self._bg, fg=self._fg, font=self._font,
                           anchor="w", justify="left")
            lab.place(x=self._pad + (i // self._rows) * col_w, y=self._pad + (i % self._rows) * self.ROW_H,
                      width=col_w - 6, height=self.ROW_H)
            self._labels.append(lab)


class FlatEntry(tk.Entry):
    """Entry with a quiet outline that turns violet while it has the cursor."""

    def __init__(self, parent, **kw):
        kw.setdefault("relief", "flat")
        kw.setdefault("bd", 4)
        kw.setdefault("bg", PAL["field"])
        kw.setdefault("fg", PAL["white"])
        kw.setdefault("insertbackground", PAL["white"])
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightbackground", PAL["border"])
        kw.setdefault("highlightcolor", PAL["accent2"])
        kw.setdefault("font", (FONT, 10))
        kw.setdefault("disabledforeground", PAL["dim"])
        super().__init__(parent, **kw)


class Toggle(tk.Frame):
    """A check box drawn as an on/off switch. Works like tk.Checkbutton: text=, variable=, command=."""

    W, H = 34, 18

    def __init__(self, parent, text="", variable=None, command=None, bg=None, fg=None, font=None,
                 anchor="w", justify="left", wraplength=0, **_ignored):
        if bg is None:
            try:
                bg = parent.cget("bg")
            except tk.TclError:
                bg = PAL["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._var = variable if variable is not None else tk.BooleanVar(value=False)
        self._cmd = command
        self._bg = bg
        self._disabled = False
        self._over = False
        self._fg = fg or PAL["white"]
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg=bg, highlightthickness=0, bd=0,
                                cursor="hand2")
        self.canvas.pack(side="left", pady=4)
        self.label = tk.Label(self, text=text, bg=bg, fg=self._fg, font=font or (FONT, 9),
                              anchor=anchor, justify=justify, wraplength=wraplength, cursor="hand2")
        self.label.pack(side="left", padx=(9, 0), fill="x", expand=True)
        for widget in (self, self.canvas, self.label):
            widget.bind("<Button-1>", self._click, add="+")
            widget.bind("<Enter>", self._enter, add="+")
            widget.bind("<Leave>", self._leave, add="+")
        self._trace = self._var.trace_add("write", lambda *_a: self._draw())
        self._draw()

    # ---- drawing ----
    def _is_on(self):
        try:
            return bool(self._var.get())
        except (tk.TclError, ValueError):
            return False

    def _draw(self):
        try:
            c = self.canvas
            c.delete("all")
            on = self._is_on()
            if self._disabled:
                track, knob = PAL["trough"], PAL["dim"]
            elif on:
                track = mix(PAL["accent2"], "#ffffff", 0.12) if self._over else PAL["accent2"]
                knob = "#ffffff"
            else:
                track = mix(PAL["field"], "#ffffff", 0.10) if self._over else PAL["field"]
                knob = PAL["muted"]
            w, h = self.W, self.H
            c.create_oval(0, 0, h, h, fill=track, outline=track)
            c.create_oval(w - h, 0, w, h, fill=track, outline=track)
            c.create_rectangle(h / 2, 0, w - h / 2, h, fill=track, outline=track)
            pad = 3
            x0 = w - h + pad if on else pad
            c.create_oval(x0, pad, x0 + h - 2 * pad, h - pad, fill=knob, outline=knob)
        except tk.TclError:
            pass   # the window is closing

    # ---- behaviour ----
    def _enter(self, _event=None):
        self._over = True
        self._draw()

    def _leave(self, _event=None):
        self._over = False
        self._draw()

    def _click(self, _event=None):
        if self._disabled:
            return
        self.toggle()
        if self._cmd:
            self._cmd()

    def toggle(self):
        new = not self._is_on()
        self._var.set(new if isinstance(self._var, tk.BooleanVar) else int(new))

    def select(self):
        self._var.set(True if isinstance(self._var, tk.BooleanVar) else 1)

    def deselect(self):
        self._var.set(False if isinstance(self._var, tk.BooleanVar) else 0)

    def invoke(self):
        self._click()

    def configure(self, cnf=None, **kw):
        kw = {**(cnf or {}), **kw}
        if "text" in kw:
            self.label.configure(text=kw.pop("text"))
        if "command" in kw:
            self._cmd = kw.pop("command")
        if "state" in kw:
            self._disabled = str(kw.pop("state")) == "disabled"
            self.label.configure(fg=PAL["dim"] if self._disabled else self._fg)
            self._draw()
        for key in ("fg", "foreground"):
            if key in kw:
                self._fg = kw.pop(key)
                self.label.configure(fg=self._fg)
        for key in ("font", "anchor", "justify", "wraplength"):
            if key in kw:
                self.label.configure(**{key: kw.pop(key)})
        for key in ("bg", "background"):
            if key in kw:
                self._bg = kw.pop(key)
                tk.Frame.configure(self, bg=self._bg)
                self.canvas.configure(bg=self._bg)
                self.label.configure(bg=self._bg)
        for key in ("variable", "selectcolor", "activebackground", "activeforeground", "highlightthickness",
                    "padx", "pady", "disabledforeground", "indicatoron", "relief", "bd", "cursor"):
            kw.pop(key, None)
        if kw:
            tk.Frame.configure(self, **kw)

    config = configure

    def destroy(self):
        try:
            self._var.trace_remove("write", self._trace)
        except (tk.TclError, ValueError, AttributeError):
            pass
        super().destroy()


class TabBar(tk.Frame):
    """Page switcher: a row of text tabs with an accent underline, and a stage that shows one page."""

    def __init__(self, parent, bg=None, accent=None):
        bg = bg or PAL["bg"]
        super().__init__(parent, bg=bg)
        self._bg = bg
        self._accent = accent or PAL["accent"]
        self.bar = tk.Frame(self, bg=bg)
        self.bar.pack(fill="x")
        tk.Frame(self, bg=PAL["border"], height=1).pack(fill="x")
        self.stage = tk.Frame(self, bg=bg)
        self.stage.pack(fill="both", expand=True, pady=(8, 0))
        self._tabs = []        # (page, label, underline)
        self._current = None

    def add(self, page, text):
        cell = tk.Frame(self.bar, bg=self._bg, cursor="hand2")
        cell.pack(side="left", padx=(0, 4))
        label = tk.Label(cell, text=text, bg=self._bg, fg=PAL["muted"], font=(FONT, 10, "bold"),
                         padx=14, pady=8, cursor="hand2")
        label.pack()
        underline = tk.Frame(cell, bg=self._bg, height=2)
        underline.pack(fill="x")
        for widget in (cell, label):
            widget.bind("<Button-1>", lambda _e, p=page: self.select(p), add="+")
            widget.bind("<Enter>", lambda _e, p=page: self._hover(p, True), add="+")
            widget.bind("<Leave>", lambda _e, p=page: self._hover(p, False), add="+")
        self._tabs.append((page, label, underline))
        if self._current is None:
            self.select(page)

    def _hover(self, page, over):
        for p, label, _u in self._tabs:
            if p is page and p is not self._current:
                label.configure(fg=PAL["white"] if over else PAL["muted"])

    def select(self, page):
        if isinstance(page, int):
            page = self._tabs[page][0]
        for p, label, underline in self._tabs:
            if p is page:
                label.configure(fg=PAL["white"])
                underline.configure(bg=self._accent)
                p.pack(in_=self.stage, fill="both", expand=True)
            else:
                label.configure(fg=PAL["muted"])
                underline.configure(bg=self._bg)
                p.pack_forget()
        self._current = page


def style_scrollbar(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("AE.Vertical.TScrollbar", background=PAL["panel3"], troughcolor=PAL["bg"],
                    bordercolor=PAL["bg"], lightcolor=PAL["panel3"], darkcolor=PAL["panel3"],
                    arrowcolor=PAL["panel3"], gripcount=0, relief="flat", arrowsize=8, borderwidth=0)
    style.map("AE.Vertical.TScrollbar",
              background=[("active", PAL["accent2"]), ("pressed", PAL["accent2"])],
              lightcolor=[("active", PAL["accent2"])], darkcolor=[("active", PAL["accent2"])])
    style.layout("AE.Vertical.TScrollbar",
                 [("Vertical.Scrollbar.trough",
                   {"sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])


def center_on_screen(win, width, height):
    """Open `win` at width x height in the middle of the screen (not the top-left corner)."""
    win.update_idletasks()
    x = max(0, (win.winfo_screenwidth() - width) // 2)
    y = max(0, (win.winfo_screenheight() - height) // 2 - 20)
    win.geometry(f"{width}x{height}+{x}+{y}")
