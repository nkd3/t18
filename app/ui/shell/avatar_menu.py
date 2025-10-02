# C:\T18\app\ui\shell\avatar_menu.py
# Global Avatar (top-right) with a two-item dropdown: My Profile, Sign out.

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import streamlit as st
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from app.ui.shell.nav_helpers import go_same_window_to_page, go_settings_users_directory

# ──────────────────────────────────────────────────────────────────────────────
# Minimal user model — expects st.session_state["auth_user"] set at login.

@dataclass
class AuthUser:
    user_id: str
    display_name: str
    email: str
    photo_bytes: Optional[bytes] = None  # raw bytes of the uploaded photo

def _get_auth_user_from_session() -> Optional[AuthUser]:
    u = st.session_state.get("auth_user")
    if not u:
        return None
    return AuthUser(
        user_id=str(u.get("user_id", "")),
        display_name=str(u.get("display_name") or u.get("name") or "User"),
        email=str(u.get("email") or ""),
        photo_bytes=u.get("photo_bytes"),
    )

# ──────────────────────────────────────────────────────────────────────────────
# Avatar rendering helpers

def _initials(text: str) -> str:
    parts = [p.strip() for p in text.split() if p.strip()]
    if not parts:
        return "U"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()

def _initials_avatar_png(initials: str, size: int = 40) -> bytes:
    img = Image.new("RGBA", (size, size), (240, 243, 248, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=(210, 216, 226, 255))

    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.43))
    except Exception:
        font = ImageFont.load_default()

    w, h = d.textsize(initials, font=font)
    d.text(((size - w) / 2, (size - h) / 2), initials, fill=(30, 41, 59, 255), font=font)

    bio = BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()

def _image_bytes_to_circle_png(img_bytes: bytes, size: int = 40) -> bytes:
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    w, h = img.size
    m = min(w, h)
    left = (w - m) // 2
    top = (h - m) // 2
    img = img.crop((left, top, left + m, top + m)).resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)

    bio = BytesIO()
    out.save(bio, format="PNG")
    return bio.getvalue()

# ──────────────────────────────────────────────────────────────────────────────

def render_avatar_menu() -> None:
    """
    Renders a right-aligned avatar that opens a tiny dropdown with ONLY:
      - My Profile  → Settings > UAM > Users Directory
      - Sign out    → Home_Landing.py
    """
    user = _get_auth_user_from_session()
    if not user:
        return  # No avatar if not logged in (safety)

    display_name = user.display_name or "User"
    photo_png = None

    if user.photo_bytes:
        try:
            photo_png = _image_bytes_to_circle_png(user.photo_bytes, size=40)
        except Exception:
            photo_png = None

    if not photo_png:
        photo_png = _initials_avatar_png(_initials(display_name), size=40)

    # Right-aligned simple layout
    cols = st.columns([1, "auto"])
    with cols[-1]:
        # Prefer popover if present; fallback to inline toggle
        try:
            with st.popover(label="", use_container_width=False, help="Account"):
                st.image(photo_png, width=40)
                st.button("👤  My Profile", key="menu_my_profile",
                          use_container_width=True, on_click=go_settings_users_directory)
                st.button("↩️  Sign out", key="menu_sign_out",
                          use_container_width=True,
                          on_click=lambda: _sign_out_and_go_home())
        except Exception:
            if st.button(" ", key="avatar_btn", help=display_name):
                st.session_state["__avatar_open__"] = not st.session_state.get("__avatar_open__", False)
            else:
                st.session_state.setdefault("__avatar_open__", False)

            st.image(photo_png, width=40)
            if st.session_state["__avatar_open__"]:
                st.button("👤  My Profile", key="menu_my_profile_fallback",
                          on_click=go_settings_users_directory)
                st.button("↩️  Sign out", key="menu_sign_out_fallback",
                          on_click=lambda: _sign_out_and_go_home())

def _sign_out_and_go_home() -> None:
    # Clear only auth state (stay safe)
    st.session_state.pop("auth_user", None)
    go_same_window_to_page("Home_Landing.py")
