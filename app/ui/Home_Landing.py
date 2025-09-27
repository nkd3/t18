# -*- coding: utf-8 -*-
# C:\T18\app\ui\Home_Landing.py
from __future__ import annotations
from pathlib import Path
import streamlit as st

# Local imports
from t18_common.schema import ensure_schema
from app.auth import verify_credentials

# --------------------------------------------------------
# Streamlit Config — MUST be first
# --------------------------------------------------------
st.set_page_config(
    page_title="Teevra18 | Login",
    page_icon="🔒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Ensure DB schema exists before any login logic
ensure_schema()

# If already logged in, route to dashboard
if st.session_state.get("user"):
    try:
        st.switch_page("pages/01_Dashboard.py")
    except Exception:
        # ✅ FIX: Use st.query_params instead of deprecated experimental API
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
            # store essential session state
            st.session_state["user"] = {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "avatar_path": user.avatar_path,
            }
            # Redirect to dashboard
            try:
                st.switch_page("pages/01_Dashboard.py")
            except Exception:
                # ✅ FIX: Guard to prevent infinite rerun loops
                if st.query_params.get("page") != "dashboard":
                    st.query_params["page"] = "dashboard"
                    st.rerun()
