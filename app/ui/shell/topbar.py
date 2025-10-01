# C:\T18\app\ui\shell\topbar.py
from __future__ import annotations
from typing import Optional, Dict, Any
from app.ui.components.top_bar import render_top_bar as _render_top_bar

def topbar(page_title: str,
           breadcrumb: Optional[str] = None,
           use_mock: bool = True,
           mock: Optional[Dict[str, Any]] = None,
           parent_href: Optional[str] = None) -> None:
    """
    Renders the global Top Bar FIRST on every page/subpage.

    For subpages, pass parent_href to make the title clickable:
        topbar("Settings", breadcrumb="Account & Roles", parent_href="?page=Settings")
    """
    _render_top_bar(page_title=page_title,
                    breadcrumb=breadcrumb,
                    use_mock=use_mock,
                    mock=mock,
                    parent_href=parent_href)
