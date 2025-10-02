# -*- coding: utf-8 -*-
# C:\T18\app\ui\webparts\signals_table_webpart.py
#
# Webpart: Signals Table
# Fix: Removed width="stretch" (invalid). Use use_container_width=True instead.

from __future__ import annotations
import streamlit as st
import pandas as pd


def render_signals_table(df: pd.DataFrame | None = None) -> None:
    """
    Renders the latest signals table.
    If no DataFrame is passed, renders a placeholder demo table.
    """
    if df is None:
        # Demo placeholder data
        df = pd.DataFrame(
            [
                {
                    "Time": "09:20:01",
                    "Symbol": "NIFTY24OCTFUT",
                    "Side": "BUY",
                    "Price": 22510.5,
                    "Reason": "Breakout",
                },
                {
                    "Time": "09:38:44",
                    "Symbol": "BANKNIFTY24OCTFUT",
                    "Side": "SELL",
                    "Price": 48755.0,
                    "Reason": "Reversal",
                },
            ]
        )

    # Render as full-width responsive dataframe
    st.dataframe(
        df,
        use_container_width=True,  # ✅ replaces invalid width="stretch"
        hide_index=True,
    )
