"""Which Edgeware modules hold their own copy of panic() (via `from panic import panic`).
run_engine.py replaces panic in every one of them; tests/test_panic_patch.py checks this list
against the real source, so a new Edgeware module that imports panic cannot be missed."""
PANIC_USERS = ("panic", "features.misc", "features.popup", "scripting.modules")
