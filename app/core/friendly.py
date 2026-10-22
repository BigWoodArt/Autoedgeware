"""Turns raw log lines into one plain sentence for the status bar. The raw line always stays in the
Log tab. Returns None for lines that need no attention."""
_RULES = [
    ("rate limited", "A site is asking us to slow down. Waiting a bit; other sites keep going."),
    ("429", "A site is asking us to slow down. Waiting a bit; other sites keep going."),
    ("falling back to html scrape", "A site's search is down. Reading its web pages instead."),
    ("failed during startup", "Part of the popup engine failed to start. Details are in the Log tab."),
    ("could not start the popup engine", "Popups could not start. Details are in the Log tab."),
    ("no results", "A search found nothing. Check the spelling of the tag or subreddit."),
    ("guest token", "RedGifs would not let us in right now. Try again in a while."),
    ("error page", "A site sent an error page instead of a file. Skipped it."),
    ("request failed", "A site is not answering right now. It will be retried on the next pass."),
    ("timed out", "A site is slow to answer. It will be retried on the next pass."),
]


def friendly(msg, level="info"):
    if level not in ("warning", "error"):
        return None
    low = (msg or "").lower()
    for needle, text in _RULES:
        if needle in low:
            return text
    return "Some downloads had trouble. Details are in the Log tab."
