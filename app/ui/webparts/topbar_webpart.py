import streamlit as st
from pathlib import Path

ASSETS = Path(r"C:\T18\assets")

def render_topbar():
    c1,c2,c3,c4 = st.columns([1.2,4,2,1])
    with c1:
        logo = ASSETS/"Teevra18_Logo.png"
        if logo.exists():
            # New API: width="content" instead of use_container_width=False
            st.image(str(logo), width="content")
        else:
            st.markdown("### 🐯 TeeVra18")
    with c2:
        st.markdown("**Dashboard | Market | Strategies | Finance | Settings**")
    with c3:
        st.success("RUNNING", icon="✅")
    with c4:
        st.markdown(":bust_in_silhouette: **You**")
