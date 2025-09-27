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

# 1) Ensure our helper import is present
if "from ops._silent_git2 import run_git_hidden" not in src:
    m = re.search(r"(^(\s*)(import|from)\b[^\n]*\n(?:[ \t]*(?:import|from)\b[^\n]*\n)*)", src, flags=re.M)
    if m:
        src = src[:m.end()] + "from ops._silent_git2 import run_git_hidden\n" + src[m.end():]
    else:
        src = "from ops._silent_git2 import run_git_hidden\n" + src
    changed = True

# 2) Replace any subprocess.run([...,"git",...]) calls
pattern1 = re.compile(r"subprocess\.run\(\s*\[(.*?)\](.*?)\)", flags=re.S)
src2 = pattern1.sub(r"run_git_hidden([\1])\2", src)
if src2 != src:
    src = src2
    changed = True

# 3) Replace subprocess.run("git ...") style calls
pattern2 = re.compile(r"subprocess\.run\(\s*([\"'])git.*?\)", flags=re.S)
src2 = pattern2.sub(lambda m: "run_git_hidden(" + m.group(0)[len("subprocess.run("):-1] + ")", src)
if src2 != src:
    src = src2
    changed = True

# 4) Replace check_output/check_call([...,"git",...])
pattern3 = re.compile(r"subprocess\.(check_output|check_call)\(\s*\[(.*?)\](.*?)\)", flags=re.S)
src2 = pattern3.sub(r"run_git_hidden([\2])\3", src)
if src2 != src:
    src = src2
    changed = True

# 5) Replace os.system("git ...")
pattern4 = re.compile(r"os\.system\(\s*([\"'])git\s")
src2 = pattern4.sub(r"run_git_hidden(\1git ", src)
if src2 != src:
    src = src2
    changed = True

if changed:
    w.write_text(src, encoding="utf-8")
    print("Patched:", w)
else:
    print("No changes needed:", w)
