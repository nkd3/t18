from pathlib import Path
import re, time

WATCHER = Path(r"C:\T18\ops\notion_git_watcher.pyw")
if not WATCHER.exists():
    WATCHER = Path(r"C:\T18\ops\notion_git_watcher.py")
if not WATCHER.exists():
    raise SystemExit("Watcher file not found in C:\\T18\\ops")

text = WATCHER.read_text(encoding="utf-8")
bak  = WATCHER.with_suffix(WATCHER.suffix + ".bak_norm_" + time.strftime("%Y%m%d%H%M%S"))
bak.write_text(text, encoding="utf-8")

changed = False

# 0) Ensure our helper import is present
if "from ops._silent_git import _run_silent, _GIT" not in text and "from _silent_git import _run_silent, _GIT" not in text:
    # insert after the first import block
    m = re.search(r"(^(\s*)(import|from)\b[^\n]*\n(?:[ \t]*(?:import|from)\b[^\n]*\n)*)", text, flags=re.M)
    inject = "from ops._silent_git import _run_silent, _GIT\n"
    if m:
        text = text[:m.end()] + inject + text[m.end():]
    else:
        text = inject + text
    changed = True

# 1) Collapse any 'from subprocess import ...' to 'import subprocess'
pattern = re.compile(r"^\s*from\s+subprocess\s+import\s+.*$", flags=re.M)
if pattern.search(text):
    text = pattern.sub("import subprocess", text)
    changed = True

# 2) Replace any uses of git as first token with _GIT (list-literal form)
#    e.g. ["git", "status"] -> [_GIT, "status"]
text2 = re.sub(r"(\[)\s*[\"']git[\"']\s*,", r"\1 _GIT,", text)
if text2 != text:
    text = text2
    changed = True

# 3) Route common subprocess entry points to _run_silent(
#    We only rewrite *bare* names; fully-qualified (subprocess.run) we convert too.
replacements = [
    (r"(?<!\.)\brun\s*\(", "_run_silent("),
    (r"(?<!\.)\bPopen\s*\(", "_run_silent("),
    (r"(?<!\.)\bcheck_output\s*\(", "_run_silent("),
    (r"(?<!\.)\bcheck_call\s*\(", "_run_silent("),
    (r"(?<!\.)\bcall\s*\(", "_run_silent("),
    (r"\bsubprocess\.run\s*\(", "_run_silent("),
    (r"\bsubprocess\.Popen\s*\(", "_run_silent("),
    (r"\bsubprocess\.check_output\s*\(", "_run_silent("),
    (r"\bsubprocess\.check_call\s*\(", "_run_silent("),
    (r"\bsubprocess\.call\s*\(", "_run_silent("),
]

for pat, repl in replacements:
    new_text = re.sub(pat, repl, text)
    if new_text != text:
        text = new_text
        changed = True

if changed:
    WATCHER.write_text(text, encoding="utf-8")
    print("Normalized subprocess + git calls in", WATCHER)
else:
    print("No changes needed:", WATCHER)
