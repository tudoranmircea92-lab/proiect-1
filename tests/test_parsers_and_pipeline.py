from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from live_db.build_operational import build_compartment_state, build_optics_summary
from live_db.config import DEFAULT_DEVICE_MAP, DEFAULT_GAS_MAP, DEFAULT_MATERIAL_MAP, DEFAULT_ZONE_MAP
from live_db.pairing import choose_best_process_candidate
from live_db.parse_optoplex import parse_optoplex_file
from live_db.parse_process import parse_process_file
from live_db.store import DuckStore


def test_parse_process_and_segments(tmp_path: Path):
    p = tmp_path / "20260224002703_8345_glassFile.csv"
    p.write_text(
        "glassId;Location;status;nomPower;actPower;nomCurrent;actCurrent;nomVoltage;actVoltage;actVacuumPressure;nomMainGas1;actMainGas1;nomMainGas2;actMainGas2;nomMainGas3;actMainGas3;nomRampGas1;actRampGas1;nomRampGas2;actRampGas2;nomRampGas3;actRampGas3;nomGasSegment;nomSegGasType;Seg1;Seg2;Seg3;Seg4;Seg5;product\n"
        "8345;1;on;10;12;5;5.5;100;99;0.003;1;1.1;2;2.2;3;3.3;0.5;0.4;0.2;0.1;0.3;0.2;5;O2;1;2;3;4;5;P1\n",
        encoding="utf-8",
    )
    rows, core = parse_process_file(p)
    assert rows[0]["seg_sum"] == 15
    assert rows[0]["seg_active_count"] == 5
    assert core["plate"] == "8345"


def test_parse_optoplex_and_summary_dynamic_positions(tmp_path: Path):
    p = tmp_path / "2026-02-24-00-25-28_Plate-8345.csv"
    p.write_text(
        "Reflection Glass\n"
        "1;0;10;1;2;3;0;0;0\n"
        "2;0;11;1;2;3;0;0;0\n"
        "Transmission\n"
        "1;0;20;1;2;3;0;0;0\n"
        "2;0;21;1;2.5;3;0;0;0\n"
        "3;0;22;1;3;3;0;0;0\n"
        "4;0;23;1;3.5;3;0;0;0\n"
        "NAGY Measurement Unit\n"
        "1;0;20;1;2;3;100;0;0\n"
        "2;0;20;1;2;3;110;0;0\n"
        "Spectrum A\n"
        "1;2;3\n",
        encoding="utf-8",
    )
    rows, meta = parse_optoplex_file(p, DEFAULT_DEVICE_MAP)
    assert len(rows) == 8
    summary = build_optics_summary(rows, meta["event_time"])[0]
    assert "T_b_edge_center_delta" in summary
    assert summary["NAGY_resistance_mean"] == 105


def test_matching():
    cands = [{"event_time": datetime(2026, 1, 1, 10, 0)}, {"event_time": datetime(2026, 1, 1, 10, 5)}]
    best = choose_best_process_candidate(cands, datetime(2026, 1, 1, 10, 4))
    assert best["event_time"] == datetime(2026, 1, 1, 10, 5)


def test_upsert_and_orphans(tmp_path: Path):
    db = DuckStore(tmp_path / "x.duckdb")
    db.upsert_rows("file_registry", [{"full_path": "a", "file_type": "process", "file_size": 1, "file_mtime": datetime.utcnow(), "status": "processed", "error_text": None, "processed_at": datetime.utcnow()}], ["full_path"])
    db.upsert_rows("file_registry", [{"full_path": "a", "file_type": "process", "file_size": 2, "file_mtime": datetime.utcnow(), "status": "processed", "error_text": None, "processed_at": datetime.utcnow()}], ["full_path"])
    size = db.conn.execute("select file_size from file_registry where full_path='a'").fetchone()[0]
    assert size == 2

    db.upsert_rows("orphan_optoplex", [{"plate": "8345", "optoplex_file_time": datetime.utcnow(), "full_path": "c", "status": "pending", "created_at": datetime.utcnow(), "matched_event_time": None}], ["plate", "optoplex_file_time"])
    cnt = db.conn.execute("select count(*) from orphan_optoplex where status='pending'").fetchone()[0]
    assert cnt == 1
    db.close()


def test_compartment_aggregation():
    rows = [{"plate": "1", "event_time": datetime.utcnow(), "Location": 1, "material_raw": "Ag", "nomPower": 1, "actPower": 2, "deltaPower": 1, "nomCurrent": 1, "actCurrent": 1, "deltaCurrent": 0, "nomVoltage": 10, "actVoltage": 11, "deltaVoltage": 1, "actVacuumPressure": 0.002, "nomGasSegment": 5, "nomSegGasType": "O2", "seg_sum": 3, "seg_mean": 1, "seg_max": 2, "seg_range": 1, "seg_active_count": 2,
             "nomMainGas1":1,"actMainGas1":1,"deltaMainGas1":0,"nomMainGas2":1,"actMainGas2":1,"deltaMainGas2":0,"nomMainGas3":1,"actMainGas3":2,"deltaMainGas3":1,
             "nomRampGas1":1,"actRampGas1":1,"deltaRampGas1":0,"nomRampGas2":1,"actRampGas2":1,"deltaRampGas2":0,"nomRampGas3":1,"actRampGas3":1,"deltaRampGas3":0}]
    comp = build_compartment_state(rows, DEFAULT_ZONE_MAP["default"], DEFAULT_MATERIAL_MAP, DEFAULT_GAS_MAP)
    assert comp[0]["seg_gas_family"] == "reactive_oxidation"
