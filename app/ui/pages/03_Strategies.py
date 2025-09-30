# Top of file (before 'import t18_common')
import sys
from pathlib import Path

ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from app.ui.shell.app_shell import render_page

def _body():
    st.write('Strategies + RR Profiles placeholders.')

if __name__ == '__main__':
    render_page('Strategies', _body)
