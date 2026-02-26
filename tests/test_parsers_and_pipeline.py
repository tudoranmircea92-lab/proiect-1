from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from live_db.build_operational import build_compartment_state, build_optics_summary
from live_db.config import DEFAULT_DEVICE_MAP, DEFAULT_GAS_MAP, DEFAULT_MATERIAL_MAP, DEFAULT_ZONE_MAP
from live_db.pairing import choose_best_process_candidate
from live_db.parse_optoplex import parse_optoplex_file
from live_db.parse_process import parse_process_file
from live_db.store import DuckStore
from live_db.config import LiveDBConfig
from scripts.run_live_db import create_or_replace_training_view, dedupe_rows, run_once, should_process_file, today_folder, validate_db_path


def test_parse_process_and_segments(tmp_path: Path):
    p = tmp_path / "20260224002703_8345_glassFile.csv"
    p.write_text(
        "glassId;Location;status;nomPower;actPower;nomCurrent;actCurrent;nomVoltage;actVoltage;actVacuumPressure;nomMainGas1;actMainGas1;nomMainGas2;actMainGas2;nomMainGas3;actMainGas3;nomRampGas1;actRampGas1;nomRampGas2;actRampGas2;nomRampGas3;actRampGas3;nomGasSegment;nomSegGasType;Seg1;Seg2;Seg3;Seg4;Seg5;product\n"
        "8345;Compartment-1;on;10;12;5;5.5;100;99;0.003;1;1.1;2;2.2;3;3.3;0.5;0.4;0.2;0.1;0.3;0.2;5;O2;1;2;3;4;5;P1\n",
        encoding="utf-8",
    )
    rows, core = parse_process_file(p)
    assert rows[0]["seg_sum"] == 15
    assert rows[0]["seg_active_count"] == 5
    assert core["plate"] == "8345"
    assert rows[0]["Location"] == 1


def test_parse_optoplex_and_summary_dynamic_positions(tmp_path: Path):
    p = tmp_path / "2026-02-24-00-25-28_Plate-8345.csv"
    p.write_text(
        "Meta;X\n"
        "Measurement Values;;;;;;;;;;;;;;;;;;;;;;\n"
        "stamp;plate;device;position;Y;;L*;;a*;;b*;;RT Glass;Resistance;Distance\n"
        "2026-02-24 00:25:28;8345;Transmission;1;0;;20;;1;;2;;3;100;0\n"
        "2026-02-24 00:25:29;8345;Transmission;2;0;;21;;1;;2.5;;3;110;0\n"
        "2026-02-24 00:25:30;8345;NAGY Measurement Unit;3;0;;22;;1;;3;;3;120;0\n"
        "Spectrum\n"
        "x;y;z\n",
        encoding="utf-8",
    )
    rows, meta = parse_optoplex_file(p, DEFAULT_DEVICE_MAP)
    assert len(rows) == 3
    summary = build_optics_summary(rows, meta["event_time"])[0]
    assert "T_b_edge_center_delta" in summary
    assert summary["NAGY_resistance_mean"] == 120


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
    assert "row_idx" in comp[0]


def test_training_view_no_crash_on_empty_db(tmp_path: Path):
    db = DuckStore(tmp_path / "empty.duckdb")
    create_or_replace_training_view(db)
    db.close()


def test_validate_db_path(tmp_path: Path):
    with pytest.raises(ValueError):
        validate_db_path(tmp_path)
    validate_db_path(tmp_path / "ok.duckdb")


def test_today_folder_and_ingested_files(tmp_path: Path):
    base = tmp_path / "root"
    t = today_folder(base, date(2026, 2, 26))
    assert str(t).endswith("2026/02/26")

    db = DuckStore(tmp_path / "z.duckdb")
    f = tmp_path / "x.csv"
    f.write_text("a", encoding="utf-8")
    assert should_process_file(db, f) is True
    db.upsert_rows("ingested_files", [{"file_path": str(f), "file_mtime": datetime.fromtimestamp(f.stat().st_mtime), "ingested_at": datetime.utcnow()}], ["file_path"])
    assert should_process_file(db, f) is False
    f.write_text("b", encoding="utf-8")
    assert should_process_file(db, f) is True
    db.close()


def test_fresh_db_bootstrap_no_crash(tmp_path: Path):
    cfg = LiveDBConfig(
        optoplex_dir=tmp_path / "optoplex",
        process_dir=tmp_path / "process",
        db_path=tmp_path / "fresh.duckdb",
        one_shot=True,
    )
    run_once(cfg, date.today())
    db = DuckStore(tmp_path / "fresh.duckdb")
    assert db.conn.execute("select count(*) from plate_core").fetchone()[0] == 0
    db.close()


def test_run_once_extracts_real_rows(tmp_path: Path):
    today = date.today()
    proc_dir = tmp_path / "process" / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
    opt_dir = tmp_path / "optoplex" / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
    proc_dir.mkdir(parents=True)
    opt_dir.mkdir(parents=True)

    process_file = proc_dir / "20260224002703_8345_glassFile.csv"
    process_file.write_text(
        "glassId;Location;status;nomPower;actPower;nomCurrent;actCurrent;nomVoltage;actVoltage;actVacuumPressure;nomMainGas1;actMainGas1;nomMainGas2;actMainGas2;nomMainGas3;actMainGas3;nomRampGas1;actRampGas1;nomRampGas2;actRampGas2;nomRampGas3;actRampGas3;nomGasSegment;nomSegGasType;Seg1;Seg2;Seg3;Seg4;Seg5;product\n"
        "8345;Compartment-1;on;10;12;5;5.5;100;99;0.003;1;1.1;2;2.2;3;3.3;0.5;0.4;0.2;0.1;0.3;0.2;5;O2;1;2;3;4;5;P1\n",
        encoding="utf-8",
    )

    opt_file = opt_dir / "2026-02-24-00-25-28_Plate-8345.csv"
    opt_file.write_text(
        "Measurement Values;;;;;;;;;;;;;;;;;;;;;;\n"
        "stamp;plate;device;position;Y;;L*;;a*;;b*;;RT Glass;Resistance;Distance\n"
        "2026-02-24 00:25:28;8345;Transmission;1;0;;20;;1;;2;;3;100;0\n"
        "2026-02-24 00:25:29;8345;Transmission;2;0;;21;;1;;2.5;;3;110;0\n"
        "Spectrum\n",
        encoding="utf-8",
    )

    cfg = LiveDBConfig(
        optoplex_dir=tmp_path / "optoplex",
        process_dir=tmp_path / "process",
        db_path=tmp_path / "live.duckdb",
        one_shot=True,
    )
    run_once(cfg, today)

    db = DuckStore(tmp_path / "live.duckdb")
    assert db.conn.execute("select count(*) from raw_process_long").fetchone()[0] >= 1
    assert db.conn.execute("select count(*) from raw_optoplex_long").fetchone()[0] >= 1
    plate = db.conn.execute("select has_process, process_source_file from plate_core where plate='8345' limit 1").fetchone()
    assert plate[0] is True
    assert str(process_file) in plate[1]
    db.close()


def test_dedupe_rows_on_raw_process_key():
    rows = [
        {"plate": "1", "event_time": datetime(2026, 1, 1), "Location": 0, "row_idx": 1, "x": 1},
        {"plate": "1", "event_time": datetime(2026, 1, 1), "Location": 0, "row_idx": 1, "x": 2},
        {"plate": "1", "event_time": datetime(2026, 1, 1), "Location": 0, "row_idx": 2, "x": 3},
    ]
    out = dedupe_rows(rows, ["plate", "event_time", "Location", "row_idx"])
    assert len(out) == 2


def test_failed_file_not_marked_ingested_and_next_file_continues(tmp_path: Path):
    today = date.today()
    proc_dir = tmp_path / "process" / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
    opt_dir = tmp_path / "optoplex" / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
    proc_dir.mkdir(parents=True)
    opt_dir.mkdir(parents=True)

    bad = proc_dir / "20260224002703_8345_glassFile.csv"
    bad.write_text("broken;csv\n", encoding="utf-8")

    good = opt_dir / "2026-02-24-00-25-28_Plate-8345.csv"
    good.write_text("Measurement Values\nstamp;plate;device;position;Y;;L*;;a*;;b*;;RT Glass;Resistance;Distance\n2026-02-24 00:25:28;8345;Transmission;1;0;;20;;1;;2;;3;100;0\nSpectrum\n", encoding="utf-8")

    cfg = LiveDBConfig(
        optoplex_dir=tmp_path / "optoplex",
        process_dir=tmp_path / "process",
        db_path=tmp_path / "cont.duckdb",
        one_shot=True,
    )
    run_once(cfg, today)

    db = DuckStore(tmp_path / "cont.duckdb")
    failed_status = db.conn.execute("select status from file_registry where full_path=?", [str(bad)]).fetchone()[0]
    assert failed_status == "failed"
    bad_mark = db.conn.execute("select count(*) from ingested_files where file_path=?", [str(bad)]).fetchone()[0]
    assert bad_mark == 0
    good_mark = db.conn.execute("select count(*) from ingested_files where file_path=?", [str(good)]).fetchone()[0]
    assert good_mark == 1
    db.close()


def test_compartment_state_dedupe_key_includes_row_idx():
    rows = [
        {"plate": "1", "event_time": datetime(2026, 1, 1), "Location": 0, "row_idx": 1},
        {"plate": "1", "event_time": datetime(2026, 1, 1), "Location": 0, "row_idx": 1},
        {"plate": "1", "event_time": datetime(2026, 1, 1), "Location": 0, "row_idx": 2},
    ]
    out = dedupe_rows(rows, ["plate", "event_time", "Location", "row_idx"])
    assert len(out) == 2
