"""Toplevel dialog for creating or editing a Scrape Preset: a name field
plus a growable list of source rows (site type + tag/query), each
removable with its own '-' button. Used identically by both the
'Create Preset' and 'Edit Preset' buttons - only the title and whether
it starts pre-filled differ."""
import tkinter as tk

from gui.widgets import ScrollFrame

from ae_settings.preset import QUALITY_LEVELS, source_entry
from core.source_groups import grouped
from core import quality_map
from core.source_registry import SOURCE_REGISTRY, SOURCE_TYPES
from gui.style import center_on_screen, FlatButton, FlatEntry, Toggle


class PresetEditorDialog(tk.Toplevel):
    def __init__(self, parent, palette, on_submit, title="Create Scrape Preset",
                 initial_name="", initial_sources=None, initial_enabled=True):
        super().__init__(parent)
        self.pal = palette
        self.on_submit = on_submit
        self.rows = []  # list of dicts: {frame, type_var, query_var}

        self.title(title)
        self.configure(bg=palette["bg"])
        center_on_screen(self, 600, 560)
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text=title.upper(), bg=palette["bg"], fg=palette["white"],
                  font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 6))

        name_row = tk.Frame(self, bg=palette["bg"])
        name_row.pack(fill="x", padx=16)
        tk.Label(name_row, text="Title", bg=palette["bg"], fg=palette["muted"],
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.name_var = tk.StringVar(value=initial_name)
        FlatEntry(name_row, textvariable=self.name_var, bg=palette["field"], fg=palette["white"],
                  insertbackground=palette["white"], relief="flat").pack(fill="x", pady=(2, 6))

        self.enabled_var = tk.BooleanVar(value=True)   # kept for old callers; a run uses only the selected preset now

        rows_header = tk.Frame(self, bg=palette["bg"])
        rows_header.pack(fill="x", padx=16)
        tk.Label(rows_header, text="Sources (site / tag / limit / quality)", bg=palette["bg"], fg=palette["muted"],
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        FlatButton(rows_header, text="+", command=self._add_row, relief="flat", bd=0,
                   width=3, font=("Segoe UI", 10, "bold"), bg=palette["accent2"], fg=palette["white"],
                   activebackground=palette["accent"], activeforeground=palette["white"]
                   ).pack(side="right")

        self._scroll = ScrollFrame(self, palette["bg"])
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(4, 4))
        self.rows_container = self._scroll.body

        btn_row = tk.Frame(self, bg=palette["bg"])
        btn_row.pack(fill="x", padx=16, pady=(4, 14), side="bottom")
        FlatButton(btn_row, text="Cancel", command=self.destroy, relief="flat", bd=0,
                   padx=10, pady=6, font=("Segoe UI", 10, "bold"),
                   bg=palette["panel3"], fg=palette["white"],
                   activebackground=palette["accent2"], activeforeground=palette["white"]
                   ).pack(side="left")
        FlatButton(btn_row, text="Find more...", command=self._find_more, relief="flat", bd=0,
                   padx=10, pady=6, font=("Segoe UI", 10, "bold"),
                   bg=palette["accent2"], fg=palette["white"],
                   activebackground=palette["accent"], activeforeground=palette["white"]
                   ).pack(side="left", padx=(8, 0))
        FlatButton(btn_row, text="OK", command=self._submit, relief="flat", bd=0,
                   padx=10, pady=6, font=("Segoe UI", 10, "bold"),
                   bg=palette["accent"], fg=palette["white"],
                   activebackground=palette["accent2"], activeforeground=palette["white"]
                   ).pack(side="right")

        initial_sources = initial_sources or [{"source_type": SOURCE_TYPES[0], "query": ""}]
        for entry in initial_sources:
            self._add_row(entry.get("source_type", SOURCE_TYPES[0]), entry.get("query", ""),
                          str(entry.get("limit", "")) if entry.get("limit") else "",
                          entry.get("quality", "Any"))

    def _add_row(self, source_type=None, query="", limit="", quality="Any"):
        pal = self.pal
        row_frame = tk.Frame(self.rows_container, bg=pal["bg"])
        row_frame.pack(fill="x", pady=2)

        type_var = tk.StringVar(value=source_type or SOURCE_TYPES[0])
        # One list with a heading per group (Image Boards / Audio / Video / Images) instead of one long list.
        menu = tk.Menubutton(row_frame, textvariable=type_var, indicatoron=True, anchor="w",
                              bg=pal["panel3"], fg=pal["white"], relief="flat", bd=0,
                              activebackground=pal["accent2"], activeforeground=pal["white"],
                              highlightthickness=0, font=("Segoe UI", 9), width=11)
        popup = tk.Menu(menu, tearoff=0, bg=pal["panel3"], fg=pal["white"],
                         activebackground=pal["accent2"], activeforeground=pal["white"],
                         disabledforeground=pal["accent2"], font=("Segoe UI", 9))
        for index, (group, ids) in enumerate(grouped(SOURCE_TYPES)):
            if index:
                popup.add_separator()
            popup.add_command(label=f"{group}:", state="disabled", font=("Segoe UI", 9, "bold"))
            for sid in ids:
                popup.add_radiobutton(label=f"   {sid}", variable=type_var, value=sid)
        menu["menu"] = popup
        menu.pack(side="left")

        query_var = tk.StringVar(value=query)
        entry = FlatEntry(row_frame, textvariable=query_var, bg=pal["field"], fg=pal["white"],
                          insertbackground=pal["white"], relief="flat")
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))

        limit_var = tk.StringVar(value=limit)
        limit_entry = FlatEntry(row_frame, textvariable=limit_var, width=4, bg=pal["field"], fg=pal["white"],
                                insertbackground=pal["white"], relief="flat")
        limit_entry.pack(side="left", padx=(0, 6))

        # Any / Good / Best: a Top sort on Reddit/Redgifs, a minimum score on the booru sites.
        # Greyed out for sites that have no such thing (Soundgasm, Erome).
        quality_var = tk.StringVar(value=quality if quality in QUALITY_LEVELS else "Any")
        quality_menu = tk.OptionMenu(row_frame, quality_var, *QUALITY_LEVELS)
        quality_menu.configure(bg=pal["panel3"], fg=pal["white"], relief="flat", bd=0,
                                activebackground=pal["accent2"], activeforeground=pal["white"],
                                disabledforeground=pal["dim"], highlightthickness=0,
                                font=("Segoe UI", 9), width=5)
        quality_menu["menu"].configure(bg=pal["panel3"], fg=pal["white"],
                                        activebackground=pal["accent2"], activeforeground=pal["white"])
        quality_menu.pack(side="left", padx=(0, 6))

        def sync_quality(*_):
            supported = quality_map.supported(type_var.get())
            quality_menu.configure(state="normal" if supported else "disabled")
            if not supported:
                quality_var.set("Any")
        type_var.trace_add("write", sync_quality)
        sync_quality()

        row = {"frame": row_frame, "type_var": type_var, "query_var": query_var, "limit_var": limit_var,
               "quality_var": quality_var}

        remove_btn = FlatButton(row_frame, text="\u2212", relief="flat", bd=0, width=3,
                                 font=("Segoe UI", 10, "bold"), bg=pal["panel3"], fg=pal["white"],
                                 activebackground=pal["danger"], activeforeground=pal["white"],
                                 command=lambda r=row: self._remove_row(r))
        remove_btn.pack(side="left")

        self.rows.append(row)

    def _find_more(self):
        """Open the Preset Finder and add whatever gets ticked as new rows (existing rows are kept)."""
        from gui.preset_finder_dialog import PresetFinderDialog

        def add(_name, sources, _start):
            existing = {(r["type_var"].get(), r["query_var"].get().strip().lower()) for r in self.rows}
            for s in sources:
                if (s["source_type"], s["query"].strip().lower()) in existing:
                    continue
                if len(self.rows) == 1 and not self.rows[0]["query_var"].get().strip():
                    self._remove_row_force(self.rows[0])      # drop the empty starter row
                self._add_row(s["source_type"], s["query"])
        PresetFinderDialog(self, self.pal, add, mode="add")

    def _remove_row_force(self, row):
        row["frame"].destroy()
        self.rows.remove(row)

    def _remove_row(self, row):
        if len(self.rows) <= 1:
            return  # keep at least one row
        row["frame"].destroy()
        self.rows.remove(row)

    def _submit(self):
        name = self.name_var.get().strip()
        if not name:
            return
        sources = [source_entry(r["type_var"].get(), r["query_var"].get(), r["limit_var"].get(),
                                r["quality_var"].get()) for r in self.rows]
        self.on_submit(name, sources, bool(self.enabled_var.get()))
        self.destroy()
