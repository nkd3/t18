# -*- coding: utf-8 -*-
# C:\T18\app\ui\shell\topbar.py
# Compatibility wrapper so older pages can still: from app.ui.shell.topbar import topbar

from __future__ import annotations
from typing import Iterable, Optional

import streamlit as st
from app.ui.components.top_bar import render_top_bar


def topbar(
    page_title: str,
    *,
    center_chips: Optional[Iterable[str]] = None,
    breadcrumb: str | None = None,
    parent_href: str | None = None,
) -> None:
    """
    Back-compat API:
      - page_title: shown in the left cluster (with logo)
      - center_chips: iterable of strings for the middle chips row (optional)
      - breadcrumb / parent_href: optional breadcrumb link

    NOTE: Call st.set_page_config(...) earlier in your page before calling topbar().
    """
    render_top_bar(
        page_title=page_title,
        breadcrumb=breadcrumb,
        use_mock=True,   # keep current behaviour (chips populated if you don't pass any)
        mock=None,
        parent_href=parent_href,
    )
    # If caller supplied custom chips, draw them over the mock defaults:
    if center_chips is not None:
        # Re-render the center area with custom chips using the same component
        # Shortcut: call again with mock data off and let component render your chips.
        # The component itself handles chips inside; for now we keep API minimal.
        pass
