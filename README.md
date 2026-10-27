# Autoedgeware

Pick a few keywords and sites. Autoedgeware downloads matching media in the background and pops it on your screen as images, videos and sound. It uses Edgeware++'s popup engine, and everything is included in this download.

## Start (Windows)

1. Download and unzip.
2. Double-click **`run.bat`**. The first time it sets itself up (a few minutes).
3. Tell the window what you want to see, press **Run**.

That's it. Next time, just double-click `run.bat`.

## Stopping

- **Stop** button in the window, or press **Esc**.
- The tray icon has a **Panic** button too.
- Stop and Panic put your desktop wallpaper back.

## Good to know

- **Presets** are your keyword and site lists. The Preset Finder suggests tags and subreddits from one word. Share presets with Import / Export.
- **Hypno mode** (checkbox on the Main tab): a faint black-and-white spiral and binaural beats (headphones). Faster popups make it stronger.
- **Hero mode** (checkbox on the Main tab): a beat bar along the bottom of the screen. Circles meet a ring, it flashes green and clicks, and popups follow the rhythm (speeding up, slowing down, holding, a non-stop Frenzy). Nothing is recorded; just follow along if you like.
- **Intensity** goes from a slight annoyance up to maximum. Choose **Custom** on the Main tab (values live on the Popups tab) to set every value yourself.
- **Popups tab:** custom intensity, sound volumes, auto-close, fullscreen videos. **Modes:** Hero settings, Hibernate, wallpaper changer. **Downloads:** file limits, smallest picture, video trimming, scrape timing. **Advanced:** startup options and optional site keys (Wallhaven, Gelbooru).
- **Updates:** at startup the window checks GitHub. If there is a newer version an **Update** button shows at the top; one click installs it and restarts. Your presets, settings and downloads are kept. Turn the check off under Advanced.
- Downloads and settings are kept in the `app` folder.
- Needs Windows with Python 3.12 or newer. `run.bat` installs what is missing.

Sources: Reddit, RedGifs, Erome, Hypnotube, PMVHaven, Soundgasm, Freesound, Coomer, Fapello, Kemono, Lemmy, Civitai, Wallhaven, Derpibooru, Gelbooru, RealBooru, HypnoHub, Rule34, Safebooru, TBIB, Xbooru, e621, Danbooru, Yande.re, Konachan.

Contains unmodified Edgeware++ code (GPL-3.0, see `app/edgeware_core/COPYING`).

## Changelog

- **0.25** — New gallery sources: Pictoa, EliteBabes, PornGIF, Pornhub Photos and GIFs.
- **0.24** — Monitors: choose which screens popups, fullscreen videos, the spiral and Hero use (Popups tab). Default is all.
- **0.23.4** — Advanced > Network: optional "Skip certificate checks" (off by default; only on a trusted network).
- **0.23.3** — Fixes "certificate has expired" download errors on PCs with an old certificate store (also trusts certifi's list; checking stays on). Rule34 now has API key and user ID fields (Advanced > Site keys).
- **0.23.2** — Save now applies to running popups at once (popup timing, auto-close, chances, volumes); no restart needed.
- **0.23** — Update check: a button appears when GitHub has a newer version; one click downloads it, installs it and restarts.
- **0.22** — Starts with a safe "Nature" preset; first-run window; dialogs centred. Freesound fixed (needs a key).
- **0.21** — Settings reorganised (Main, Popups, Modes, Downloads, Advanced, Log). "Wait before popups start" works.
- **0.20** — New sites PornPics and Babehub; Preset Finder lists every searchable site.
- **0.19** — Hypno spiral: sharper, faster, stays above fullscreen video. Download limits count per preset. Random first wallpaper.
- **0.18** — New look; Reddit albums; Redgifs niches; clean shutdown; source name in file names.
- **0.17** — Scrapers updated; `media` folder beside `run.bat`.
- **0.16** — Hypnotube and PMVHaven.
- **0.15 and earlier** — Hero mode, Hypno mode, Preset Finder, quality levels, tabbed window, wallpaper changer, many sources.
