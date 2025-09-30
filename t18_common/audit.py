# C:\T18\t18_common\audit.py
import os, sqlite3, time, json
from pathlib import Path

ROOT = Path(r"C:\T18")
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "t18.db"))

def _db():
    return sqlite3.connect(DB_PATH)

def log(actor_username:str|None, scope:str, action:str, target:str|None=None, meta:dict|None=None):
    with _db() as con:
        cur = con.cursor()
        cur.execute("""INSERT INTO audit_log(ts,actor_username,scope,action,target,meta_json)
                       VALUES (?,?,?,?,?,?)""",
                    (int(time.time()), actor_username, scope, action, target,
                     json.dumps(meta or {}, ensure_ascii=False)))
        con.commit()
