import os, sys, time, requests, traceback, socket, json
LOG = r"C:\T18\logs\probe.log"
os.makedirs(r"C:\T18\logs", exist_ok=True)
def log(s): 
    with open(LOG,"a",encoding="utf-8") as f: f.write(s+"\n")
log("=== PROBE START ===")
log("python: " + sys.executable)
log("T18_NOTION_TOKEN set? " + ("YES" if os.environ.get("T18_NOTION_TOKEN") else "NO"))
try:
    r = requests.get("https://api.notion.com/v1/", timeout=15)
    log(f"GET /v1/ -> {r.status_code}")
except Exception as e:
    log("ERROR GET /v1/: " + repr(e))
    log(traceback.format_exc())
# Try a DB query (structure-only; will 401/403 if token missing, *that’s fine*)
DB="275e38d133c781498421d9b4321e56c8"
hdrs={"Authorization":"Bearer "+(os.environ.get("T18_NOTION_TOKEN") or "MISSING"),
      "Notion-Version":"2022-06-28","Content-Type":"application/json"}
try:
    r = requests.post(f"https://api.notion.com/v1/databases/{DB}/query", headers=hdrs, data="{}", timeout=20)
    log(f"POST /databases/.../query -> {r.status_code}")
    log("Resp head: " + json.dumps(dict(r.headers)))
    log("Resp body: " + r.text[:400])
except Exception as e:
    log("ERROR POST query: " + repr(e))
    log(traceback.format_exc())
log("=== PROBE END ===")
