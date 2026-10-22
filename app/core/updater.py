"""Update check against the GitHub repo, and the download step. No Tk here, so it can be tested.

Flow: fetch_remote_version() reads app/VERSION from the main branch. If it is newer, download_and_prepare()
downloads the repo zip and unpacks it, then launch_helper() starts apply_update.py (a separate process, because
the running program cannot overwrite its own files) and the window closes. The helper copies the files and
reopens run.bat."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPO = "BigWoodArt/Autoedgeware"
BRANCH = "main"
VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/app/VERSION"
ZIP_URL = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"
HERE = os.path.dirname(os.path.abspath(__file__))


def parse_version(text):
    """'v0.22.4' -> (0, 22, 4); None when it is not a version."""
    m = re.fullmatch(r"\s*v?(\d+)\.(\d+)\.(\d+)\s*", str(text or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(remote, local):
    r, l = parse_version(remote), parse_version(local)
    return bool(r and l and r > l)


def _get(url, timeout, opener=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Autoedgeware-updater"})
    with (opener or urllib.request.urlopen)(req, timeout=timeout) as resp:
        return resp.read()


def fetch_remote_version(timeout=6, opener=None):
    """The newest version text on GitHub, or None when offline or unreadable."""
    try:
        text = _get(VERSION_URL, timeout, opener).decode("utf-8", "replace").strip()
    except Exception:
        return None
    return text if parse_version(text) else None


def check(local_version, timeout=6, opener=None):
    """The newer version text if there is one, else None."""
    remote = fetch_remote_version(timeout, opener)
    return remote if remote and is_newer(remote, local_version) else None


def find_source_root(folder):
    """The unpacked repo folder (it holds app/VERSION and app/run_engine.py), or None."""
    for base, dirs, _files in os.walk(folder):
        if os.path.isfile(os.path.join(base, "app", "VERSION")) and os.path.isfile(os.path.join(base, "app", "run_engine.py")):
            return base
        if base.count(os.sep) - folder.count(os.sep) >= 2:
            dirs[:] = []
    return None


def download_and_prepare(work_dir=None, timeout=60, opener=None):
    """Downloads and unpacks the repo zip. Returns (source_root, work_dir). Raises RuntimeError on a bad zip."""
    work_dir = work_dir or tempfile.mkdtemp(prefix="autoedgeware_update_")
    zip_path = os.path.join(work_dir, "update.zip")
    with open(zip_path, "wb") as f:
        f.write(_get(ZIP_URL, timeout, opener))
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(os.path.join(work_dir, "x"))
    except zipfile.BadZipFile as ex:
        raise RuntimeError(f"the download was not a valid zip ({ex})")
    root = find_source_root(os.path.join(work_dir, "x"))
    if not root:
        raise RuntimeError("the download does not look like Autoedgeware")
    return root, work_dir


def launch_helper(source_root, install_root, work_dir, pid=None):
    """Starts apply_update.py in its own process. The caller then closes the window."""
    helper = os.path.join(work_dir, "apply_update.py")
    shutil.copyfile(os.path.join(HERE, "apply_update.py"), helper)
    args = [sys.executable, helper, str(pid or os.getpid()), source_root, install_root]
    flags = 0x08000000 | 0x00000008 if os.name == "nt" else 0       # no console window, detached
    return subprocess.Popen(args, cwd=work_dir, creationflags=flags)
