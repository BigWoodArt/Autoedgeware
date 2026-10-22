"""Small shared Tk pieces: a scrolling frame, a collapsible section, and the dark tab style."""
import tkinter as tk
from tkinter import ttk


from gui.style import style_scrollbar   # re-exported: the app sets the scrollbar look once at start


class ScrollFrame(tk.Frame):
    """Put widgets in `.body`. The mouse wheel scrolls it while the pointer is over it."""

    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", style="AE.Vertical.TScrollbar", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self._bar, self._bar_shown = bar, True
        self.body.bind("<Configure>", lambda e: self._resized())
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(self._window, width=e.width),
                                                   self._resized()))
        self.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _resized(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # no scroll bar while everything fits
        needs = self.body.winfo_reqheight() > self.canvas.winfo_height() + 1 and self.canvas.winfo_height() > 1
        if needs and not self._bar_shown:
            self._bar.pack(side="right", fill="y", before=self.canvas)
            self._bar_shown = True
        elif not needs and self._bar_shown and self.canvas.winfo_height() > 1:
            self._bar.pack_forget()
            self._bar_shown = False

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")

    def to_top(self):
        self.canvas.yview_moveto(0)


class Collapsible(tk.Frame):
    """A header button that shows/hides `.body`."""

    def __init__(self, parent, title, pal, open_=False):
        super().__init__(parent, bg=pal["panel"])
        self.title, self._open = title, open_
        self.button = tk.Button(self, command=self.toggle, relief="flat", bd=0, anchor="w",
                                font=("Segoe UI", 9, "bold"), bg=pal["panel"], fg=pal["white"],
                                activebackground=pal["panel"], activeforeground=pal["accent2"],
                                cursor="hand2")
        self.button.pack(fill="x")
        self.body = tk.Frame(self, bg=pal["panel"])
        self._render()

    def _render(self):
        self.button.configure(text=("▾ " if self._open else "▸ ") + self.title)
        if self._open:
            self.body.pack(fill="x", pady=(4, 0))
        else:
            self.body.pack_forget()

    def toggle(self):
        self._open = not self._open
        self._render()
