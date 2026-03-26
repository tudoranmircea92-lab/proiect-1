from __future__ import annotations

"""Production-oriented Streamlit analysis app entrypoint."""

from pathlib import Path

import streamlit as st

from analytics.compare import compare_feature_maps
from analytics.root_cause import likely_root_causes
from services.monitor_service import top_anomalies
from ui.compare_page import render_compare_page
from ui.monitor_page import render_monitor_page
from ui.plate_page import render_plate_page
from ui.search_page import render_search_page


st.set_page_config(page_title="Glass Coating Analysis", layout="wide")
st.title("Industrial Glass Coating Analysis")

if "demo_plate" not in st.session_state:
    st.session_state["demo_plate"] = {
        "plate_id": "15860",
        "process": {"matched": True},
        "optoplex": {"matched": True},
        "lambda": {"matched": False},
    }

nav = st.sidebar.radio("Section", ["Search", "Plate", "Compare", "Monitor"], key="nav_section")
state = {"days": ["2026-03-24", "2026-03-25", "2026-03-26"], "cache_root": str(Path("C:/db/cache_fast"))}

if nav == "Search":
    render_search_page(state)
elif nav == "Plate":
    render_plate_page(st.session_state.get("demo_plate") or {})
elif nav == "Compare":
    good = {"critical_deltaPower_mean": 0.1, "split_power_c62_c63": 1.01}
    bad = {"critical_deltaPower_mean": 2.3, "split_power_c62_c63": 0.82}
    render_compare_page(compare_feature_maps(good, bad))
else:
    plate_scores = [
        {"plate_id": "15860", "anomaly_score": 0.22},
        {"plate_id": "15861", "anomaly_score": 0.81},
        {"plate_id": "15862", "anomaly_score": 0.45},
    ]
    anomalies = top_anomalies(plate_scores)
    render_monitor_page(anomalies, likely_root_causes({"critical_deltaPower_mean": 1.7, "split_power_c62_c63": 0.84}))
