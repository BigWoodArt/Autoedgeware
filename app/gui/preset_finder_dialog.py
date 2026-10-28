"""Preset Finder: type a word, see what each site has for it, tick what you want, add more words,
then save. Results are kept between searches, so ticks survive 'Add new term'."""
import threading
import tkinter as tk
from tkinter import messagebox

from ae_settings.wizard_logic import safe_name
from core import preset_finder
from core.source_registry import SOURCE_REGISTRY
from core.win_dpi import scale_px, ui_scale
from gui.widgets import ScrollFrame
from gui.style import center_on_screen, FlatButton, FlatEntry, Toggle


class PresetFinderDialog(tk.Toplevel):
    """mode 'new': asks for a name and can start right away; on_submit(name, sources, start_now).
    mode 'add': on_submit(None, sources, False) so the caller can add rows to an existing preset."""

    def __init__(self, parent, palette, on_submit, mode="new", first_term=""):
        super().__init__(parent)
        self.pal, self.on_submit, self.mode = palette, on_submit, mode
        self.picks = []                 # every Pick shown so far
        self.vars = {}                  # pick.key -> BooleanVar
        self._busy = False
        self.title("Find sources" if mode == "add" else "Find sources for a new preset")
        self.configure(bg=palette["bg"])
        center_on_screen(self, 620, 680)
        self.transient(parent)
        self.grab_set()
        self._text_w = scale_px(580, ui_scale(self))
        self._row_w = scale_px(540, ui_scale(self))

        def lab(parent_, text, color=None, size=9, bold=True):
            return tk.Label(parent_, text=text, bg=palette["bg"], fg=color or palette["white"], justify="left",
                            font=("Segoe UI", size, "bold" if bold else "normal"), wraplength=self._text_w)

        def btn(parent_, text, cmd, primary=False):
            return FlatButton(parent_, text=text, command=cmd, relief="flat", bd=0, padx=12, pady=6,
                             font=("Segoe UI", 10, "bold"), cursor="hand2",
                             bg=palette["accent"] if primary else palette["panel3"], fg=palette["white"],
                             activebackground=palette["accent2"], activeforeground=palette["white"],
                             disabledforeground=palette["dim"])

        # Bottom first so it always keeps its space.
        bottom = tk.Frame(self, bg=palette["bg"])
        bottom.pack(side="bottom", fill="x", padx=16, pady=(4, 14))
        self.count_var = tk.StringVar()
        tk.Label(bottom, textvariable=self.count_var, bg=palette["bg"], fg=palette["muted"],
                 font=("Segoe UI", 9), wraplength=self._text_w, justify="left").pack(anchor="w", pady=(0, 6))
        if mode == "new":
            self.start_var = tk.BooleanVar(value=True)
            Toggle(bottom, text="Start the popups as soon as I save", variable=self.start_var,
                           bg=palette["bg"], fg=palette["white"], selectcolor=palette["field"],
                           activebackground=palette["bg"], activeforeground=palette["white"],
                           font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        row = tk.Frame(bottom, bg=palette["bg"])
        row.pack(fill="x")
        btn(row, "Cancel", self.destroy).pack(side="left")
        btn(row, "Add new term", self._add_new_term).pack(side="left", padx=(8, 0))
        btn(row, "Save preset" if mode == "new" else "Add to preset", self._save, primary=True).pack(side="right")

        top = tk.Frame(self, bg=palette["bg"])
        top.pack(fill="x", padx=16, pady=(14, 0))
        if mode == "new":
            lab(top, "Preset name").pack(anchor="w")
            self.name_var = tk.StringVar(value="My Preset")
            FlatEntry(top, textvariable=self.name_var, bg=palette["field"], fg=palette["white"],
                     insertbackground=palette["white"], relief="flat").pack(fill="x", pady=(2, 8))
        lab(top, "Type a word, then Search").pack(anchor="w")
        srow = tk.Frame(top, bg=palette["bg"])
        srow.pack(fill="x", pady=(2, 6))
        self.term_var = tk.StringVar(value=first_term)
        self.term_entry = FlatEntry(srow, textvariable=self.term_var, bg=palette["field"], fg=palette["white"],
                                   insertbackground=palette["white"], relief="flat")
        self.term_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.term_entry.bind("<Return>", lambda e: self._search())
        self.search_btn = btn(srow, "Search", self._search)
        self.search_btn.pack(side="left")

        lab(top, "Sites to search").pack(anchor="w")
        grid = tk.Frame(top, bg=palette["bg"])
        grid.pack(fill="x", pady=(2, 4))
        self.site_vars = {}
        for i, (site, on) in enumerate(preset_finder.FINDER_SITES):
            cls = SOURCE_REGISTRY.get(site)
            if cls is None:
                continue
            var = tk.BooleanVar(value=on)
            self.site_vars[site] = var
            Toggle(grid, text=cls.label, variable=var, bg=palette["bg"], fg=palette["white"],
                           selectcolor=palette["field"], activebackground=palette["bg"],
                           activeforeground=palette["white"], font=("Segoe UI", 9), highlightthickness=0
                           ).grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 10))

        self.status_var = tk.StringVar(value="Results appear below. Tick the ones you want.")
        tk.Label(top, textvariable=self.status_var, bg=palette["bg"], fg=palette["muted"],
                 font=("Segoe UI", 9), wraplength=self._text_w, justify="left").pack(anchor="w", pady=(4, 2))

        self.results = ScrollFrame(self, palette["panel"])
        self.results.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self._update_count()
        self.term_entry.focus_set()
        if first_term:
            self.after(200, self._search)

    # ---------- search ----------

    def _search(self):
        if self._busy:
            return
        term = self.term_var.get()
        sites = [s for s, v in self.site_vars.items() if v.get()]
        if not sites:
            self.status_var.set("Tick at least one site to search.")
            return
        self._busy = True
        self.search_btn.configure(state="disabled")
        self.status_var.set(f"Searching {len(sites)} site(s) for \"{preset_finder.clean_term(term)}\"... (up to {int(preset_finder.SEARCH_TIMEOUT)} s)")

        def work():
            try:
                found = preset_finder.find(term, sites, SOURCE_REGISTRY)
                error = None
            except ValueError as ex:
                found, error = None, str(ex)
            except Exception as ex:      # never let a site take the window down
                found, error = None, f"Search failed: {ex}"
            try:
                self.after(0, self._show, found, error)
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def _show(self, found, error):
        self._busy = False
        self.search_btn.configure(state="normal")
        if error:
            self.status_var.set(error)
            return
        before = len(self.picks)
        preset_finder.merge(self.picks, found)
        added = len(self.picks) - before
        self.status_var.set(f"Added {added} result(s). Not every site answers; \"search as typed\" always works.")
        self._render()

    def _render(self):
        pal = self.pal
        for child in self.results.body.winfo_children():
            child.destroy()
        by_site = {}
        for p in self.picks:
            by_site.setdefault(p.site, []).append(p)
        for site, picks in by_site.items():
            label = getattr(SOURCE_REGISTRY.get(site), "label", site)
            tk.Label(self.results.body, text=label.upper(), bg=pal["panel"], fg=pal["accent2"],
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
            for p in picks:
                var = self.vars.get(p.key)
                if var is None:
                    var = tk.BooleanVar(value=p.ticked)
                    var.trace_add("write", lambda *_a, pick=p, v=var: self._on_tick(pick, v))
                    self.vars[p.key] = var
                text = p.label + (f"   ({p.count:,})" if p.count is not None else "") + (f"   - {p.note}" if p.note else "")
                Toggle(self.results.body, text=text, variable=var, anchor="w", justify="left",
                               bg=pal["panel"], fg=pal["white"], selectcolor=pal["field"],
                               activebackground=pal["panel"], activeforeground=pal["white"],
                               font=("Segoe UI", 9), highlightthickness=0, wraplength=self._row_w
                               ).pack(anchor="w", padx=16)
        self._update_count()

    def _on_tick(self, pick, var):
        pick.ticked = bool(var.get())
        self._update_count()

    def _update_count(self):
        n = len(preset_finder.to_sources(self.picks))
        text = f"{n} source(s) picked."
        if n > preset_finder.WARN_ABOVE:
            text += f" That is a lot: more than {preset_finder.WARN_ABOVE} sources makes downloads slower."
        self.count_var.set(text)

    # ---------- buttons ----------

    def _add_new_term(self):
        """Keep every result and tick; clear the box for the next word."""
        self.term_var.set("")
        self.term_entry.focus_set()
        self.status_var.set("Type another word, then Search. Your ticks are kept.")

    def _save(self):
        sources = preset_finder.to_sources(self.picks)
        if not sources:
            messagebox.showinfo("Autoedgeware", "Tick at least one result first.", parent=self)
            return
        if self.mode == "new":
            name, start = safe_name(self.name_var.get()), bool(self.start_var.get())
            self.destroy()
            self.on_submit(name, sources, start)
        else:
            self.destroy()
            self.on_submit(None, sources, False)
