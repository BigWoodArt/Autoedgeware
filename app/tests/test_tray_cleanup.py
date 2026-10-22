"""Autoedgeware-only: the tray icon is removed on every exit path."""
import unittest
from pathlib import Path

from core import engine_control

ROOT = Path(__file__).resolve().parent.parent


class Tray:
    def __init__(self, fail=False):
        self.calls, self._visible, self.fail = [], True, fail

    @property
    def visible(self): return self._visible

    @visible.setter
    def visible(self, v):
        self.calls.append(f"visible={v}")
        self._visible = v

    def stop(self):
        self.calls.append("stop")
        if self.fail:
            raise OSError("boom")


class State:
    pass


class StopTray(unittest.TestCase):
    def test_hides_then_stops_once(self):
        st = State(); st.tray = Tray()
        engine_control.stop_tray(st)
        engine_control.stop_tray(st)
        self.assertEqual(st.tray.calls, ["visible=False", "stop"])

    def test_no_tray_is_fine(self):
        engine_control.stop_tray(State())
        st = State(); st.tray = None
        engine_control.stop_tray(st)

    def test_errors_never_escape(self):
        st = State(); st.tray = Tray(fail=True)
        engine_control.stop_tray(st)

    def test_tray_object_is_kept_so_edgewares_own_panic_still_works(self):
        st = State(); st.tray = Tray()
        engine_control.stop_tray(st)
        self.assertIsNotNone(st.tray)


class Wiring(unittest.TestCase):
    def test_every_exit_path_calls_it(self):
        engine = (ROOT / "run_engine.py").read_text(encoding="utf-8")
        self.assertIn("atexit.register(lambda: engine_control.stop_tray(state))", engine)
        self.assertIn("engine_control.stop_tray(state)", engine)                    # after mainloop ends
        gui = (ROOT / "gui/app.py").read_text(encoding="utf-8")
        self.assertIn("engine_control.shutdown(self._live_state)", gui)           # window closed


class TrayHide(unittest.TestCase):
    def state(self):
        st = State()
        st.tray, st.popups, st.audio_players = Tray(), [], []
        return st

    def test_stop_hides_and_run_shows(self):
        st = self.state()
        engine_control.stop_popups(st)
        self.assertFalse(st.tray.visible)
        engine_control.resume_popups(st)
        self.assertTrue(st.tray.visible)

    def test_embedded_panic_hides(self):
        st = self.state()
        engine_control.make_embedded_panic()(None, None, st)
        self.assertFalse(st.tray.visible)

    def test_no_tray_or_stopped_tray(self):
        st = State()
        st.popups, st.audio_players = [], []
        engine_control.stop_popups(st)               # no tray: no error
        st = self.state()
        engine_control.stop_tray(st)
        st.tray.calls.clear()
        engine_control.resume_popups(st)
        self.assertEqual(st.tray.calls, [])          # stopped for good: never shown again


if __name__ == "__main__":
    unittest.main()


class ShutdownAll(unittest.TestCase):
    def test_shutdown_ends_tray_keyboard_and_arms_exit(self):
        calls = []

        class Proc:
            def terminate(self): calls.append("terminate")
            def join(self, t): calls.append("join")
            def is_alive(self): return False
        st = State()
        st.tray, st.popups, st.audio_players, st.keyboard_process = Tray(), [], [], Proc()
        timer = engine_control.shutdown(st, force_after=60, exit_fn=lambda: None)
        try:
            self.assertIn("stop", st.tray.calls)
            self.assertEqual(calls[:2], ["terminate", "join"])
            self.assertTrue(timer.daemon and timer.is_alive())
        finally:
            timer.cancel()
