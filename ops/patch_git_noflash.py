from pathlib import Path
import re, time

w = Path(r"C:\T18\ops\notion_git_watcher.pyw")
if not w.exists():
    w = Path(r"C:\T18\ops\notion_git_watcher.py")
if not w.exists():
    raise SystemExit("Watcher file not found in C:\\T18\\ops")

src = w.read_text(encoding="utf-8")
bak = w.with_suffix(w.suffix + ".bak_noflash_" + time.strftime("%Y%m%d%H%M%S"))
bak.write_text(src, encoding="utf-8")

changed = False

# 1) Ensure our helper import is present just after the first import block
shim = "\nfrom ops._silent_git2 import run_git_hidden\n"
m = re.search(r"(^(\s*)(import|from)\b[^\n]*\n(?:[ \t]*(?:import|from)\b[^\n]*\n)*)", src, flags=re.M)
if m and "from ops._silent_git2 import run_git_hidden" not in src:
    src = src[:m.end()] + shim + src[m.end():]
    changed = True

# 2) Replace direct git subprocess invocations with run_git_hidden
#    Handle typical patterns your watcher likely uses:
patterns = [
    # subprocess.run([...,"git",...])
    (r"subprocess\.run\(\s*\[(?P<head>[^]]*?)\]\s*(?P<rest>[\),])",
     lambda mo: re.sub(r'([\'"])git(\.exe)?\1', '\"git\"',  # normalize
                       f"run_git_hidden([{mo.group('head')}]){mo.group('rest')}")
    ),
    # subprocess.run("git ...", shell=True/False)
    (r"subprocess\.run\(\s*([\"'])git[^)]*\)", 
     lambda mo: "run_git_hidden(" + mo.group(0)[len("subprocess.run("):-1] + ")"),
    ),
    # check_output([...,"git",...]) or check_call(...)
    (r"subprocess\.(check_output|check_call)\(\s*\[(?P<head>[^]]*?)\]\s*(?P<rest>[\),])",
     lambda mo: re.sub(r'([\'"])git(\.exe)?\1', '\"git\"',
                       f"run_git_hidden([{mo.group('head')}]){mo.group('rest')}")
    ),
]

for pat, repl in patterns:
    new = re.sub(pat, repl, src)
    if new != src:
        src = new
        changed = True

# 3) Best-effort replace common helper wrappers if present (e.g., git_status(), git_pull(), etc.)
src = re.sub(r"\bgit\s+status\b", "git status", src)  # keep text stable
src = re.sub(
    r"def\s+git_(status|pull|push|add|commit|revparse)\s*\([^\)]*\):\s*\n",
    r"\g<0># NOTE: implementation patched to use run_git_hidden\n", src
)

# 4) Prevent any stray os.system("git ...")
src = re.sub(r"os\.system\(\s*([\"'])git\s", r"run_git_hidden(\1git ", src)

if changed:
    w.write_text(src, encoding="utf-8")
    print("Patched:", w)
else:
    print("No changes needed:", w)
