# C:\T18\app\ui\webparts\topbar_webpart.py
import streamlit as st
from pathlib import Path

ASSETS = Path(r"C:\T18\assets")

def render_topbar():
    c1, c2, c3, c4 = st.columns([1.2, 4, 2, 1])
    with c1:
        logo = ASSETS / "Teevra18_Logo.png"
        if logo.exists():
            # FIX: width must be int or None, not a string
            st.image(str(logo), width=None)
        else:
            st.markdown("### 🐯 TeeVra18")
    with c2:
        st.markdown("**Dashboard | Market | Strategies | Finance | Settings**")
    with c3:
        st.success("RUNNING", icon="✅")
    with c4:
        st.markdown(":bust_in_silhouette: **You**")
