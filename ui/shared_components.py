from __future__ import annotations

"""Reusable Streamlit UI components with safe defaults."""

import streamlit as st


def safe_selectbox(label: str, options: list, key: str, index: int = 0):
    if not options:
        st.info(f"No options for {label}.")
        return None
    idx = min(index, len(options) - 1)
    return st.selectbox(label, options, index=idx, key=key)


def safe_metric(label: str, value, delta=None):
    st.metric(label=label, value="-" if value is None else value, delta=delta)
