"""Autoedgeware-only: Hypno mode is hooked into every place it must be (checks the source text and the stop path)."""
import unittest
from pathlib import Path

from ae_settings.settings import DEFAULTS
from core import engine_control

ROOT = Path(__file__).resolve().parent.parent


def text(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Hypno:
    def __init__(self): self.calls = []
    def teardown(self): self.calls.append("teardown")
    def shutdown(self): self.calls.append("shutdown")


class State:
    pass


class StopPaths(unittest.TestCase):
    def test_stop_takes_it_down_and_exit_ends_it(self):
        st = State(); st.ae_hypno = Hypno(); st.audio_players = []; st.popups = []
        engine_control.stop_popups(st)
        self.assertEqual(st.ae_hypno.calls, ["teardown"])
        engine_control.stop_hypno(st, final=True)
        self.assertEqual(st.ae_hypno.calls, ["teardown", "shutdown"])
        engine_control.resume_popups()

    def test_no_hypno_is_fine(self):
        engine_control.stop_hypno(State())
        engine_control.stop_hypno(None, final=True)


class Wiring(unittest.TestCase):
    def test_setting_default_is_off_and_saved_by_the_window(self):
        self.assertIs(DEFAULTS["hypno_mode"], False)
        gui = text("gui/app.py")
        self.assertIn('self.settings["hypno_mode"] = bool(self.hypno_var.get())', gui)
        self.assertIn("Hypno mode", gui)
        self.assertIn("binaural beats", gui)                       # the short explanation under the checkbox

    def test_checkbox_sits_on_the_main_tab_under_the_presets(self):
        gui = text("gui/app.py")
        main_tab = gui[gui.index("def _build_main_tab"):gui.index("def _build_popups_tab")]
        self.assertIn("Hypno mode", main_tab)
        self.assertLess(main_tab.index("media_count_label.pack"), main_tab.index("Hypno mode"))
        self.assertLess(main_tab.index("Hypno mode"), main_tab.index('"INTENSITY"'))

    def test_checkbox_works_while_running(self):
        gui = text("gui/app.py")
        self.assertIn("command=self._on_hypno_toggle", gui)
        self.assertIn("hypno.set_enabled(self.hypno_var.get())", gui)

    def test_engine_creates_it_starts_it_and_ends_it_on_every_exit(self):
        engine = text("run_engine.py")
        self.assertIn("HypnoController(root, settings, pack, state, BASE_DIR)", engine)
        self.assertIn('hypno.set_enabled(ae_settings.get("hypno_mode", False))', engine)
        self.assertIn('_safe("hypno mode", hypno.start)', engine)
        self.assertIn("atexit.register(lambda: engine_control.stop_hypno(state, final=True))", engine)
        self.assertGreaterEqual(engine.count("engine_control.stop_hypno(state, final=True)"), 3)   # atexit, panic, exit
        self.assertIn("engine_control.stop_hypno(self._live_state, final=True)", text("gui/app.py"))

    def test_spiral_is_clickthrough_fullscreen_and_outside_the_popup_lists(self):
        src = text("hypno.py")
        self.assertIn("set_clickthrough(self)", src)
        self.assertIn("monitor.width, monitor.height", src)
        self.assertIn("self.state.popups.remove(self)", src)       # popups do not dodge it
        self.assertIn("self.state.popup_number -= 1", src)
        self.assertIn("def should_init", src)                      # does not use up a video slot
        self.assertIn("def _probe", src)                           # needs no ffprobe
        self.assertIn("if self._ae_closed", src)                   # closed before it finished opening

    def test_beats_do_not_count_as_playing_sounds(self):
        src = text("hypno.py")
        self.assertIn("mpv.MPV(", src)
        self.assertNotIn("audio_players.append", src)      # never registered in the list that caps sounds

    def test_opacity_comes_from_the_capped_function(self):
        self.assertIn("hypno_logic.opacity(lvl)", text("hypno.py"))


if __name__ == "__main__":
    unittest.main()


class KeepAliveWiring(unittest.TestCase):
    def test_fullscreen_video_restores_hypno(self):
        src = open(Path(__file__).parent.parent / "ae_video_popup.py", encoding="utf-8").read()
        self.assertIn("keep_alive", src)
        self.assertIn("_lift_hypno", src)

    def test_controller_has_keep_alive(self):
        src = open(Path(__file__).parent.parent / "hypno.py", encoding="utf-8").read()
        self.assertIn("def keep_alive", src)
        self.assertIn("player.play(self.beat_file)", src)
        self.assertIn("self.keep_alive()", src)


class FullscreenFixes(unittest.TestCase):
    def test_spiral_over_fullscreen_video(self):
        src = (Path(__file__).parent.parent / "hypno.py").read_text(encoding="utf-8")
        self.assertIn('getattr(popup, "_ae_full", False)', src)
        self.assertIn("loop_file=\"inf\"", src)
        self.assertIn("idle_active", src)

    def test_fullscreen_volume(self):
        src = (Path(__file__).parent.parent / "ae_video_popup.py").read_text(encoding="utf-8")
        self.assertIn('self.player.mpv["volume"]', src)
        self.assertEqual(DEFAULTS["fullscreen_video_volume_pct"], 70)


class SpiralWatch(unittest.TestCase):
    def _spiral(self, idle, paused):
        import ast
        src = text("hypno.py")
        node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_watch")
        ns = {"WATCH_MS": 1000}
        exec(ast.get_source_segment(src, node).replace("\n    ", "\n"), ns)   # dedent
        class MP:
            idle_active, pause = idle, paused
            played = None
            def play(self, m): self.played = m
        sp = type("S", (), {})()
        sp._watch = lambda: ns["_watch"](sp)
        sp._ae_closed, sp.media = False, "x.mp4"
        sp.player = type("P", (), {"mpv": MP()})()
        sp.after = lambda *a, **k: None
        sp._note = lambda t: None
        sp.state = type("St", (), {"popups": []})()
        sp.calls = []
        sp.attributes = lambda *a: sp.calls.append(a)
        sp.lift = lambda: sp.calls.append("lift")
        sp._lift_others = lambda: sp.calls.append("others")
        return sp

    def test_restarts_a_stopped_picture(self):
        sp = self._spiral(True, False); sp._watch()
        self.assertEqual(sp.player.mpv.played, "x.mp4")

    def test_resumes_a_paused_picture(self):
        sp = self._spiral(False, True); sp._watch()
        self.assertFalse(sp.player.mpv.pause)

    def test_leaves_a_playing_picture_alone(self):
        sp = self._spiral(False, False); sp._watch()
        self.assertIsNone(sp.player.mpv.played)

    def test_retakes_the_top_while_a_fullscreen_video_plays(self):
        sp = self._spiral(False, False)
        sp._watch()
        self.assertEqual(sp.calls, [])
        sp.state.popups.append(type("V", (), {"_ae_full": True})())
        sp._watch()
        self.assertIn("lift", sp.calls)
        self.assertIn(("-topmost", True), sp.calls)
