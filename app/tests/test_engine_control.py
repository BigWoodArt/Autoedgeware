"""Autoedgeware-specific (not shared): Stop/Run for the popup engine."""
import unittest

from core import engine_control


class Player:
    def __init__(self):
        self.paused = False

    def pause(self):
        self.paused = True


class Popup:
    def __init__(self, fail=False):
        self.closed, self.fail = False, fail

    def close(self):
        if self.fail:
            raise RuntimeError("stubborn")
        self.closed = True


class State:
    def __init__(self, popups, players):
        self.popups, self.audio_players = popups, players


class Control(unittest.TestCase):
    def setUp(self):
        engine_control.resume_popups()

    def tearDown(self):
        engine_control.resume_popups()

    def test_stop_closes_popups_silences_audio_and_holds_back_new_ones(self):
        chance = engine_control.gated(lambda: 40)
        self.assertEqual(chance(), 40)
        popups, players = [Popup(), Popup(fail=True), Popup()], [Player(), Player()]
        state = State(popups, players)
        closed = engine_control.stop_popups(state)
        self.assertEqual(closed, 2)                                   # the stubborn one doesn't block the rest
        self.assertTrue(popups[0].closed and popups[2].closed)
        self.assertTrue(all(p.paused for p in players))
        self.assertEqual(state.audio_players, [])
        self.assertEqual(chance(), 0)                                 # nothing new while stopped

    def test_run_again_brings_popups_back(self):
        chance = engine_control.gated(lambda: 40)
        engine_control.stop_popups(State([], []))
        self.assertEqual(chance(), 0)
        engine_control.resume_popups()
        self.assertEqual(chance(), 40)

    def test_embedded_panic_stops_but_never_touches_the_window(self):
        class Root:
            def destroy(self):
                raise AssertionError("panic must not destroy the window")
        called = []
        panic = engine_control.make_embedded_panic(lambda: called.append(1))
        popup, player = Popup(), Player()
        state = State([popup], [player])
        panic(Root(), None, state, condition=False)          # wrong key: nothing happens
        self.assertFalse(popup.closed)
        self.assertEqual(called, [])
        panic(Root(), None, state)                           # real panic: popups + audio stop
        self.assertTrue(popup.closed and player.paused)
        self.assertEqual(called, [1])
        self.assertTrue(engine_control.is_paused())


if __name__ == "__main__":
    unittest.main()


class FakeRoot:
    """Tk's after(): runs scheduled calls in time order when run() is called."""
    def __init__(self):
        self.queue, self.now, self.n = [], 0, 0

    def after(self, ms, fn):
        self.n += 1
        self.queue.append((self.now + ms, self.n, fn))

    def run(self, until_ms=10 ** 9):
        while self.queue:
            self.queue.sort()
            t, _, fn = self.queue[0]
            if t > until_ms:
                break
            self.queue.pop(0)
            self.now = t
            fn()


class Track:
    def __init__(self, volume=0.5):
        self.volume, self.playing, self.log = volume, True, []

    def pause(self):
        self.playing = False
        self.log.append("pause")

    def play(self):
        self.playing = True
        self.log.append("play")


class HibernateAudio(unittest.TestCase):
    def setUp(self):
        engine_control.resume_popups()
        engine_control._ducked.clear()

    def tearDown(self):
        engine_control.resume_popups()          # a test that pressed Stop must not leave the engine stopped
        engine_control._ducked.clear()

    def test_tracks_fade_out_and_pause_then_come_back_from_the_same_spot(self):
        root, a, b = FakeRoot(), Track(0.5), Track(0.4)
        state = State([], [a, b])
        self.assertEqual(engine_control.duck_audio(state, root), 2)
        root.run(1500)
        self.assertTrue(a.playing)                      # still fading
        self.assertTrue(0 < a.volume < 0.5)
        root.run()
        self.assertFalse(a.playing)
        self.assertFalse(b.playing)
        self.assertEqual((a.volume, b.volume), (0.0, 0.0))
        self.assertEqual(state.audio_players, [a, b])   # still its tracks: they count toward the audio limit
        self.assertEqual(engine_control.unduck_audio(state, root, 0.6), 2)
        self.assertTrue(a.playing and b.playing)
        root.run(1500)
        self.assertTrue(0 < a.volume < 0.6)
        root.run()
        self.assertAlmostEqual(a.volume, 0.6)
        self.assertEqual(a.log, ["pause", "play"])      # paused and resumed, never restarted or stopped

    def test_a_second_duck_does_nothing_and_unduck_without_duck_does_nothing(self):
        root, a = FakeRoot(), Track()
        state = State([], [a])
        self.assertEqual(engine_control.duck_audio(state, root), 1)
        self.assertEqual(engine_control.duck_audio(state, root), 0)
        root.run()
        self.assertEqual(a.log, ["pause"])
        self.assertEqual(engine_control.unduck_audio(state, root, 0.5), 1)
        self.assertEqual(engine_control.unduck_audio(state, root, 0.5), 0)

    def test_tracks_that_ended_or_were_stopped_meanwhile_are_not_started_again(self):
        root, a, b = FakeRoot(), Track(), Track()
        state = State([], [a, b])
        engine_control.duck_audio(state, root)
        root.run()
        state.audio_players.remove(a)                   # e.g. it was closed
        self.assertEqual(engine_control.unduck_audio(state, root, 0.5), 1)
        self.assertEqual(a.log, ["pause"])
        # Stop while asleep: nothing is brought back
        c = Track()
        state2 = State([], [c])
        engine_control.duck_audio(state2, root)
        root.run()
        engine_control.stop_popups(state2)
        self.assertEqual(engine_control.unduck_audio(state2, root, 0.5), 0)

    def test_the_engine_does_it_on_hibernate_and_audio_fades_by_playing_time(self):
        import os
        base = os.path.join(os.path.dirname(__file__), "..")
        run = open(os.path.join(base, "run_engine.py"), encoding="utf-8").read()
        self.assertIn("engine_control.duck_audio(state, root)", run)
        self.assertIn("engine_control.unduck_audio(state, root, settings.audio_volume)", run)
        audio = open(os.path.join(base, "edgeware_core", "src", "features", "audio.py"), encoding="utf-8").read()
        self.assertIn("player.time >= fade_start", audio)
        self.assertNotIn("root.after(audio_duration - fade_out_duration", audio)
