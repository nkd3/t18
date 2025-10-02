# C:\T18\app\ui\components\top_bar.py
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from io import BytesIO
import os, base64, html
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────────────────────────────────────
ASSETS = Path(r"C:\T18\assets")
LOGO_ENV = os.getenv("T18_LOGO_PATH")
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
    if LOGO_ENV and Path(LOGO_ENV).exists():
        p = Path(LOGO_ENV)
        mime = "image/png" if p.suffix.lower() == ".png" else "image/x-icon"
        return _b64_data_uri(p, mime)
    if LOGO_PNG.exists():
        return _b64_data_uri(LOGO_PNG, "image/png")
    if LOGO_ICO.exists():
        return _b64_data_uri(LOGO_ICO, "image/x-icon")
    return None

# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class UiUser:
    full_name: str
    username: str
    email: str
    role: str
    photo_bytes: bytes | None = None
    photo_path: str | None = None

def _get_ui_user() -> UiUser | None:
    u = st.session_state.get("user") or st.session_state.get("auth_user")
    if not u:
        return None
    return UiUser(
        full_name=str(u.get("full_name") or u.get("display_name") or u.get("name") or ""),
        username=str(u.get("username") or u.get("user_id") or ""),
        email=str(u.get("email") or ""),
        role=str(u.get("role") or u.get("role_name") or ""),
        photo_bytes=u.get("photo_bytes"),
        photo_path=u.get("photo_path"),
    )

def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p.strip()]
    if not parts:
        return "U"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else (parts[0][1] if len(parts[0]) > 1 else ""))).upper()

def _text_wh(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    if hasattr(draw, "textbbox"):
        x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
        return (x1 - x0, y1 - y0)
    if hasattr(font, "getsize"):
        return font.getsize(text)  # type: ignore[attr-defined]
    return (int(0.6 * font.size * max(1, len(text))), font.size)

def _initials_circle_png(text: str, size: int = 48) -> bytes:
    img = Image.new("RGBA", (size, size), (36, 40, 48, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=(210, 216, 226, 255))
    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.42))
    except Exception:
        font = ImageFont.load_default()
    w, h = _text_wh(d, text, font)
    d.text(((size - w) / 2, (size - h) / 2), text, fill=(30, 41, 59, 255), font=font)
    bio = BytesIO(); img.save(bio, format="PNG"); return bio.getvalue()

def _circle_from_bytes(img_bytes: bytes, size: int = 48) -> bytes:
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    w, h = img.size; m = min(w, h)
    img = img.crop(((w - m)//2, (h - m)//2, (w - m)//2 + m, (h - m)//2 + m)).resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0,0,0,0))
    out.paste(img, (0,0), mask)
    bio = BytesIO(); out.save(bio, format="PNG"); return bio.getvalue()

def _avatar_png_bytes() -> bytes:
    user = _get_ui_user()
    if user and user.photo_bytes:
        try: return _circle_from_bytes(user.photo_bytes, size=48)
        except Exception: pass
    if user and user.photo_path and Path(user.photo_path).exists():
        try: return _circle_from_bytes(Path(user.photo_path).read_bytes(), size=48)
        except Exception: pass
    if AVATAR_PNG.exists():
        try: return _circle_from_bytes(AVATAR_PNG.read_bytes(), size=48)
        except Exception: pass
    init = _initials((user.full_name if user else "") or (user.username if user else "") or "User")
    return _initials_circle_png(init, size=48)

def _avatar_data_uri() -> str:
    return f"data:image/png;base64,{base64.b64encode(_avatar_png_bytes()).decode('ascii')}"

# ──────────────────────────────────────────────────────────────────────────────
# Action handlers to keep navigation in the SAME window
def _go_settings_users_directory() -> None:
    """Route to Settings → Account & Roles (UAM) → Users Directory."""
    try:
        # If your settings subpage exists as a page file
        st.switch_page("pages/Settings_Account_Roles.py")
    except Exception:
        # Fallback via query params to reach the Users Directory section
        try:
            st.query_params.clear()
            st.query_params["page"] = "Settings"
            st.query_params["settings_tab"] = "UAM"
            st.query_params["settings_section"] = "users_directory"
        finally:
            st.rerun()

def _sign_out_and_go_home() -> None:
    """Clear session and go to Home_Landing.py in the SAME window."""
    for k in ("user", "auth_user"):
        st.session_state.pop(k, None)
    try:
        st.switch_page("Home_Landing.py")
    except Exception:
        try:
            st.query_params.clear()
            st.query_params["page"] = "Home_Landing"
        finally:
            st.rerun()

def _handle_url_actions() -> None:
    """
    Process ?t18_action=profile|signout triggered from the CSS dropdown <a> links.
    This guarantees same-window navigation.
    """
    act = st.query_params.get("t18_action")
    if not act:
        return
    # Clear the action param to avoid loops on rerun
    current = dict(st.query_params)
    current.pop("t18_action", None)
    st.query_params.clear()
    for k, v in current.items():
        st.query_params[k] = v

    if act == "signout":
        _sign_out_and_go_home()
    elif act == "profile":
        _go_settings_users_directory()

# ──────────────────────────────────────────────────────────────────────────────
def _style_once():
    st.markdown("""
    <style>
      .t18-logo{ width:42px; height:42px; border-radius:50%; object-fit:cover;
                 background:#0e1013; border:1px solid rgba(255,255,255,.08); }
      .t18-title{ font-weight:700; font-size:17px; white-space:nowrap; margin-left:.5rem; }
      .t18-breadcrumb{ color:#9aa0a6; font-size:13px; opacity:.9; margin-left:.5rem; }

      .t18-center-row{ display:flex; align-items:center; gap:8px; white-space:nowrap; overflow:hidden; }
      .t18-chip{
        display:inline-flex; align-items:center; gap:5px;
        padding:6px 10px; border-radius:9999px;
        font-size:12px; line-height:1; height:28px;
        border:1px solid rgba(255,255,255,.10);
        background: rgba(120,255,180,0.08); color:#e6f4ea;
      }
      .t18-chip strong{ opacity:.92 }
      .t18-bg-info  { background:rgba(60,130,255,.12);  color:#b3ccff; }
      .t18-bg-ok    { background:rgba(34,197,94,.12);   color:#bff0cc; }
      .t18-bg-warn  { background:rgba(245,158,11,.12);  color:#ffe0b3; }
      .t18-bg-crit  { background:rgba(239,68,68,.14);   color:#ffd1d1; }
      .t18-bg-muted { background:rgba(148,163,184,.12); color:#d5dbe5; }
      @media (max-width: 1780px){ .chip-chain   { display:none; } }
      @media (max-width: 1700px){ .chip-candles { display:none; } }
      @media (max-width: 1620px){ .chip-depth   { display:none; } }
      @media (max-width: 1540px){ .chip-ingest  { display:none; } }
      @media (max-width: 1460px){ .chip-token   { display:none; } }
      @media (max-width: 1380px){ .chip-ping    { display:none; } }
      @media (max-width: 1300px){ .chip-fresh   { display:none; } }

      /* Right cluster */
      .t18-right-wrap { display:flex; align-items:center; gap:12px; justify-content:flex-end; }

      /* CSS-only dropdown: hidden checkbox toggles the menu */
      .t18-acc { position:relative; display:inline-block; }
      .t18-acc input.t18-toggle{ position:absolute; opacity:0; pointer-events:none; }
      .t18-acc label.t18-avatar{
        width:48px; height:48px; border-radius:50%;
        background-size:cover; background-position:center center;
        border:1px solid rgba(255,255,255,.10);
        display:inline-block; cursor:pointer;
      }
      .t18-acc .t18-menu{
        position:absolute; right:0; top:58px; min-width:172px;
        background:rgba(20,22,26,.98); border:1px solid rgba(255,255,255,.10);
        border-radius:12px; padding:8px; display:none; z-index:9999;
        box-shadow:0 8px 24px rgba(0,0,0,.35);
      }
      .t18-acc input.t18-toggle:checked ~ .t18-menu{ display:block; }
      .t18-acc .t18-menu a{
        display:block; text-decoration:none; color:#e6eaf2;
        padding:8px 10px; border-radius:8px; font-size:14px;
      }
      .t18-acc .t18-menu a:hover{ background:rgba(255,255,255,.06); }

      .t18-bell{ font-size:18px; opacity:.85; }
      hr.t18-sep{ margin-top:.35rem; margin-bottom:.5rem; border:0; border-top:1px solid rgba(255,255,255,.08); }
    </style>
    """, unsafe_allow_html=True)

def _chip(label: str, value: str, level: str="info", extra_class: str = "") -> str:
    klass = {"info":"t18-bg-info","ok":"t18-bg-ok","warn":"t18-bg-warn",
             "crit":"t18-bg-crit","muted":"t18-bg-muted"}.get(level,"t18-bg-info")
    return f'<span class="t18-chip {klass} {extra_class}"><strong>{html.escape(label)}:</strong> {html.escape(value)}</span>'

# ──────────────────────────────────────────────────────────────────────────────
def render_top_bar(page_title: str,
                   breadcrumb: str | None = None,
                   use_mock: bool = True,
                   mock: dict | None = None,
                   parent_href: str | None = None):
    """
    Chips stay compact & single-line. Right side shows bell + avatar.
    Clicking the avatar opens a CSS-only dropdown (My Profile / Sign out).
    Links are handled inside the app so navigation stays in the SAME window.
    """
    # Handle actions triggered by the dropdown links
    _handle_url_actions()

    _style_once()
    logo_src = _logo_src()
    avatar_src = _avatar_data_uri()

    d = mock or {
        "trading_state":"RUNNING","market_session":"LIVE",
        "ping_ms":42,"last_tick_s":1.0,"token_left_min":245,
        "ingest_health":"OK","depth_health":"OK","candles_health":"OK","chain_health":"OK"
    }
    lvl = lambda v: {"OK":"ok","DEGRADED":"warn","ERROR":"crit"}.get(v,"muted")
    ts_level = {"RUNNING":"info","PAUSED":"warn","PANIC":"crit"}.get(d.get("trading_state","RUNNING"),"info")
    ms_level = {"PREOPEN":"info","LIVE":"ok","HALTED":"warn","CLOSED":"muted","HOLIDAY":"muted"}.get(d.get("market_session","LIVE"),"info")
    fresh_level = "ok" if float(d.get("last_tick_s", 1.0)) <= 3 else ("warn" if float(d.get("last_tick_s", 1.0)) <= 10 else "crit")
    token_level = "ok" if int(d.get("token_left_min", 245)) > 180 else ("warn" if int(d.get("token_left_min", 245)) > 60 else "crit")

    c_left, c_center, c_right = st.columns([1.4, 6.6, 2.0])

    with c_left:
        title_html = f"""
          <div style="display:flex;align-items:center;gap:.5rem;">
            {f'<img class="t18-logo" src="{logo_src}" alt="Logo"/>' if logo_src else ''}
            <span class="t18-title">{html.escape(page_title)}</span>
            {f'<span class="t18-breadcrumb">› {html.escape(breadcrumb)}</span>' if breadcrumb else ''}
          </div>
        """
        st.markdown(title_html, unsafe_allow_html=True)

    with c_center:
        chips_html = f"""
        <div class="t18-center-row">
          {_chip("State", d.get("trading_state","RUNNING"), ts_level, "chip-state")}
          {_chip("Market", d.get("market_session","LIVE"), ms_level, "chip-market")}
          {_chip("Freshness", f'{float(d.get("last_tick_s",1.0)):.1f}s', fresh_level, "chip-fresh")}
          {_chip("Ping", f'{int(d.get("ping_ms",42))}ms', "info", "chip-ping")}
          {_chip("Token", f'{int(d.get("token_left_min",245))}min', token_level, "chip-token")}
          {_chip("Ingest", d.get("ingest_health","OK"), lvl(d.get("ingest_health","OK")), "chip-ingest")}
          {_chip("Depth", d.get("depth_health","OK"), lvl(d.get("depth_health","OK")), "chip-depth")}
          {_chip("Candles", d.get("candles_health","OK"), lvl(d.get("candles_health","OK")), "chip-candles")}
          {_chip("Chain", d.get("chain_health","OK"), lvl(d.get("chain_health","OK")), "chip-chain")}
        </div>
        """
        st.markdown(chips_html, unsafe_allow_html=True)

    with c_right:
        # Pure HTML, CSS-only toggle via hidden checkbox; links handled via _handle_url_actions()
        st.markdown(f"""
          <div class="t18-right-wrap">
            <span class="t18-bell" title="Notifications">🔔</span>
            <div class="t18-acc">
              <input type="checkbox" id="t18-acc-toggle" class="t18-toggle" />
              <label for="t18-acc-toggle" class="t18-avatar" style="background-image:url('{avatar_src}');" title="Account"></label>
              <div class="t18-menu">
                <a href="?t18_action=profile">👤 My Profile</a>
                <a href="?t18_action=signout">↩️ Sign out</a>
              </div>
            </div>
          </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr class='t18-sep'/>", unsafe_allow_html=True)
