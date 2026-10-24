"""Launch the Autoedgeware config GUI: python gui_main.py"""
# Edgeware expects to run DPI-unaware (its own launchers do this). Must happen
# before any Tk window exists, or 4K/scaled screens misplace video popups.
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(0)
except Exception:
    pass

import os

from core import ssl_fix
ssl_fix.install_from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ae_settings", "settings.json"))  # also trust certifi's roots: fixes "certificate has expired" on PCs with an old store

from gui.app import AutoedgewareGUI

if __name__ == "__main__":
    AutoedgewareGUI().mainloop()
