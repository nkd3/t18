# Finds your watcher (the one that uses build_props(...)) and patches it
# to set a Notion checkbox ("prop_git_tracked" from watcher_config.ini)
# Usage:
#   C:\T18\.venv\Scripts\python.exe C:\T18\ops\patch_git_tracked.py

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\T18")
OPS  = ROOT / "ops"

def find_watcher():
    # Prefer the file you actually run
    primary = OPS / "notion_git_watcher.pyw"
    if primary.exists():
        return primary

    # Otherwise, search for something that calls build_props(...)
    candidates = list(OPS.glob("*.py")) + list(OPS.glob("*.pyw")) + list(ROOT.glob("*.py")) + list(ROOT.glob("*.pyw"))
    hits = []
    for f in candidates:
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "build_props(" in t:
            hits.append(f)
    if hits:
        # Pick the one in ops/ if present, else the first hit
        for h in hits:
            if str(h).lower().startswith(str(OPS).lower()):
                return h
        return hits[0]
    return None

def patch_text(text: str) -> str:
    # 1) Add helper only once
    if "def build_props_with_git(" not in text:
        helper = r"""
def build_props_with_git(p, title_prop, optmap):
    # Wraps build_props(...) and injects a checkbox for "git tracked" if configured
    import subprocess, configparser
    from pathlib import Path

    props = build_props(p, title_prop, optmap)

    ini = r"C:\T18\ops\watcher_config.ini"
    cfg = configparser.ConfigParser()
    try:
        cfg.read(ini, encoding="utf-8")
    except Exception:
        return props

    prop_name = cfg.get("notion", "prop_git_tracked", fallback="").strip()
    if not prop_name:
        return props

    repo_dir = cfg.get("github", "repo_dir", fallback=str(Path(p).anchor)).strip()
    if not repo_dir:
        repo_dir = str(Path(p).anchor)

    tracked = False
    try:
        repo_dir_path = Path(repo_dir).resolve()
        p_path = Path(p).resolve()
        rel = p_path.relative_to(repo_dir_path)

        # Exit code: 0 => tracked, nonzero => untracked
        completed = subprocess.run(
            ["git", "-C", str(repo_dir_path), "ls-files", "--error-unmatch", str(rel)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
        tracked = (completed.returncode == 0)
    except Exception:
        tracked = False

    props[prop_name] = {"checkbox": bool(tracked)}
    return props
"""
        text += "\n" + helper

    # 2) Replace any "properties": build_props(...) with our wrapper
    text = text.replace(
        '"properties": build_props(p,title_prop,optmap),',
        '"properties": build_props_with_git(p,title_prop,optmap),'
    )
    text = re.sub(
        r'"properties":\s*build_props\(\s*p\s*,\s*title_prop\s*,\s*optmap\s*\)\s*,',
        '"properties": build_props_with_git(p,title_prop,optmap),',
        text
    )

    return text

def main():
    watcher = find_watcher()
    if not watcher:
        print("Could not find a watcher file that calls build_props(...).", file=sys.stderr)
        sys.exit(1)

    original = watcher.read_text(encoding="utf-8")
    patched  = patch_text(original)

    if patched == original:
        print(f"No changes made (already patched?) -> {watcher}")
    else:
        watcher.write_text(patched, encoding="utf-8")
        print(f"Patched: {watcher}")

if __name__ == "__main__":
    main()
