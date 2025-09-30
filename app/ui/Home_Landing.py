# -*- coding: utf-8 -*-
# C:\T18\app\ui\Home_Landing.py
from __future__ import annotations

# ---- PATH BOOTSTRAP (must be before any project imports)
import sys
from pathlib import Path
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --------------------------------------------------------
# Standard imports
# --------------------------------------------------------
import sqlite3
import streamlit as st

# Project imports (now that ROOT is on sys.path)
from t18_common.schema import ensure_schema
from app.auth import verify_credentials  # assumes package layout: C:\T18\app\auth.py (or auth/__init__.py)

# --------------------------------------------------------
# Streamlit Config — MUST be first UI call
# --------------------------------------------------------
st.set_page_config(
    page_title="Teevra18 | Login",
    page_icon="🔒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --------------------------------------------------------
# Helpers
# --------------------------------------------------------
DB_PATH = ROOT / "data" / "t18.db"

def ensure_user_exists(username: str, display_name: str = None, role: str = "trader") -> None:
    """
    Auto-provision a minimal user row if missing, so it shows up in UAM immediately
    after the first successful login. Safe no-op if user already exists.
    """
    if not username:
        return
    uname = username.strip()
    uname_norm = uname.lower()
    dname = display_name or uname

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username=? AND deleted_ts IS NULL", (uname,))
        if cur.fetchone():
            return
        cur.execute(
            """
            INSERT INTO users (username, display_name, role, password_hash, active, mfa_enabled,
                               profile_pic, force_reset, last_login_ts, created_ts)
            VALUES (?, ?, ?, NULL, 1, 0, NULL, 0, strftime('%s','now'), strftime('%s','now'))
            """,
            (uname, dname, role)
        )
        conn.commit()

# --------------------------------------------------------
# Ensure DB schema exists before any login logic
# --------------------------------------------------------
ensure_schema()

# If already logged in, route to dashboard
if st.session_state.get("user"):
    try:
        st.switch_page("pages/01_Dashboard.py")
    except Exception:
        # Fallback to query params routing
        if st.query_params.get("page") != "dashboard":
            st.query_params["page"] = "dashboard"
            st.rerun()
    st.stop()

# --------------------------------------------------------
# UI — Minimal, centered login
# --------------------------------------------------------
st.markdown("<h2 style='text-align:center;margin-top:0;'>Welcome to TeeVra18</h2>", unsafe_allow_html=True)
st.caption("Local-only. Please sign in to continue.")

with st.form("login_form", clear_on_submit=False):
    username = st.text_input("Username", value="", autocomplete="username")
    password = st.text_input("Password", value="", type="password", autocomplete="current-password")
    c1, c2 = st.columns([1,1])
    with c1:
        submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)
    with c2:
        st.form_submit_button("Cancel", use_container_width=True)

if submit:
    if not username or not password:
        st.error("Please enter both username and password.")
    else:
        user = verify_credentials(username, password)
        if not user:
            st.error("Invalid credentials or inactive user.")
        else:
            # Store essential session state
            st.session_state["user"] = {
                "id": getattr(user, "id", None),
                "username": getattr(user, "username", username),
                "full_name": getattr(user, "full_name", username),
                "role": getattr(user, "role", "trader"),
                "avatar_path": getattr(user, "avatar_path", None),
            }
            # Auto-provision in DB if missing so UAM shows it immediately
            ensure_user_exists(
                st.session_state["user"]["username"],
                display_name=st.session_state["user"]["full_name"],
                role=st.session_state["user"]["role"]
            )
            # Redirect to dashboard
            try:
                st.switch_page("pages/01_Dashboard.py")
            except Exception:
                # Guard to prevent infinite rerun loops
                if st.query_params.get("page") != "dashboard":
                    st.query_params["page"] = "dashboard"
                    st.rerun()
