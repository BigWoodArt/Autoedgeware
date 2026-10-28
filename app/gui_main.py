"""Launch the Autoedgeware config GUI: python gui_main.py"""
# Windows display scale (125%, 150%, ...) has to be chosen before any Tk window,
# or Windows bitmap-stretches the UI and a 2K screen looks soft.
try:
    from core.win_dpi import enable
    enable()
except Exception:
    pass

import os

from core import ssl_fix
ssl_fix.install_from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ae_settings", "settings.json"))  # also trust certifi's roots: fixes "certificate has expired" on PCs with an old store

from gui.app import AutoedgewareGUI

if __name__ == "__main__":
    AutoedgewareGUI().mainloop()
