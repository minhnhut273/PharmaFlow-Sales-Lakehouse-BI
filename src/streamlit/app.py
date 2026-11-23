"""Main multipage entry point for PharmaFlow BI Streamlit Dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from components.filters import render_sidebar_and_get_filters  # noqa: E402

st.set_page_config(
    page_title="PharmaFlow BI — Bán lẻ Dược phẩm & Thời tiết",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/01_tong_quan.py", title="Cửa Hàng & Mặt Hàng", icon="🏪", url_path="tong-quan", default=True),
    st.Page("pages/03_cua_hang_loi_nhuan.py", title="Cụm CH & Bản Đồ", icon="🗺️", url_path="cua-hang-loi-nhuan"),
    st.Page("pages/02_thoi_tiet_dia_diem.py", title="Thời Tiết & Mùa Vụ", icon="🌦️", url_path="thoi-tiet-dia-diem"),
    st.Page("pages/04_san_pham_atc.py", title="So Sánh Kỳ & Danh Mục", icon="⚡", url_path="san-pham-atc"),
    st.Page("pages/05_du_bao_nhu_cau.py", title="Dự Báo Nhu Cầu (ML)", icon="📈", url_path="du-bao-nhu-cau"),
]

nav = st.navigation(pages, position="sidebar")
st.session_state["_active_filters"] = render_sidebar_and_get_filters()
nav.run()
