from __future__ import annotations

import streamlit as st


def render_monitor_page(anomalies: list[dict], causes: list[str]):
    st.subheader("Monitor / RCA")
    st.write("Top anomalies")
    st.dataframe(anomalies, use_container_width=True)
    st.write("Likely root causes")
    for cause in causes:
        st.write(f"- {cause}")
