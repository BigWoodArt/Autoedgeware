"""Launch the Autoedgeware config GUI: python gui_main.py"""
# Edgeware expects to run DPI-unaware (its own launchers do this). Must happen
# before any Tk window exists, or 4K/scaled screens misplace video popups.
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(0)
except Exception:
    pass

from gui.app import AutoedgewareGUI

if __name__ == "__main__":
    AutoedgewareGUI().mainloop()
