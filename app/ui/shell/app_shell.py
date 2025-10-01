# C:\T18\app\ui\shell\app_shell.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from typing import Callable

def render_page(title: str, body_fn: Callable[[], None]) -> None:
    """
    Shell wrapper that:
      1) Calls set_page_config() FIRST (per Streamlit rules)
      2) Executes the provided body function (where pages should call topbar(...))
    NOTE: This shell intentionally does NOT render any top bar to avoid
          double headers and to prevent legacy webparts from running.
    """
    # MUST be the first Streamlit call on the page:
    st.set_page_config(
        page_title=f"Teevra18 | {title}",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Do NOT import or call any legacy render_topbar() here.
    # Each page calls: from app.ui.shell.topbar import topbar; topbar("<Title>", breadcrumb="...")

    # Run the page body
    body_fn()
