from __future__ import annotations

import streamlit as st

from ui.shared_components import safe_metric


def render_plate_page(plate: dict):
    st.subheader("Plate overview")
    if not plate:
        st.warning("No plate selected.")
        return
    c1, c2, c3 = st.columns(3)
    with c1:
        safe_metric("Plate", plate.get("plate_id"))
    with c2:
        safe_metric("Process matched", bool(plate.get("process")))
    with c3:
        safe_metric("Optoplex matched", bool(plate.get("optoplex")))
    st.json(plate)
