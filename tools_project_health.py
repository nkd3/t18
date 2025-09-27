from pathlib import Path
from dotenv import load_dotenv
import os, subprocess, sys

ROOT = Path(r"C:\T18")
assert ROOT.exists(), "Root missing"
load_dotenv(ROOT/".env", override=True)

ok = True
def require(name, cond):
    global ok
    print(f"{name}: {'OK' if cond else 'MISSING'}")
    ok = ok and cond

require(".venv python", (ROOT/".venv/Scripts/python.exe").exists())
require(".env present", (ROOT/".env").exists())
require("NOTION_TOKEN", bool(os.getenv("NOTION_TOKEN")))
require("NOTION_PAGE_ID", bool(os.getenv("NOTION_PAGE_ID")))
require("DB file", (ROOT/"data/t18.db").exists())
require("tools_autodoc_to_notion.py", (ROOT/"tools_autodoc_to_notion.py").exists())
require("tools_watch_and_sync_notion.py", (ROOT/"tools_watch_and_sync_notion.py").exists())

# git status quick
try:
    out = subprocess.check_output(["git","status","--porcelain"], cwd=ROOT, text=True)
    print("git working tree:", "clean" if not out.strip() else "changes present")
except Exception as e:
    print("git status error:", e); ok=False

sys.exit(0 if ok else 1)
