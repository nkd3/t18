from pathlib import Path
import re

p = Path(r"C:\T18\ops\notion_git_watcher.pyw")
if not p.exists():
    p = Path(r"C:\T18\ops\notion_git_watcher.py")
text = p.read_text(encoding="utf-8")

# Ensure we import subprocess/os where needed
if "import subprocess" not in text:
    text = "import subprocess\n" + text
if "import os" not in text:
    text = "import os\n" + text

# Insert/replace the silent-subprocess shim with a hardened one
shim = r"""
# --- silent-subprocess shim (hardened: hide + detach + non-interactive git) ---
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
DETACHED_PROCESS = 0x00000008
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
SW_HIDE = 0

def _run_silent(cmd:list[str], cwd=None, env=None):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    flags = CREATE_NO_WINDOW | DETACHED_PROCESS
    e = os.environ.copy()
    if env:
        e.update(env)
    # kill *all* git UI/interaction every time:
    e.setdefault("GIT_TERMINAL_PROMPT", "0")
    e.setdefault("GCM_INTERACTIVE", "Never")
    e.setdefault("GIT_ASKPASS", "echo")
    e.setdefault("SSH_ASKPASS", "echo")
    e.setdefault("GIT_PAGER", "cat")
    return subprocess.run(cmd, cwd=cwd, env=e, startupinfo=si, creationflags=flags,
                          shell=False, capture_output=True, text=True)

# Resolve git.exe once, avoid git.cmd shim
_GIT = r"C:\Program Files\Git\bin\git.exe"
if not os.path.exists(_GIT):
    _GIT = r"C:\Program Files (x86)\Git\bin\git.exe"
"""

if "silent-subprocess shim" in text:
    # Replace existing shim block (simple approach: replace up to next two blank lines)
    text = re.sub(r"# --- silent-subprocess shim.*?(\n\n|\Z)", shim + "\n\n", text, flags=re.S)
else:
    text = shim + "\n" + text

# Replace every place that calls git to use _GIT and _run_silent
# Examples: ["git","status"...] or ('git', 'pull'...)
text = re.sub(r"""(\[)["']git["']\s*,\s*""", r"\1_GIT, ", text)
text = text.replace("subprocess.run(", "_run_silent(")

p.write_text(text, encoding="utf-8")
print("Hardened shim applied to", p)
