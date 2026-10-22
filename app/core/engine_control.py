"""Stop / Run for the popup engine WITHOUT quitting the app.

Edgeware's own panic() ends by destroying the main window - which, when the engine runs inside the
Autoedgeware window, closes Autoedgeware itself. Stop uses this instead: close open popups, silence
audio, and hold back new ones until Run. (The tray icon's Panic still quits everything, on purpose.)
No Edgeware imports here, so it can be tested on its own."""
_paused = False
_hold = False           # Hero mode's 'Hold': no NEW popups (open ones stay)


def set_hold(flag):
    global _hold
    _hold = bool(flag)


_ducked = []            # audio players paused for Hibernate (they carry on from the same spot afterwards)
DUCK_MS = 3000          # fade out / fade in time


def _ramp(root, ms, step_fn, done=None, tick_ms=40):
    """Call step_fn(0..1) in even steps over `ms` (on Tk's own timer), then done()."""
    steps = max(1, int(ms // tick_ms))
    count = [0]

    def tick():
        count[0] += 1
        step_fn(min(1.0, count[0] / float(steps)))
        if count[0] < steps:
            root.after(tick_ms, tick)
        elif done:
            done()
    tick()


def duck_audio(state, root, ms=DUCK_MS):
    """Hibernate: fade every playing audio track out and pause it. Returns how many. unduck_audio() brings them
    back from the same spot."""
    players = [p for p in list(state.audio_players) if p not in _ducked]
    for player in players:
        _ducked.append(player)
        try:
            start = float(player.volume)
        except Exception:
            start = 1.0

        def lower(f, player=player, start=start):
            try:
                player.volume = start * (1 - f)
            except Exception:
                pass

        def pause(player=player):
            try:
                player.pause()
            except Exception:
                pass
        _ramp(root, ms, lower, pause)
    return len(players)


def unduck_audio(state, root, volume, ms=DUCK_MS):
    """Hibernate is over: play the paused tracks again, fading up to `volume`. Returns how many."""
    players = [p for p in _ducked if p in state.audio_players]
    _ducked.clear()
    for player in players:
        try:
            player.volume = 0
            player.play()
        except Exception:
            continue

        def raise_(f, player=player):
            try:
                player.volume = volume * f
            except Exception:
                pass
        _ramp(root, ms, raise_)
    return len(players)


def gated(chance_fn):
    """Wrap a popup chance so it reads 0 while stopped or holding."""
    return lambda: 0 if (_paused or _hold) else chance_fn()


def stop_popups(state):
    """Returns how many popups were closed."""
    global _paused
    _paused = True
    _ducked.clear()
    set_tray_visible(state, False)       # nothing running: no icon in the notification area
    stop_hypno(state)
    stop_hero(state)
    restore_wallpaper(state)
    for player in list(state.audio_players):
        try:
            player.pause()
        except Exception:
            pass
    state.audio_players.clear()
    closed = 0
    for popup in list(state.popups):
        try:
            popup.close()
            closed += 1
        except Exception:
            pass        # one stubborn popup must not stop the rest from closing
    return closed


def resume_popups(state=None):
    global _paused
    _paused = False
    set_tray_visible(state, True)
    changer = getattr(state, "ae_wallpaper", None)
    if changer is not None:
        try:
            changer.start()      # saves the wallpaper as it is now, then rotation continues
        except Exception:
            pass


def set_tray_visible(state, visible):
    """Hide or show the tray icon without ending it (Stop / Panic / Pause hide it; Run shows it again).
    Never raises, and does nothing once the tray has been stopped for good."""
    tray = getattr(state, "tray", None)
    if tray is None or getattr(state, "ae_tray_stopped", False):
        return
    try:
        tray.visible = bool(visible)
    except Exception:
        pass


def stop_hypno(state, final=False):
    """Take down the Hypno spiral and beats. final=True when the program is ending (no more ticks)."""
    hypno = getattr(state, "ae_hypno", None)
    if hypno is not None:
        try:
            hypno.shutdown() if final else hypno.teardown()
        except Exception:
            pass


def stop_hero(state, final=False):
    """Take down the Hero bar. final=True when the program is ending."""
    hero = getattr(state, "ae_hero", None)
    if hero is not None:
        try:
            hero.shutdown() if final else hero.teardown()
        except Exception:
            pass


def stop_tray(state):
    """Remove the tray (notification area) icon. Windows leaves a dead icon behind when a program ends without
    removing its own, so every exit path calls this. Safe to call more than once. Not used by Panic itself:
    Edgeware's own panic() already stops the tray, and a second stop there could break it."""
    tray = getattr(state, "tray", None)
    if tray is None or getattr(state, "ae_tray_stopped", False):
        return
    state.ae_tray_stopped = True
    for step in (lambda: setattr(tray, "visible", False), tray.stop):
        try:
            step()
        except Exception:
            pass


def stop_keyboard(state):
    """End Edgeware's global-hotkey helper process. Left running, it (and the thread that listens to it)
    keeps the program alive after the window closes."""
    proc = getattr(state, "keyboard_process", None)
    if proc is None:
        return
    for step in (proc.terminate, lambda: proc.join(1), lambda: proc.is_alive() and proc.kill()):
        try:
            step()
        except Exception:
            pass


def shutdown(state, force_after=3.0, exit_fn=None):
    """Everything that could outlive the window: popups and their video players, the tray icon, the hotkey
    helper. Then a guard: if the program has not ended `force_after` seconds later, it is ended outright."""
    for step in (lambda: stop_popups(state), lambda: stop_tray(state), lambda: stop_keyboard(state)):
        try:
            step()
        except Exception:
            pass
    import os
    import threading
    timer = threading.Timer(force_after, exit_fn or (lambda: os._exit(0)))
    timer.daemon = True
    timer.start()
    return timer


def restore_wallpaper(state):
    """Put the user's own wallpaper back (no-op when the wallpaper feature is off or already restored)."""
    changer = getattr(state, "ae_wallpaper", None)
    if changer is not None:
        try:
            changer.stop()
        except Exception:
            pass


def is_paused():
    return _paused


def make_embedded_panic(on_stop=None):
    """Panic for when the engine lives inside the Autoedgeware window: stop popups and audio but keep
    the window (Edgeware's own panic ends by destroying the root, which would close the whole app).
    Same call signature as Edgeware's panic(root, settings, state, condition, disable)."""
    def embedded_panic(root, settings, state, condition=True, disable=True):
        if not condition:
            return
        stop_popups(state)
        if on_stop:
            try:
                on_stop()
            except Exception:
                pass
    return embedded_panic
