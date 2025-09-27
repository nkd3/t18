import streamlit as st

def render_summary_chips():
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Today P/L", "₹0", "+0")
    c2.metric("Open Risk", "₹0")
    c3.metric("Trades", "0")
    c4.metric("Signals", "🟢0 · 🟠0 · 🔴0")
