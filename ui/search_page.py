from __future__ import annotations

import streamlit as st

from ui.shared_components import safe_selectbox


def render_search_page(state: dict):
    st.subheader("Search")
    st.caption("Filter plates by date, id, product, thickness, and source availability.")
    days = state.get("days", [])
    selected_day = safe_selectbox("Date", days, key="search_date")
    st.text_input("Plate ID", key="search_plate")
    st.text_input("Product", key="search_product")
    st.text_input("Thickness", key="search_thickness")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.checkbox("Has process", value=False, key="search_has_process")
    with c2:
        st.checkbox("Has optoplex", value=False, key="search_has_optoplex")
    with c3:
        st.checkbox("Has lambda", value=False, key="search_has_lambda")
    st.write({"selected_day": selected_day})
