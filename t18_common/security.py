# C:\T18\t18_common\security.py
import re, time, os, sqlite3, secrets, json
from pathlib import Path
from passlib.hash import bcrypt

ROOT = Path(r"C:\T18")
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "t18.db"))

def _db():
    return sqlite3.connect(DB_PATH)

def hash_password(plain: str) -> str:
    return bcrypt.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(plain, hashed)
    except Exception:
        return False

def get_policy(conn):
    cur = conn.cursor()
    cur.execute("SELECT min_length,require_upper,require_lower,require_digit,require_symbol,blocklist_on,history_N,expiry_days,lockout_thresh,lockout_secs FROM password_policy WHERE id=1")
    row = cur.fetchone()
    if not row:
        return dict(min_length=12, require_upper=1, require_lower=1, require_digit=1, require_symbol=1,
                    blocklist_on=1, history_N=5, expiry_days=90, lockout_thresh=5, lockout_secs=900)
    keys = ["min_length","require_upper","require_lower","require_digit","require_symbol","blocklist_on","history_N","expiry_days","lockout_thresh","lockout_secs"]
    return dict(zip(keys, row))

def validate_password(conn, user_id:int|None, new_pwd:str) -> dict:
    pol = get_policy(conn)
    problems = []
    if len(new_pwd) < pol["min_length"]:
        problems.append(f"min length {pol['min_length']}")
    if pol["require_upper"] and not re.search(r"[A-Z]", new_pwd):
        problems.append("needs uppercase")
    if pol["require_lower"] and not re.search(r"[a-z]", new_pwd):
        problems.append("needs lowercase")
    if pol["require_digit"] and not re.search(r"[0-9]", new_pwd):
        problems.append("needs digit")
    if pol["require_symbol"] and not re.search(r"[^\w\s]", new_pwd):
        problems.append("needs symbol")

    if pol["blocklist_on"]:
        cur = conn.cursor()
        cur.execute("SELECT phrase FROM password_blocklist")
        bl = {r[0] for r in cur.fetchall()}
        if new_pwd.lower() in bl:
            problems.append("blocked/common password")

    if user_id is not None and pol["history_N"]>0:
        cur = conn.cursor()
        cur.execute("""SELECT password_hash FROM password_history
                       WHERE user_id=? ORDER BY changed_ts DESC LIMIT ?""", (user_id, pol["history_N"]))
        hist = [r[0] for r in cur.fetchall()]
        for h in hist:
            if bcrypt.verify(new_pwd, h):
                problems.append(f"matches last {pol['history_N']} history")
                break

    return {"ok": len(problems)==0, "problems": problems, "policy": pol}

def record_password_history(conn, user_id:int, new_hash:str):
    cur = conn.cursor()
    cur.execute("INSERT INTO password_history(user_id,password_hash,changed_ts) VALUES (?,?,?)",
                (user_id,new_hash,int(time.time())))
    conn.commit()

def list_role_caps(conn, role:str)->set:
    cur = conn.cursor()
    cur.execute("SELECT capability FROM role_permissions WHERE role=?", (role,))
    return {r[0] for r in cur.fetchall()}

def ensure_not_last_admin(conn, target_user_id:int)->None:
    cur = conn.cursor()
    cur.execute("SELECT role, deleted_ts FROM users WHERE user_id=?", (target_user_id,))
    row = cur.fetchone()
    if not row: return
    role, deleted_ts = row
    if role != "Admin": return
    # how many active admins remain if this one is removed/demoted?
    cur.execute("SELECT COUNT(*) FROM users WHERE role='Admin' AND deleted_ts IS NULL AND active=1 AND user_id<>?", (target_user_id,))
    remaining = cur.fetchone()[0]
    if remaining == 0:
        raise RuntimeError("Safety: cannot remove/demote the last Admin.")

def redact(d:dict, keys=("password","password_hash","totp_secret","recovery_json")):
    dd = dict(d)
    for k in keys:
        if k in dd: dd[k] = "***"
    return dd
