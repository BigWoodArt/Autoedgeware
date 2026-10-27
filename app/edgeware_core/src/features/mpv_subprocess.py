# Copyright (C) 2025 Araten & Marigold
#
# This file is part of Edgeware++.
#
# Edgeware++ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Edgeware++ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Edgeware++.  If not, see <https://www.gnu.org/licenses/>.

import ast
import io
import sys

# Same per-monitor mode as the main window, before mpv loads. A player that
# disagrees about DPI draws the video in the wrong place on a scaled screen.
if sys.platform == "win32":
    try:
        import ctypes
        _dpi = ctypes.windll.user32.SetProcessDpiAwarenessContext
        _dpi.argtypes = [ctypes.c_void_p]
        _dpi.restype = ctypes.c_int
        _dpi(ctypes.c_void_p(-4))   # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    except Exception:
        pass

import mpv
from PIL import Image

_, wid, properties_str, media, overlay = sys.argv
properties = ast.literal_eval(properties_str)

player = mpv.MPV(wid=wid)
for key, value in properties.items():
    player[key] = value

# Light settings for many small popups (same list as VideoPlayer.LIGHT_PROPERTIES); unknown names are skipped.
for key, value in {"vd-lavc-threads": 2, "demuxer-max-bytes": "16777216", "demuxer-max-back-bytes": "4194304",
                   "hidpi-window-scale": "no"}.items():
    try:
        player[key] = value
    except Exception:
        pass

if int(overlay):
    bytes = sys.stdin.buffer.read()
    image = Image.open(io.BytesIO(bytes))
    player.create_image_overlay().update(image)

player.play(media)
player.wait_for_playback()
