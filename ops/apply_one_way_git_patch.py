import re, time, os
from pathlib import Path

watcher = Path(r"C:\\T18\\ops\\notion_git_watcher.pyw")
text = watcher.read_text(encoding="utf-8")
bak  = watcher.with_suffix(watcher.suffix + ".bak_oneway_" + time.strftime("%Y%m%d%H%M%S"))
bak.write_text(text, encoding="utf-8")

changed = False

# a) ensure hidden git helper import
if ("from ops._silent_git import _run_silent, _GIT" not in text) and ("from _silent_git import _run_silent, _GIT" not in text):
    m = re.search(r'^(?:import[^\n]*\n|from[^\n]*\n)+', text, flags=re.M)
    if m:
        text = text[:m.end()] + "from ops._silent_git import _run_silent, _GIT\n" + text[m.end():]
    else:
        text = "from ops._silent_git import _run_silent, _GIT\n" + text
    changed = True

# b) replace ['git', ...] -> [_GIT, ...] using a lambda (so no escapes in repl)
pat_git_list = re.compile(r'(\[)\s*([\'"])git\2\s*,')
text2 = pat_git_list.sub(lambda m: m.group(1) + " _GIT,", text)
if text2 != text:
    text = text2
    changed = True

# c) subprocess.run(...) -> _run_silent(...)
if "subprocess.run(" in text:
    text = text.replace("subprocess.run(", "_run_silent(")
    changed = True

# d) comment out any lines that perform fetch/pull (list or string invocations)
verbs = ("fetch","pull")
lines = text.splitlines(True)
out = []
for ln in lines:
    low = ln.lower()
    if ("git" in low or "_git" in low) and any(v in low for v in verbs):
        if not low.lstrip().startswith(("#","'''",'\"\"\"')):
            out.append("# [one-way] removed: " + ln)
            changed = True
            continue
    out.append(ln)
text = "".join(out)

# e) make push quiet if present (best-effort)
def ensure_flags(lst_text):
    # only add if not already there
    if "--quiet" in lst_text or "--porcelain" in lst_text:
        return lst_text
    return lst_text.replace("push", "push --quiet --porcelain", 1)

text = re.sub(r'(\[_GIT\s*,[^\]]*\bpush\b[^\]]*\])', lambda m: ensure_flags(m.group(1)), text)

# f) force non-interactive env if code builds env
if "GIT_TERMINAL_PROMPT" not in text and "env = os.environ.copy()" in text:
    text = text.replace(
        "env = os.environ.copy()",
        "env = os.environ.copy(); env.setdefault('GIT_TERMINAL_PROMPT','0'); env.setdefault('GCM_INTERACTIVE','Never'); env.setdefault('GIT_ASKPASS','echo'); env.setdefault('SSH_ASKPASS','echo'); env.setdefault('GIT_PAGER','cat')"
    )

watcher.write_text(text, encoding="utf-8")
print("Patched for one-way:", watcher)
