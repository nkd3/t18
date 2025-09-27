# Patch the watcher to set a Notion checkbox (prop_git_tracked) based on git tracking
# Save as: C:\T18\ops\notion_watcher_patch_gittracked.py
# Run once with your venv's python:  C:\T18\.venv\Scripts\python.exe C:\T18\ops\notion_watcher_patch_gittracked.py

from pathlib import Path
import re

WATCHER = Path(r"C:\T18\ops\notion_watcher.py")
text = WATCHER.read_text(encoding="utf-8")

# 1) Add our helper function only once
if "def build_props_with_git(" not in text:
    helper = r"""
def build_props_with_git(p, title_prop, optmap):
    """
    helper += r"""# Wraps build_props(...) and injects a checkbox for "git tracked" if configured in watcher_config.ini
    import subprocess, os
    from pathlib import Path
    import configparser

    # Start with existing props
    props = build_props(p, title_prop, optmap)

    # Read config to find checkbox name + repo dir
    ini = r"C:\T18\ops\watcher_config.ini"
    cfg = configparser.ConfigParser()
    try:
        cfg.read(ini, encoding="utf-8")
    except Exception:
        return props

    prop_name = cfg.get("notion", "prop_git_tracked", fallback="").strip()
    if not prop_name:
        return props  # nothing to do if not configured

    repo_dir = cfg.get("github", "repo_dir", fallback=str(Path(p).anchor)).strip() or str(Path(p).anchor)

    # Determine if file is tracked by git
    tracked = False
    try:
        repo_dir_path = Path(repo_dir).resolve()
        p_path = Path(p).resolve()
        # If p is outside repo_dir, relative_to will fail
        rel = p_path.relative_to(repo_dir_path)

        # Prefer a git on PATH (your start_watcher.cmd sets PATH for SYSTEM)
        # Exit code 0 => tracked, nonzero => untracked
        completed = subprocess.run(
            ["git", "-C", str(repo_dir_path), "ls-files", "--error-unmatch", str(rel)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)  # hide console if on pythonw
        )
        tracked = (completed.returncode == 0)
    except Exception:
        tracked = False

    # Inject/overwrite the checkbox
    props[prop_name] = {"checkbox": bool(tracked)}
    return props
"""
    text += "\n" + helper

# 2) In both create_page(...) and update_page(...), replace:
#       "properties": build_props(p,title_prop,optmap),
#    with:
#       "properties": build_props_with_git(p,title_prop,optmap),
text = text.replace(
    '"properties": build_props(p,title_prop,optmap),',
    '"properties": build_props_with_git(p,title_prop,optmap),'
)

# Some variants may have spaces after commas; patch those too
text = re.sub(
    r'"properties":\s*build_props\(\s*p\s*,\s*title_prop\s*,\s*optmap\s*\)\s*,',
    '"properties": build_props_with_git(p,title_prop,optmap),',
    text
)

WATCHER.write_text(text, encoding="utf-8")
print("Patched Notion watcher to set the Git Tracked checkbox.")
