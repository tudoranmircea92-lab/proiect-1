from __future__ import annotations

import streamlit as st


def render_compare_page(rows: list[dict]):
    st.subheader("Compare plates")
    if not rows:
        st.info("No compare data available.")
        return
    st.dataframe(rows, use_container_width=True)
