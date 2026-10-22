"""Compare shared scraper files with sources/MANIFEST.json (line endings ignored); --manifest regenerates it. Exit 0 = identical."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_FILES = ["core/netlog.py", "core/thumbs.py", "core/query_clean.py", "core/media_item.py", "core/winproc.py", "core/safety.py"]


def shared_files():
    files = sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "sources").glob("*.py"))
    return files + [f for f in CORE_FILES if (ROOT / f).exists()]


def digest(rel):
    data = (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:16]


def version():
    for line in (ROOT / "sources" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("SOURCES_VERSION"):
            return line.split("=", 1)[1].split("#")[0].strip().strip("\"'")
    return "unknown"


def main():
    manifest_path = ROOT / "sources" / "MANIFEST.json"
    if "--manifest" in sys.argv:
        data = {"sources_version": version(), "files": {f: digest(f) for f in shared_files()}}
        manifest_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"wrote {manifest_path.name}: {len(data['files'])} files, version {data['sources_version']}")
        return 0
    canon = json.loads(manifest_path.read_text(encoding="utf-8"))
    mine = {f: digest(f) for f in shared_files()}
    bad = []
    for f, h in canon["files"].items():
        if f not in mine:
            print(f"MISSING  {f}"); bad.append(f)
        elif mine[f] != h:
            print(f"DIFFERS  {f}"); bad.append(f)
    for f in mine:
        if f not in canon["files"]:
            print(f"EXTRA    {f}  (not in canonical set)")
    total = len(canon["files"])
    print(f"SOURCES canonical {canon['sources_version']} (this project reports {version()}): "
          f"{total - len(bad)}/{total} files match" + (f"; differ/missing: {', '.join(bad)}" if bad else " - IDENTICAL"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
