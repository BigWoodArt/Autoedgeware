"""Draws the Hypno files in a separate, low-priority process so the window and the popups never stutter.
Run as:  python core/hypno_gen.py <folder> <m|l>"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv):
    from core import hypno_assets
    folder, target = argv[1], (argv[2] if len(argv) > 2 else "m")
    hypno_assets.ensure_assets(folder, None, target if target in hypno_assets.LEVELS else "m")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
