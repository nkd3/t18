# C:\T18\app\ui\shell\nav_helpers.py
# Windows • Python 3.11 • Streamlit
# Same-window navigation helpers for a Streamlit multi-page app.

from __future__ import annotations
from typing import Dict
import streamlit as st

def _qp_set(params: Dict[str, str]) -> None:
    try:
        st.query_params.clear()
        for k, v in params.items():
            st.query_params[k] = v
    except Exception:
        pass  # older Streamlit versions may behave differently

def go_same_window_to_page(page_file: str) -> None:
    """
    Navigate to a top-level page .py in the SAME window if possible.
    Example: go_same_window_to_page("pages/01_Dashboard.py")
    """
    try:
        st.switch_page(page_file)  # type: ignore[attr-defined]
    except Exception:
        # Fallback: route via query-params (shell/router should respect this)
        _qp_set({"page": page_file.replace(".py", "")})
        st.rerun()

def go_settings_users_directory() -> None:
    """
    Navigate to: Settings > Account & Roles (UAM) > Users Directory
    Assumption: Settings pages read these query params.
    """
    try:
        st.switch_page("pages/Settings_Account_Roles.py")  # type: ignore[attr-defined]
    except Exception:
        _qp_set({
            "page": "Settings",
            "settings_tab": "UAM",
            "settings_section": "users_directory",
        })
        st.rerun()
