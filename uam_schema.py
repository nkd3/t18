# C:\T18\uam_schema.py
import sqlite3, os, secrets, time, json
from pathlib import Path

ROOT = Path(r"C:\T18")
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "t18.db"))

DDL = [
"""
CREATE TABLE IF NOT EXISTS users(
  user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  username       TEXT UNIQUE NOT NULL,
  display_name   TEXT NOT NULL,
  role           TEXT NOT NULL CHECK(role IN ('Admin','Trader')),
  password_hash  TEXT NOT NULL,
  active         INTEGER NOT NULL DEFAULT 1,
  mfa_enabled    INTEGER NOT NULL DEFAULT 0,
  profile_pic    TEXT,  -- path or small dataurl
  force_reset    INTEGER NOT NULL DEFAULT 0,
  last_login_ts  INTEGER,
  created_ts     INTEGER NOT NULL,
  deleted_ts     INTEGER
);
""",
"""
CREATE TABLE IF NOT EXISTS password_history(
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER NOT NULL,
  password_hash  TEXT NOT NULL,
  changed_ts     INTEGER NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
""",
"""
CREATE TABLE IF NOT EXISTS mfa_secrets(
  user_id        INTEGER PRIMARY KEY,
  totp_secret    TEXT NOT NULL,
  recovery_json  TEXT NOT NULL, -- ["code1","code2",...]
  created_ts     INTEGER NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
""",
"""
CREATE TABLE IF NOT EXISTS sessions(
  session_id     TEXT PRIMARY KEY,
  user_id        INTEGER NOT NULL,
  device_label   TEXT,
  ip_addr        TEXT,
  user_agent     TEXT,
  issued_ts      INTEGER NOT NULL,
  last_seen_ts   INTEGER NOT NULL,
  revoked_ts     INTEGER,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
""",
"""
CREATE TABLE IF NOT EXISTS audit_log(
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  ts             INTEGER NOT NULL,
  actor_username TEXT,
  scope          TEXT NOT NULL,   -- e.g. 'UAM'
  action         TEXT NOT NULL,   -- e.g. 'CREATE_USER'
  target         TEXT,            -- e.g. 'username:alice'
  meta_json      TEXT             -- details (redacted where needed)
);
""",
"""
CREATE TABLE IF NOT EXISTS password_policy(
  id             INTEGER PRIMARY KEY CHECK(id=1),
  min_length     INTEGER NOT NULL DEFAULT 12,
  require_upper  INTEGER NOT NULL DEFAULT 1,
  require_lower  INTEGER NOT NULL DEFAULT 1,
  require_digit  INTEGER NOT NULL DEFAULT 1,
  require_symbol INTEGER NOT NULL DEFAULT 1,
  blocklist_on   INTEGER NOT NULL DEFAULT 1,
  history_N      INTEGER NOT NULL DEFAULT 5,
  expiry_days    INTEGER NOT NULL DEFAULT 90,
  lockout_thresh INTEGER NOT NULL DEFAULT 5,
  lockout_secs   INTEGER NOT NULL DEFAULT 900
);
""",
"""
CREATE TABLE IF NOT EXISTS password_blocklist(
  phrase TEXT PRIMARY KEY
);
""",
"""
CREATE TABLE IF NOT EXISTS role_permissions(
  role TEXT NOT NULL,
  capability TEXT NOT NULL,
  PRIMARY KEY(role, capability)
);
""",
]

DEFAULT_PERMS = {
  "Admin": [
    "user.create","user.edit","user.disable","user.enable","user.delete_soft",
    "user.reset_password","user.view_sessions","user.revoke_session","user.revoke_all",
    "policy.view","policy.edit","audit.view","audit.export","role.matrix.view","role.matrix.edit"
  ],
  "Trader": [
    "user.self.view","user.self.mfa_enroll","user.self.reset_password",
    "policy.view","audit.view"
  ]
}

def ensure_policy_and_perms(cur):
    cur.execute("INSERT OR IGNORE INTO password_policy(id) VALUES (1)")
    for role, caps in DEFAULT_PERMS.items():
        for c in caps:
            cur.execute("INSERT OR IGNORE INTO role_permissions(role, capability) VALUES (?,?)", (role,c))

def seed_blocklist(cur):
    common = ["password","Password123","qwerty","letmein","admin","welcome","iloveyou","12345678","teevra18","<PLACEHOLDER>"]
    for w in common:
        cur.execute("INSERT OR IGNORE INTO password_blocklist(phrase) VALUES (?)", (w.lower(),))

def bootstrap_admin(cur, username="admin"):
    # Only if no admins exist
    cur.execute("SELECT COUNT(*) FROM users WHERE role='Admin' AND deleted_ts IS NULL")
    if cur.fetchone()[0] == 0:
        from passlib.hash import bcrypt
        now = int(time.time())
        pwd = "Admin!" + secrets.token_urlsafe(8)
        phash = bcrypt.hash(pwd)
        cur.execute("""INSERT INTO users(username,display_name,role,password_hash,active,mfa_enabled,force_reset,last_login_ts,created_ts)
                       VALUES (?,?,?,?,?,?,?, ?,?)""",
                    (username,"Administrator","Admin",phash,1,0,1,None,now))
        cur.execute("SELECT user_id FROM users WHERE username=?", (username,))
        uid = cur.fetchone()[0]
        cur.execute("INSERT INTO password_history(user_id,password_hash,changed_ts) VALUES (?,?,?)",(uid,phash,now))
        print(f"[BOOTSTRAP] Admin user created: {username} / TEMP PASSWORD: {pwd}")
        print("Please login and change password immediately.")

def main():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        for stmt in DDL:
            cur.execute(stmt)
        ensure_policy_and_perms(cur)
        seed_blocklist(cur)
        bootstrap_admin(cur, username="admin")
        con.commit()
    print(f"UAM schema ready at {DB_PATH}")

if __name__ == "__main__":
    main()
