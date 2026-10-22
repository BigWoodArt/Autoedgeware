"""The click sound for Hero mode: a short soft tick made with the standard library only."""
import math
import os
import wave

RATE = 22050


def make_click(path, volume_percent, freq=1100.0, ms=45):
    """A short decaying tone. Volume (0-100) sets how loud the file itself is (the click plays through the
    system's own player, which has no volume control of its own)."""
    n = int(RATE * ms / 1000)
    peak = int(32767 * 0.9 * max(0, min(100, volume_percent)) / 100.0)
    data = bytearray()
    for i in range(n):
        t = i / RATE
        attack = min(1.0, i / (RATE * 0.002))          # 2 ms ramp-up: no pop at the start
        decay = math.exp(-t * 90.0)
        v = int(peak * attack * decay * math.sin(2 * math.pi * freq * t))
        data += v.to_bytes(2, "little", signed=True)
    tmp = path + ".part"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(data))
    os.replace(tmp, path)
    return path
