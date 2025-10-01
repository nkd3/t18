# C:\T18\app\ui\pages\Settings_Account_Roles.py
# -*- coding: utf-8 -*-
# Windows • Python 3.11 • Streamlit
# Relies on: t18_common.security, t18_common.audit, uam_schema
# DB path: from ENV DB_PATH else C:\T18\data\t18.db

from pathlib import Path
import sys, os, io, time, json, base64, sqlite3
import pandas as pd
import streamlit as st
from PIL import Image
import pyotp, qrcode

# ── IMPORTANT: first Streamlit call must be set_page_config ─────────────────────
APP_TITLE = "Settings • Account & Roles (UAM)"
st.set_page_config(page_title=APP_TITLE, page_icon="👥", layout="wide")

# ── PATH BOOTSTRAP ─────────────────────────────────────────────────────────────
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Local imports AFTER path bootstrap
from app.ui.shell.topbar import topbar
from t18_common.security import (
    _db, hash_password, verify_password, validate_password,
    record_password_history, list_role_caps, ensure_not_last_admin, redact
)
from t18_common.audit import log as audit_log

# ── Schema ensure (may show st.error, so it must run AFTER set_page_config) ────
def ensure_schema():
    try:
        with _db() as con:
            con.execute("SELECT 1 FROM users LIMIT 1")
    except sqlite3.OperationalError:
        try:
            import uam_schema
            uam_schema.main()
        except Exception as e:
            st.error(f"Failed to initialize UAM schema: {e}")
            raise

ensure_schema()

# ── Global Top Bar (renders FIRST, after set_page_config) ──────────────────────
# parent_href makes the parent title clickable (back to main Settings page).
# If your routing differs, change to the correct href (e.g., "/?page=05_Settings").
topbar("Settings", breadcrumb="Account & Roles", parent_href="?page=Settings")

st.title("👥 Account & Roles (UAM)")

# Effective DB path (display only)
db_path_effective = os.getenv("DB_PATH", str(Path(r"C:\T18\data\t18.db")))
st.caption(
    "Manage users, MFA, sessions, roles & audit. Safety checks prevent removal/demotion of the last Admin.  "
    f"**DB:** `{db_path_effective}`"
)

# ── Helpers ────────────────────────────────────────────────────────────────────
def db():
    return _db()

def get_actor_username() -> str:
    u = st.session_state.get("user")
    if isinstance(u, dict):
        return u.get("username", "admin")
    if isinstance(u, str):
        return u or "admin"
    return "admin"

def img_to_dataurl(img: Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

def fmt_epoch_series_to_local_str(s: pd.Series, tz: str = "Europe/London") -> pd.Series:
    s_clean = pd.to_numeric(s, errors="coerce")
    s_clean = s_clean.where(s_clean.notna() & (s_clean > 0), other=pd.NA)
    dt = pd.to_datetime(s_clean, unit="s", errors="coerce")
    try:
        dt = dt.dt.tz_localize("UTC").dt.tz_convert(tz)
    except TypeError:
        dt = dt.dt.tz_convert(tz)
    return dt.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")

def show_policy_preview(conn):
    pol = validate_password(conn, None, "Aa1!example")["policy"]
    cols = st.columns(5)
    cols[0].metric("Min length", pol.get("min_length", ""))
    cols[1].metric("History N", pol.get("history_N", ""))
    cols[2].metric("Expiry (days)", pol.get("expiry_days", ""))
    cols[3].metric("Lockout thresh", pol.get("lockout_thresh", ""))
    cols[4].metric("Cooldown (s)", pol.get("lockout_secs", ""))

def load_users(conn, show_deleted: bool, show_inactive: bool) -> pd.DataFrame:
    where = []
    if not show_deleted:
        where.append("deleted_ts IS NULL")
    if not show_inactive:
        where.append("active=1")
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    q = f"""
        SELECT
            user_id,
            username              AS Username,
            COALESCE(display_name, username) AS [Display Name],
            role                  AS Role,
            active                AS Active,
            mfa_enabled           AS MFA,
            last_login_ts         AS LastLogin,
            created_ts            AS Created,
            deleted_ts            AS DeletedTs,
            CASE WHEN deleted_ts IS NULL THEN 0 ELSE 1 END AS SoftDeleted
        FROM users
        {where_sql}
        ORDER BY CASE WHEN role='Admin' THEN 1 ELSE 0 END DESC, username ASC
    """
    df = pd.read_sql_query(q, conn)
    if not df.empty:
        df["LastLogin"] = fmt_epoch_series_to_local_str(df["LastLogin"], tz="Europe/London")
        df["Created"]   = fmt_epoch_series_to_local_str(df["Created"], tz="Europe/London")
        df["DeletedTs"] = fmt_epoch_series_to_local_str(df["DeletedTs"], tz="Europe/London")
        df["Active"] = df["Active"].astype(int)
        df["MFA"]    = df["MFA"].astype(int)
        df["SoftDeleted"] = df["SoftDeleted"].astype(int)
    return df

# ── Users Directory ────────────────────────────────────────────────────────────
with db() as con:
    st.subheader("Users Directory")
    fc1, fc2, fc3, fc4 = st.columns([1.2, 1.2, 2, 1])
    with fc1:
        show_deleted = st.toggle("Show soft-deleted", value=True, key="uam_show_deleted")
    with fc2:
        show_inactive = st.toggle("Show inactive", value=True, key="uam_show_inactive")
    with fc3:
        search_text = st.text_input("Search (username/display)", value="", key="uam_search")
    with fc4:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    df = load_users(con, show_deleted=show_deleted, show_inactive=show_inactive)

    if search_text:
        needle = search_text.strip().lower()
        if needle:
            df = df[
                df["Username"].str.lower().str.contains(needle) |
                df["Display Name"].str.lower().str.contains(needle)
            ]

    st.dataframe(
        df[["Username","Display Name","Role","Active","MFA","SoftDeleted","LastLogin","Created","DeletedTs"]],
        use_container_width=True,
        hide_index=True
    )

    # Row selector (includes soft-deleted so you can undelete)
    user_list = ["<none>"] + (df["Username"].tolist() if not df.empty else [])
    selected_username = st.selectbox("Select user to manage", user_list)

    # ── Create User ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Create User")
    with st.form("create_user"):
        cu_username = st.text_input("Username (unique, case-insensitive)").strip()
        cu_display  = st.text_input("Display Name").strip()
        cu_role     = st.selectbox("Role", ["Trader", "Admin"])
        pw_mode     = st.radio("Password", ["Generate secure", "Set manually"])
        cu_force    = st.checkbox("Force reset at first login", value=True)

        c_up, _ = st.columns(2)
        profile_dataurl = None
        with c_up:
            up = st.file_uploader("Profile picture (PNG/JPG)", type=["png","jpg","jpeg"])
        if up:
            img = Image.open(up).convert("RGBA").resize((256,256))
            profile_dataurl = img_to_dataurl(img)
            st.image(img, caption="Preview (auto 256x256)")

        cu_pwd = st.text_input("Set password", type="password") if pw_mode == "Set manually" else None
        st.caption("Usernames are treated case-insensitively (no duplicates by case).")

        if st.form_submit_button("Create"):
            cur = con.cursor()
            uname = cu_username
            uname_norm = uname.lower()

            if not uname or not cu_display:
                st.error("Username and Display Name are required.")
                st.stop()

            # Case-insensitive uniqueness
            row = cur.execute("""
                SELECT 1 FROM users
                WHERE (username_norm = ? OR lower(username) = ?)
                  AND deleted_ts IS NULL
                LIMIT 1
            """, (uname_norm, uname_norm)).fetchone()
            if row:
                st.error("Username already exists (case-insensitive).")
                st.stop()

            if pw_mode == "Generate secure":
                import secrets, string
                alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
                cu_pwd = "".join(secrets.choice(alphabet) for _ in range(18))
                st.info(f"Generated password (copy now): **{cu_pwd}**")

            v = validate_password(con, None, cu_pwd)
            if not v["ok"]:
                st.error("Password fails policy: " + ", ".join(v["problems"]))
                st.stop()

            ph  = hash_password(cu_pwd)
            now = int(time.time())
            cur.execute("""
                INSERT INTO users(
                    username, username_norm, display_name, role,
                    password_hash, active, mfa_enabled, profile_pic,
                    force_reset, last_login_ts, created_ts, deleted_ts
                ) VALUES (?,?,?,?,?, 1, 0, ?, ?, NULL, ?, NULL)
            """, (uname, uname_norm, cu_display, cu_role, ph, profile_dataurl, int(cu_force), now))
            uid = cur.lastrowid

            record_password_history(con, uid, ph)
            con.commit()
            audit_log(get_actor_username(), "UAM","CREATE_USER", f"username:{uname}", meta={"role": cu_role, "user_id": uid})
            st.success(f"User '{uname}' created (id={uid}).")
            st.rerun()  # immediate refresh

    st.divider()
    st.subheader("User Actions")

    if selected_username != "<none>":
        cur = con.cursor()
        sel = cur.execute(
            """SELECT user_id, username, display_name, role, active, mfa_enabled, force_reset, deleted_ts
               FROM users WHERE username=? LIMIT 1""",
            (selected_username,)
        ).fetchone()

        if not sel:
            st.warning("User not found.")
        else:
            sel_map = dict(
                user_id=sel[0], username=sel[1], display_name=sel[2],
                role=sel[3], active=sel[4], mfa_enabled=sel[5], force_reset=sel[6],
                deleted_ts=sel[7]
            )

            # If soft-deleted: offer Undelete action and disable others
            if sel_map["deleted_ts"]:
                st.warning("This user is soft-deleted.")
                if st.button("Undelete user (restore & activate)", type="primary"):
                    cur.execute("UPDATE users SET deleted_ts=NULL, active=1 WHERE user_id=?", (sel_map["user_id"],))
                    con.commit()
                    audit_log(get_actor_username(), "UAM","UNDELETE_USER", f"username:{selected_username}", meta={})
                    st.success("User restored and activated.")
                    st.rerun()
            else:
                # Edit
                with st.expander("Edit User / Role / Status / Password", expanded=True):
                    new_display = st.text_input("Display Name", value=sel_map["display_name"], key="ed_disp")
                    new_role    = st.selectbox("Role", ["Trader","Admin"], index=(0 if sel_map["role"]=="Trader" else 1), key="ed_role")
                    new_active  = st.checkbox("Active", value=bool(sel_map["active"]), key="ed_active")
                    st.caption("⚠️ Changing role impacts capabilities. Admin has full rights; Trader has limited read-only settings.")

                    if st.button("Save changes"):
                        try:
                            if new_role != sel_map["role"]:
                                ensure_not_last_admin(con, sel_map["user_id"])
                            cur.execute("UPDATE users SET display_name=?, role=?, active=? WHERE user_id=?",
                                        (new_display, new_role, 1 if new_active else 0, sel_map["user_id"]))
                            con.commit()
                            audit_log(get_actor_username(), "UAM","EDIT_USER", f"username:{selected_username}",
                                      meta=redact({"before_role": sel_map["role"], "after_role": new_role}))
                            st.success("Updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                    st.markdown("---")
                    st.markdown("**Reset password**")
                    new_pwd = st.text_input("New password", type="password")
                    if st.button("Apply password reset"):
                        v = validate_password(con, sel_map["user_id"], new_pwd)
                        if not v["ok"]:
                            st.error("Password fails policy: " + ", ".join(v["problems"]))
                        else:
                            ph = hash_password(new_pwd)
                            cur.execute("UPDATE users SET password_hash=?, force_reset=1 WHERE user_id=?",
                                        (ph, sel_map["user_id"]))
                            record_password_history(con, sel_map["user_id"], ph)
                            con.commit()
                            audit_log(get_actor_username(), "UAM","RESET_PASSWORD", f"username:{selected_username}", meta={})
                            st.success("Password reset and set to force change on next login.")

                    # Quick Set Temp Password & Activate
                    st.markdown("---")
                    st.markdown("**Quick Set Temp Password & Activate**")
                    temp_pwd = st.text_input("Temp password", value="P@ssw0rd@100", type="password", key="temp_pwd_setter")
                    if st.button("Apply temp password & activate user"):
                        v = validate_password(con, sel_map["user_id"], temp_pwd)
                        if not v["ok"]:
                            st.error("Temp password fails policy: " + ", ".join(v["problems"]))
                        else:
                            ph = hash_password(temp_pwd)
                            cur.execute(
                                "UPDATE users SET password_hash=?, active=1, deleted_ts=NULL, force_reset=0 WHERE user_id=?",
                                (ph, sel_map["user_id"])
                            )
                            record_password_history(con, sel_map["user_id"], ph)
                            con.commit()
                            audit_log(get_actor_username(), "UAM","FORCE_SET_PASSWORD_ACTIVATE",
                                      f"username:{selected_username}", meta={"force": True})
                            st.success("Temp password set, user activated & undeleted (if needed).")
                            st.rerun()

                    st.markdown("---")
                    st.markdown("**Disable / Enable**")
                    cols_en = st.columns(2)
                    if cols_en[0].button("Disable user", disabled=not sel_map["active"]):
                        try:
                            ensure_not_last_admin(con, sel_map["user_id"])
                            cur.execute("UPDATE users SET active=0 WHERE user_id=?", (sel_map["user_id"],))
                            con.commit()
                            audit_log(get_actor_username(), "UAM","DISABLE_USER", f"username:{selected_username}", meta={})
                            st.success("User disabled.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                    if cols_en[1].button("Enable user", disabled=bool(sel_map["active"])):
                        cur.execute("UPDATE users SET active=1 WHERE user_id=?", (sel_map["user_id"],))
                        con.commit()
                        audit_log(get_actor_username(), "UAM","ENABLE_USER", f"username:{selected_username}", meta={})
                        st.success("User enabled.")
                        st.rerun()

                    st.markdown("---")
                    st.markdown("**Soft Delete**")
                    if st.button("Delete (soft)"):
                        try:
                            ensure_not_last_admin(con, sel_map["user_id"])
                            cur.execute("UPDATE users SET deleted_ts=? WHERE user_id=?", (int(time.time()), sel_map["user_id"]))
                            con.commit()
                            audit_log(get_actor_username(), "UAM","DELETE_SOFT", f"username:{selected_username}", meta={})
                            st.success("User soft-deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

            # ── MFA (TOTP) ──────────────────────────────────────────────────────
            with st.expander("MFA (TOTP)"):
                st.write("Enroll or view status. Recovery codes are shown once on enroll.")
                if not sel_map["mfa_enabled"]:
                    if st.button("Enroll TOTP"):
                        import secrets, string
                        secret = pyotp.random_base32()
                        recovery = [
                            "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
                            for _ in range(6)
                        ]
                        cur.execute(
                            "INSERT OR REPLACE INTO mfa_secrets(user_id, totp_secret, recovery_json, created_ts) VALUES (?,?,?,?)",
                            (sel_map["user_id"], secret, json.dumps(recovery), int(time.time()))
                        )
                        cur.execute("UPDATE users SET mfa_enabled=1 WHERE user_id=?", (sel_map["user_id"],))
                        con.commit()
                        audit_log(get_actor_username(), "UAM","MFA_ENROLL", f"username:{selected_username}", meta={})
                        st.success("TOTP enrolled.")
                        issuer = "T18"
                        otp = pyotp.totp.TOTP(secret)
                        uri = otp.provisioning_uri(name=selected_username, issuer_name=issuer)
                        qr_img = qrcode.make(uri).get_image()
                        st.image(qr_img, caption="Scan this QR in your Authenticator app")
                        st.code("\n".join(recovery), language="text")
                else:
                    st.info("TOTP already enabled.")
                    col_mfa1, col_mfa2 = st.columns(2)
                    if col_mfa1.button("Regenerate Recovery Codes"):
                        import secrets, string
                        recovery = [
                            "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
                            for _ in range(6)
                        ]
                        cur.execute(
                            "UPDATE mfa_secrets SET recovery_json=?, created_ts=? WHERE user_id=?",
                            (json.dumps(recovery), int(time.time()), sel_map["user_id"])
                        )
                        con.commit()
                        st.success("New recovery codes generated. Copy and store them safely.")
                        st.code("\n".join(recovery), language="text")

                    if col_mfa2.button("Reset TOTP (Disable)"):
                        cur.execute("DELETE FROM mfa_secrets WHERE user_id=?", (sel_map["user_id"],))
                        cur.execute("UPDATE users SET mfa_enabled=0 WHERE user_id=?", (sel_map["user_id"]),)
                        con.commit()
                        audit_log(get_actor_username(), "UAM","MFA_RESET", f"username:{selected_username}", meta={})
                        st.warning("TOTP disabled. Re-enroll to enable again.")

# ── Roles & Policy & Audit ─────────────────────────────────────────────────────
st.divider()
st.subheader("Roles & Permissions (matrix)")
with db() as con2:
    rp = pd.read_sql_query("SELECT role, capability FROM role_permissions ORDER BY role, capability", con2)
st.dataframe(rp, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Password Policy")
with db() as con3:
    show_policy_preview(con3)
    with st.form("pol_form"):
        pol_df = pd.read_sql_query("SELECT * FROM password_policy WHERE id=1", con3)
        if pol_df.empty:
            st.error("Password policy row is missing (id=1). Please run schema bootstrap.")
        else:
            pol = pol_df.iloc[0].to_dict()
            c1, c2, c3, c4, c5 = st.columns(5)
            min_length = c1.number_input("Min length", min_value=6, max_value=128, value=int(pol["min_length"]))
            histN      = c2.number_input("History N", min_value=0, max_value=24, value=int(pol["history_N"]))
            expiry     = c3.number_input("Expiry (days)", min_value=0, max_value=365, value=int(pol["expiry_days"]))
            lock_thr   = c4.number_input("Lockout threshold", min_value=0, max_value=20, value=int(pol["lockout_thresh"]))
            lock_sec   = c5.number_input("Cooldown (secs)", min_value=0, max_value=86400, value=int(pol["lockout_secs"]))

            r1, r2, r3, r4, r5 = st.columns(5)
            reqU = r1.checkbox("Require UPPER", value=bool(pol["require_upper"]))
            reqL = r2.checkbox("Require lower", value=bool(pol["require_lower"]))
            reqD = r3.checkbox("Require digit", value=bool(pol["require_digit"]))
            reqS = r4.checkbox("Require symbol", value=bool(pol["require_symbol"]))
            blk  = r5.checkbox("Blocklist on", value=bool(pol["blocklist_on"]))

            if st.form_submit_button("Save policy"):
                cur = con3.cursor()
                cur.execute(
                    """UPDATE password_policy SET
                         min_length=?, history_N=?, expiry_days=?, lockout_thresh=?, lockout_secs=?,
                         require_upper=?, require_lower=?, require_digit=?, require_symbol=?, blocklist_on=?
                       WHERE id=1""",
                    (min_length, histN, expiry, lock_thr, lock_sec,
                     int(reqU), int(reqL), int(reqD), int(reqS), int(blk))
                )
                con3.commit()
                audit_log(get_actor_username(), "UAM","POLICY_EDIT", "password_policy", meta={})
                st.success("Policy saved.")

st.divider()
st.subheader("Audit & Compliance")
with db() as con4:
    actor = st.text_input("Actor username filter (optional)")
    time_min = st.number_input("From (epoch sec, optional)", value=0)
    q = "SELECT ts, actor_username, scope, action, target, meta_json FROM audit_log WHERE 1=1"
    params = []
    if actor:
        q += " AND actor_username=?"; params.append(actor)
    if time_min>0:
        q += " AND ts>=?"; params.append(int(time_min))
    q += " ORDER BY ts DESC LIMIT 1000"
    aud = pd.read_sql_query(q, con4, params=params)
    if not aud.empty:
        aud["ts"] = fmt_epoch_series_to_local_str(aud["ts"], tz="Europe/London")
    st.dataframe(aud, use_container_width=True, hide_index=True)

st.info("Safety: UI prevents removing/demoting the last Admin. Keep at least two Admins for recovery.")
