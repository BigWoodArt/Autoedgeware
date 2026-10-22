"""Autoedgeware's video popup: Edgeware's own VideoPopup, except that a wide video can fill a whole monitor.

Other popups keep appearing on top of it (they are created later, so they stack above). One fullscreen video
at a time. It closes on Panic and Stop like any popup (it is in state.popups), and by itself after a set time.
Import only after edgeware_core/src is on sys.path (see run_engine.py)."""
import utils
from features.video_popup import VideoPopup

from core import file_log
from core.fullscreen_video import fullscreen_decision, play_seconds

CONFIG = {"chance": 0, "seconds": 600, "log_dir": None, "volume_pct": 70, "min_height": 1080,   # seconds = longest a video may stay up
          "click_close": True}      # False: clicking a FULLSCREEN video does nothing; it plays to its end (small popups are unaffected)


def configure(chance, seconds, log_dir=None, volume_pct=70, min_height=1080, click_close=True):
    CONFIG.update(chance=max(0, min(100, int(chance))), seconds=max(10, int(seconds)), log_dir=log_dir,
                  volume_pct=max(0, min(100, int(volume_pct))), min_height=max(0, int(min_height)),
                  click_close=bool(click_close))


class AEVideoPopup(VideoPopup):
    _fullscreen_open = False      # shared by all instances: only one at a time

    def _finish_init(self, properties: dict) -> None:
        self._ae_duration = properties.get("duration")     # seconds, as text, from ffprobe
        super()._finish_init(properties)
        if getattr(self, "_ae_full", False):      # a whole screen of video sounds louder: turn it down
            try:
                pct = max(0, min(100, int(self.settings_ae_pct())))
                self.player.mpv["volume"] = self.settings.video_volume * pct / 100
            except Exception:
                pass

    def compute_geometry(self, source_width: int, source_height: int) -> None:
        self._ae_full = False
        yes, why = fullscreen_decision(source_width, source_height, CONFIG["chance"], AEVideoPopup._fullscreen_open,
                                       min_height=CONFIG["min_height"])
        if CONFIG["log_dir"] and CONFIG["chance"] > 0:
            file_log.write(CONFIG["log_dir"], f"POPUP: video {source_width}x{source_height}: "
                           f"{'fullscreen' if yes else 'normal popup - ' + why}", "info")
        if yes:
            self.monitor = utils.random_monitor(self.settings)
            self.width, self.height = self.monitor.width, self.monitor.height
            self.x, self.y = self.monitor.x, self.monitor.y
            self.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
            self._ae_full = True
            AEVideoPopup._fullscreen_open = True
            self.after(400, self._lift_others)
            self.after(450, self._lift_hypno)
            self.after(1500, self._lift_hypno)
            self.after(3000, self._lift_hypno)
            # Plays to its end once (not the normal popup timer), capped at the Settings maximum.
            self.after(int(play_seconds(getattr(self, "_ae_duration", None), CONFIG["seconds"]) * 1000), self._expire)
            if CONFIG["log_dir"]:
                file_log.write(CONFIG["log_dir"], f"POPUP: fullscreen video: {self.media.name}", "info")
            return
        super().compute_geometry(source_width, source_height)

    def _lift_others(self):
        """Popups that were already open would be hidden by the new fullscreen window: bring them back up."""
        try:
            for popup in list(self.state.popups):
                if popup is not self:
                    popup.lift()
        except Exception:
            pass

    def settings_ae_pct(self):
        return CONFIG.get("volume_pct", 70)

    def _lift_hypno(self):
        try:
            hypno = getattr(self.state, "ae_hypno", None)
            if hypno is not None:
                hypno.keep_alive()
            hero = getattr(self.state, "ae_hero", None)
            if hero is not None:
                hero.raise_now()
        except Exception:
            pass

    def _expire(self):
        if self in self.state.popups:
            self.close()

    def try_timeout(self) -> None:
        if not self._ae_full:        # the normal popup timer would cut a fullscreen video short (it has its own end)
            super().try_timeout()

    def try_button(self) -> None:
        if getattr(self, "_ae_full", False) and not CONFIG["click_close"]:
            return                   # a fullscreen video that cannot be clicked away: it plays to its end (Panic/Stop still close it)
        super().try_button()

    def try_move(self) -> None:
        if not self._ae_full:
            super().try_move()

    def close(self) -> None:
        if getattr(self, "_ae_full", False):
            AEVideoPopup._fullscreen_open = False
            self._ae_full = False
        super().close()
