"""First-run questions: what do you want to see? Builds the first preset from the answers, so nothing
needs to ship inside the app."""
import tkinter as tk
from tkinter import messagebox

from ae_settings.wizard_logic import build_sources, nature_sources, safe_name
from core.win_dpi import scale_px, ui_scale
from gui.style import center_on_screen, FlatButton, FlatEntry, Toggle

# (source id, label, ticked at first)
SITES = [
    ("reddit", "Reddit", True),
    ("redgifs", "RedGifs", True),
    ("realbooru", "RealBooru", True),
    ("hypnohub", "HypnoHub", True),
    ("gelbooru", "Gelbooru", False),
    ("rule34", "Rule34", False),
    ("safebooru", "Safebooru", False),
]


class FirstRunDialog(tk.Toplevel):
    def __init__(self, parent, palette, on_submit):
        super().__init__(parent)
        self.pal, self.on_submit = palette, on_submit
        self.title("Welcome - make your first preset")
        self.configure(bg=palette["bg"])
        center_on_screen(self, 520, 600)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        wrap = scale_px(480, ui_scale(self))

        def lab(text, size=9, color=None, bold=True):
            return tk.Label(self, text=text, bg=palette["bg"], fg=color or palette["white"],
                            font=("Segoe UI", size, "bold" if bold else "normal"), justify="left",
                            wraplength=wrap)

        def entry(var):
            return FlatEntry(self, textvariable=var, bg=palette["field"], fg=palette["white"],
                            insertbackground=palette["white"], relief="flat")

        lab("What do you want to see?", 14).pack(anchor="w", padx=18, pady=(16, 2))
        lab("Answer below and popups start in a minute. You can change everything later with Edit Preset.",
            9, palette["muted"], False).pack(anchor="w", padx=18, pady=(0, 10))

        self.name_var = tk.StringVar(value="My First Preset")
        self.words_var = tk.StringVar()
        self.subs_var = tk.StringVar()
        lab("Preset name").pack(anchor="w", padx=18)
        entry(self.name_var).pack(fill="x", padx=18, pady=(2, 8))
        lab("Keywords (tags or search words, separate with commas)").pack(anchor="w", padx=18)
        entry(self.words_var).pack(fill="x", padx=18, pady=(2, 8))
        lab("Subreddits (Reddit only, separate with commas)").pack(anchor="w", padx=18)
        entry(self.subs_var).pack(fill="x", padx=18, pady=(2, 8))

        lab("Sites").pack(anchor="w", padx=18, pady=(4, 0))
        grid = tk.Frame(self, bg=palette["bg"])
        grid.pack(fill="x", padx=18)
        self.site_vars = {}
        for i, (sid, label, on) in enumerate(SITES):
            var = tk.BooleanVar(value=on)
            self.site_vars[sid] = var
            Toggle(grid, text=label, variable=var, bg=palette["bg"], fg=palette["white"],
                           selectcolor=palette["field"], activebackground=palette["bg"],
                           activeforeground=palette["white"], font=("Segoe UI", 9)
                           ).grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 14))
        lab("New here? 'Nature starter' makes a safe preset in one click.",
            8, palette["dim"], False).pack(anchor="w", padx=18, pady=(6, 0))
        lab("Gelbooru works best with an account key (Advanced tab > Site keys); without one it reads web pages.",
            8, palette["dim"], False).pack(anchor="w", padx=18, pady=(6, 0))

        self.start_var = tk.BooleanVar(value=True)
        Toggle(self, text="Start the popups as soon as I click Create", variable=self.start_var,
                       bg=palette["bg"], fg=palette["white"], selectcolor=palette["field"],
                       activebackground=palette["bg"], activeforeground=palette["white"],
                       font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(14, 0))

        row = tk.Frame(self, bg=palette["bg"])
        row.pack(fill="x", padx=18, pady=16, side="bottom")
        FlatButton(row, text="Find sources for me...", command=self._find, relief="flat", bd=0, padx=10, pady=6,
                  font=("Segoe UI", 10, "bold"), bg=palette["accent2"], fg=palette["white"],
                  activebackground=palette["accent"], activeforeground=palette["white"]
                  ).pack(side="left", padx=(8, 0))
        FlatButton(row, text="Nature starter", command=self._nature, relief="flat", bd=0, padx=10, pady=6,
                  font=("Segoe UI", 10, "bold"), bg=palette["accent2"], fg=palette["white"],
                  activebackground=palette["accent"], activeforeground=palette["white"]).pack(side="left", padx=(8, 0))
        FlatButton(row, text="Skip for now", command=self.destroy, relief="flat", bd=0, padx=10, pady=6,
                  font=("Segoe UI", 10, "bold"), bg=palette["panel3"], fg=palette["white"],
                  activebackground=palette["accent2"], activeforeground=palette["white"]).pack(side="left")
        FlatButton(row, text="Create", command=self._submit, relief="flat", bd=0, padx=14, pady=6,
                  font=("Segoe UI", 10, "bold"), bg=palette["accent"], fg=palette["white"],
                  activebackground=palette["accent2"], activeforeground=palette["white"]).pack(side="right")

    def _nature(self):
        """One click: a ready preset of nature pictures, clips and sounds."""
        self.destroy()
        self.on_submit("Nature", nature_sources(), True)

    def _find(self):
        """Skip the typing: search each site for one word and tick what you like."""
        from gui.preset_finder_dialog import PresetFinderDialog

        def done(name, sources, start_now):
            self.destroy()
            self.on_submit(name, sources, start_now)
        PresetFinderDialog(self, self.pal, done, mode="new", first_term=self.words_var.get().split(",")[0].strip())

    def _submit(self):
        sites = [sid for sid, var in self.site_vars.items() if var.get()]
        try:
            sources = build_sources(self.words_var.get(), self.subs_var.get(), sites)
        except ValueError as ex:
            messagebox.showinfo("Autoedgeware", str(ex), parent=self)
            return
        name = safe_name(self.name_var.get())
        self.destroy()
        self.on_submit(name, sources, bool(self.start_var.get()))
