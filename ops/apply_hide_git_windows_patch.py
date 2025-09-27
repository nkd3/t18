from pathlib import Path
import re

# Find the watcher
watcher = Path(r"C:\T18\ops\notion_git_watcher.pyw")
if not watcher.exists():
    watcher = Path(r"C:\T18\ops\notion_git_watcher.py")
if not watcher.exists():
    raise SystemExit("Watcher file not found in C:\\T18\\ops")

text = watcher.read_text(encoding="utf-8")
bak  = watcher.with_suffix(watcher.suffix + ".bak_hidegit_" + __import__("time").strftime("%Y%m%d%H%M%S"))
bak.write_text(text, encoding="utf-8")

changed = False

# 1) Make sure we can import our helper
if "from ops._silent_git import _run_silent, _GIT" not in text and \
   "from _silent_git import _run_silent, _GIT" not in text:
    # Try a graceful insertion after the first import block
    if "import " in text:
        text = re.sub(
            r"(^import[^\n]*\n(?:import[^\n]*\n|from[^\n]*\n)*)",
            r"\1from ops._silent_git import _run_silent, _GIT\n",
            text, count=1, flags=re.M
        )
    else:
        text = "from ops._silent_git import _run_silent, _GIT\n" + text
    changed = True

# 2) Replace any direct git invocations to call git.exe explicitly
new_text = re.sub(r'(\[)\s*[\'"]git[\'"]\s*,', r'\1 _GIT,', text)
if new_text != text:
    text = new_text
    changed = True

# 3) Route subprocess.run(...) through _run_silent(...)
#    (Scoped replace: only if the code actually uses subprocess.run)
if "subprocess.run(" in text and "_run_silent(" not in text:
    text = text.replace("subprocess.run(", "_run_silent(")
    changed = True

if changed:
    watcher.write_text(text, encoding="utf-8")
    print("Patched:", watcher)
else:
    print("No changes needed:", watcher)
