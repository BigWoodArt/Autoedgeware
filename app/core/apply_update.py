"""Copies an unpacked update over the install, then reopens run.bat.

Standalone on purpose (standard library only): it runs in its own process after the app has closed, from a
temporary folder, so it can overwrite the app's own files.

usage: apply_update.py <pid of the app> <unpacked repo folder> <install folder (holds run.bat and app\\)>

Never deleted or overwritten: the user's settings, presets, media folder and setup marker. Files are only added or
replaced, never removed."""
import os
import shutil
import subprocess
import sys
import time

KEEP_FILES = {"settings.json", "presets.json", ".setup_ok", "blacklist.json"}
KEEP_DIRS = {"media", "blacklist", "logs", "__pycache__", ".git", ".github"}
LAST = {"run.bat"}                     # copied last: the launcher may still be finishing


def wait_for_exit(pid, seconds=60):
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
            if handle:
                ctypes.windll.kernel32.WaitForSingleObject(handle, int(seconds * 1000))
                ctypes.windll.kernel32.CloseHandle(handle)
                return
        except Exception:
            pass
    else:
        for _ in range(int(seconds * 4)):
            try:
                os.kill(int(pid), 0)
            except OSError:
                break
            time.sleep(0.25)
    time.sleep(1.0)


def plan(source_root):
    """[(relative path)] of the files to copy, run.bat last."""
    files = []
    for base, dirs, names in os.walk(source_root):
        dirs[:] = [d for d in dirs if d not in KEEP_DIRS]
        for name in names:
            rel = os.path.relpath(os.path.join(base, name), source_root)
            if name in KEEP_FILES or name.startswith(".git"):
                continue
            files.append(rel)
    files.sort(key=lambda r: (os.path.basename(r).lower() in LAST, r))
    return files


def copy_file(src, dst, tries=8):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for i in range(tries):
        try:
            shutil.copyfile(src, dst)
            return True
        except OSError:
            time.sleep(0.5)
    return False


def apply(source_root, install_root, log):
    failed = []
    for rel in plan(source_root):
        if not copy_file(os.path.join(source_root, rel), os.path.join(install_root, rel)):
            failed.append(rel)
            log(f"could not copy {rel}")
    return failed


def main(argv):
    pid, source_root, install_root = argv[1], argv[2], argv[3]
    log_path = os.path.join(install_root, "app", "update.log")

    def log(text):
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + text + "\n")
        except OSError:
            pass

    wait_for_exit(pid)
    log("applying update")
    failed = apply(source_root, install_root, log)
    log("done" if not failed else f"done with {len(failed)} file(s) not copied")
    run_bat = os.path.join(install_root, "run.bat")
    if os.name == "nt" and os.path.isfile(run_bat):
        subprocess.Popen(["cmd", "/c", "start", "", run_bat], cwd=install_root, creationflags=0x08000000)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
