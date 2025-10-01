# C:\T18\app\ui\components\top_bar.py
from __future__ import annotations
from pathlib import Path
import os, base64
import streamlit as st

ASSETS = Path(r"C:\T18\assets")
LOGO_PNG = ASSETS / "Teevra18_Logo.png"
LOGO_ICO = ASSETS / "Teevra18_Logo.ico"
AVATAR_PNG = ASSETS / "avatar.png"

def _b64_data_uri(path: Path, mime: str) -> str | None:
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None

def _logo_src() -> str | None:
    if LOGO_PNG.exists():
        return _b64_data_uri(LOGO_PNG, "image/png")
    if LOGO_ICO.exists():
        return _b64_data_uri(LOGO_ICO, "image/x-icon")
    return None

def _avatar_src() -> str | None:
    if AVATAR_PNG.exists():
        return _b64_data_uri(AVATAR_PNG, "image/png")
    return None

def _style_once():
    st.markdown("""
    <style>
      /* ---- layout skeleton ---- */
      .t18-topbar{
        height:90px; padding:10px 18px;
        border-bottom:1px solid rgba(0,0,0,.12);
        display:flex; align-items:center; gap:16px;
        box-sizing:border-box;
      }
      /* Reserve space for the right cluster so center never runs under it */
      .t18-right { display:flex; align-items:center; gap:12px; flex:0 0 260px; min-width:260px; justify-content:flex-end; }
      .t18-left  { display:flex; align-items:center; gap:12px; flex:0 1 28%; min-width:240px; overflow:hidden; }
      .t18-center{ display:flex; align-items:center; gap:12px; flex:1 1 auto; min-width:0; overflow:hidden; }

      .t18-topbar *{ line-height:1; vertical-align:middle; }

      /* title + breadcrumb (breadcrumb truncates) */
      .t18-title{ font-weight:700; font-size:18px; white-space:nowrap; }
      .t18-title a{ color:inherit; text-decoration:none; border-bottom:1px dotted rgba(255,255,255,.25); }
      .t18-title a:hover{ opacity:.9; }
      .t18-breadcrumb{
        color:var(--text-color,#9aa0a6); font-size:14px; opacity:.9;
        max-width:28vw; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
      }

      /* 70x70 circular media */
      .t18-logo, .t18-avatar{
        width:70px; height:70px; border-radius:50%;
        object-fit:cover; display:inline-block; background:#ddd; flex:0 0 auto;
      }

      /* chips */
      .t18-chip{
        display:inline-flex; align-items:center; gap:6px;
        padding:9px 16px; border-radius:9999px;
        font-size:15px; line-height:1; height:38px;
        white-space:nowrap; box-sizing:border-box; flex:0 0 auto;
      }
      .t18-chip strong{ opacity:.85 }
      .t18-bg-info  { background:#e6f4ff; color:#1677ff; }
      .t18-bg-ok    { background:#eafff0; color:#389e0d; }
      .t18-bg-warn  { background:#fff7e6; color:#d48806; }
      .t18-bg-crit  { background:#fff1f0; color:#cf1322; }
      .t18-bg-muted { background:#f5f5f5; color:#595959; }

      /* RESPONSIVE: progressively hide lower-priority chips when width shrinks
         (works for sidebar open/closed without overlap). Keep State/Market. */
      @media (max-width: 1700px){ .chip-chain   { display:none; } }
      @media (max-width: 1620px){ .chip-candles { display:none; } }
      @media (max-width: 1540px){ .chip-depth   { display:none; } }
      @media (max-width: 1460px){ .chip-ingest  { display:none; } }
      @media (max-width: 1380px){ .chip-token   { display:none; } }
      @media (max-width: 1300px){ .chip-ping    { display:none; } }
      @media (max-width: 1220px){ .chip-fresh   { display:none; } }

      /* When very narrow, also constrain left area a bit more */
      @media (max-width: 1200px){
        .t18-left{ flex-basis:22%; }
        .t18-breadcrumb{ max-width:22vw; }
      }
      @media (max-width: 1000px){
        .t18-left{ flex-basis:18%; }
        .t18-breadcrumb{ max-width:18vw; }
      }
    </style>
    """, unsafe_allow_html=True)

def _chip(label: str, value: str, level: str="info", extra_class: str = "") -> str:
    klass = {"info":"t18-bg-info","ok":"t18-bg-ok","warn":"t18-bg-warn",
             "crit":"t18-bg-crit","muted":"t18-bg-muted"}.get(level,"t18-bg-info")
    return f'<span class="t18-chip {klass} {extra_class}"><strong>{label}:</strong> {value}</span>'

def _env_badge():
    env = os.getenv("T18_ENV","LOCAL").upper()
    level = {"LOCAL":"muted","PAPER":"warn","LIVE-READY":"ok"}.get(env,"muted")
    return _chip("ENV",env,level)

def render_top_bar(page_title: str,
                   breadcrumb: str | None = None,
                   use_mock: bool = True,
                   mock: dict | None = None,
                   parent_href: str | None = None):
    """
    parent_href: optional link for the page_title when a breadcrumb is shown.
                 Example for Settings subpage: parent_href='?page=Settings'
                 (You can pass any absolute/relative URL.)
    """
    _style_once()

    # media
    logo_src = _logo_src()
    avatar_src = _avatar_src()
    logo_html = f'<img class="t18-logo" src="{logo_src}" alt="Logo" />' if logo_src else '<span class="t18-logo" title="Logo"></span>'
    avatar_html = f'<img class="t18-avatar" src="{avatar_src}" alt="User" title="User" />' if avatar_src else '<span class="t18-avatar" title="User" style="display:inline-grid;place-items:center;font-size:28px;">👤</span>'

    # status
    d = mock or {
        "trading_state":"RUNNING","market_session":"LIVE",
        "ping_ms":42,"last_tick_s":1.0,"token_left_min":245,
        "ingest_health":"OK","depth_health":"OK","candles_health":"OK","chain_health":"OK"
    }
    lvl = lambda v: {"OK":"ok","DEGRADED":"warn","ERROR":"crit"}.get(v,"muted")
    ts_level = {"RUNNING":"info","PAUSED":"warn","PANIC":"crit"}.get(d["trading_state"],"info")
    ms_level = {"PREOPEN":"info","LIVE":"ok","HALTED":"warn","CLOSED":"muted","HOLIDAY":"muted"}.get(d["market_session"],"info")
    fresh_level = "ok" if d["last_tick_s"]<=3 else ("warn" if d["last_tick_s"]<=10 else "crit")
    token_level = "ok" if d["token_left_min"]>180 else ("warn" if d["token_left_min"]>60 else "crit")

    # left cluster (clickable parent when breadcrumb is present and parent_href provided)
    if breadcrumb and parent_href:
        title_html = f'<span class="t18-title"><a href="{parent_href}">{page_title}</a></span>'
    else:
        title_html = f'<span class="t18-title">{page_title}</span>'

    left_html = f"""
      <div class="t18-left">
        {logo_html}
        {title_html}
        {f'<span class="t18-breadcrumb">› {breadcrumb}</span>' if breadcrumb else ''}
      </div>"""

    center_html = f"""
      <div class="t18-center">
        {_chip("State", d["trading_state"], ts_level, "chip-state")}
        {_chip("Market", d["market_session"], ms_level, "chip-market")}
        {_chip("Freshness", f'{d["last_tick_s"]:.1f}s', fresh_level, "chip-fresh")}
        {_chip("Ping", f'{d["ping_ms"]}ms', "info", "chip-ping")}
        {_chip("Token", f'{d["token_left_min"]}min', token_level, "chip-token")}
        {_chip("Ingest", d["ingest_health"], lvl(d["ingest_health"]), "chip-ingest")}
        {_chip("Depth", d["depth_health"], lvl(d["depth_health"]), "chip-depth")}
        {_chip("Candles", d["candles_health"], lvl(d["candles_health"]), "chip-candles")}
        {_chip("Chain", d["chain_health"], lvl(d["chain_health"]), "chip-chain")}
      </div>"""

    right_html = f"""
      <div class="t18-right">
        {_env_badge()}
        <span title="Notifications">🔔</span>
        {avatar_html}
      </div>"""

    st.markdown(f"""
      <div class="t18-topbar">
        {left_html}{center_html}{right_html}
      </div>
    """, unsafe_allow_html=True)
