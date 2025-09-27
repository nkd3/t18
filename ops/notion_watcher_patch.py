# --- PATCH: broaden file watching + safe body for text files only ---
# Drop this into: C:\T18\ops\notion_watcher_patch.py and run it once

from pathlib import Path
p = Path(r"C:\T18\ops\notion_watcher.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    "def iter_txt():\n    for p in ROOT.glob(\"*.txt\"):\n        if p.is_file(): yield p\n",
    "def iter_txt():\n"
    "    exts = {'.txt','.md','.markdown','.log','.py','.ps1','.bat','.cmd','.json','.yaml','.yml',\n"
    "            '.pptx','.ppt','.docx','.xlsx','.pdf'}\n"
    "    for p in ROOT.iterdir():\n"
    "        if p.is_file() and p.suffix.lower() in exts:\n"
    "            yield p\n"
)

s = s.replace(
    "def create_page(p: Path, db_id: str, title_prop: str, optmap: dict):\n"
    "    try:\n"
    "        try: body = p.read_text(encoding=\"utf-8\", errors=\"ignore\")\n"
    "        except Exception: body = \"\"\n"
    "        data = {\"parent\":{\"database_id\":db_id},\n"
    "                \"properties\": build_props(p,title_prop,optmap),\n"
    "                \"children\": to_children(body)}\n",
    "def create_page(p: Path, db_id: str, title_prop: str, optmap: dict):\n"
    "    try:\n"
    "        text_exts = {'.txt','.md','.markdown','.log','.json','.yaml','.yml','.py','.ps1','.bat','.cmd'}\n"
    "        if p.suffix.lower() in text_exts:\n"
    "            try: body = p.read_text(encoding='utf-8', errors='ignore')\n"
    "            except Exception: body = ''\n"
    "            children = to_children(body)\n"
    "        else:\n"
    "            note = f\"Binary file: {p.name} (size {p.stat().st_size} bytes). Contents not uploaded.\"\n"
    "            children = to_children(note)\n"
    "        data = {\"parent\":{\"database_id\":db_id},\n"
    "                \"properties\": build_props(p,title_prop,optmap),\n"
    "                \"children\": children}\n"
)

p.write_text(s, encoding="utf-8")
print("Patched C:\\T18\\ops\\notion_watcher.py")
