from __future__ import annotations

import sys
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.api import routes
    from app.main import app
    from app.services.data_repository import DataRepository
    from app.services.job_service import JobService
    from app.services.optimization_service import OptimizationService
    from app.services.training_service import TrainingService

    trainer = TrainingService()
    trainer.artifacts_root = tmp_path / "runs"
    trainer.artifacts_root.mkdir(parents=True, exist_ok=True)
    repo = DataRepository()
    jobs = JobService()
    optimizer = OptimizationService(trainer, repo)

    monkeypatch.setattr(routes, "trainer", trainer, raising=False)
    monkeypatch.setattr(routes, "repo", repo, raising=False)
    monkeypatch.setattr(routes, "jobs", jobs, raising=False)
    monkeypatch.setattr(routes, "optimizer", optimizer, raising=False)

    return TestClient(app)


def _make_base_rows(n=80):
    rows = []
    for i in range(n):
        row = {
            "plate": f"PLT-{i//2}",
            "file_ts": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=i),
            "product": "P1" if i % 2 == 0 else "P2",
            "thickness": "4",
            "actProcessSpeed_mm": 120 + (i % 5),
            "main1": 4.0 + 0.01 * i,
            "main2": 3.0 + 0.01 * i,
            "main3": 2.0 + 0.005 * i,
            "c1.on": 1,
            "c2.on": 1,
            "c3.on": 0,
            "c1.pwr": 10 + 0.1 * np.sin(i),
            "c2.pwr": 8 + 0.1 * np.cos(i),
            "c3.pwr": 2.5,  # OFF cathode with nonzero power to test filtering
            "c1.power_mean": 10 + 0.1 * np.sin(i),
            "c2.power_mean": 8 + 0.1 * np.cos(i),
            "c3.power_mean": 2.5,
            "c1.mainGas1": 1.0 + 0.01 * np.sin(i),
            "c2.mainGas1": 1.2 + 0.01 * np.cos(i),
            "c3.mainGas1": 0.4,
            "c1.mainGas2": 0.9 + 0.01 * np.sin(i),
            "c2.mainGas2": 1.1 + 0.01 * np.cos(i),
            "c3.mainGas2": 0.3,
            "c1.mainGas3": 0.8 + 0.01 * np.sin(i),
            "c2.mainGas3": 1.0 + 0.01 * np.cos(i),
            "c3.mainGas3": 0.2,
            "c1.s1g": 0.2 + 0.005 * np.sin(i),
            "c1.s2g": 0.2 + 0.005 * np.cos(i),
            "c2.s1g": 0.25 + 0.005 * np.sin(i),
            "c2.s2g": 0.25 + 0.005 * np.cos(i),
        }
        for p in range(1, 10):
            a = 3.0 + 0.08 * np.sin(i + p)
            b = -2.0 + 0.08 * np.cos(i + p)
            if i == 10 and p == 9:
                a = 7.8  # outlier
            if i == 12 and p == 7:
                b = np.nan  # missing position
            row[f"a_RG_p{p}"] = a
            row[f"b_RG_p{p}"] = b
        for dev in ["RG", "RF", "T"]:
            row[f"L_{dev}_mean"] = 50 + 0.1 * np.sin(i)
            row[f"a_{dev}_mean"] = 3 + 0.1 * np.sin(i)
            row[f"b_{dev}_mean"] = -2 + 0.1 * np.cos(i)
            row[f"L_{dev}_std"] = 0.4 + 0.02 * np.cos(i)
            row[f"a_{dev}_std"] = 0.3 + 0.02 * np.sin(i)
            row[f"b_{dev}_std"] = 0.35 + 0.02 * np.cos(i)
        rows.append(row)
    return rows


@pytest.fixture()
def dataset_by_cathode(tmp_path):
    df = pd.DataFrame(_make_base_rows(90))
    path = tmp_path / "dataset_by_cathode.csv"
    df.to_csv(path, index=False)
    return path, df


@pytest.fixture()
def dataset_by_segment(tmp_path):
    df = pd.DataFrame(_make_base_rows(90))
    for c in [x for x in df.columns if x.startswith('c1.mainGas') or x.startswith('c2.mainGas') or x.startswith('c3.mainGas')]:
        df.drop(columns=[c], inplace=True)
    df["seg1.main1"] = 0.6
    df["seg1.main2"] = 0.5
    df["seg2.main1"] = 0.7
    df["seg2.main2"] = 0.6
    path = tmp_path / "dataset_by_segment.csv"
    df.to_csv(path, index=False)
    return path, df


@pytest.fixture()
def wait_job(client):
    def _wait(job_id: str, max_iter: int = 2000):
        for _ in range(max_iter):
            r = client.get(f"/api/jobs/{job_id}")
            data = r.json()
            if data["status"] in {"done", "error", "failed"}:
                return data
            time.sleep(0.02)
        raise AssertionError(f"job {job_id} did not finish")

    return _wait


@pytest.fixture()
def trained_dataset(client, wait_job, dataset_by_cathode):
    path, _ = dataset_by_cathode
    res = client.post("/api/data/load", json={"path": str(path), "format": "csv"})
    load_job = wait_job(res.json()["job_id"])
    assert load_job["status"] == "done", load_job
    dataset_id = load_job["result"]["dataset_id"]

    train_payload = {
        "dataset_id": dataset_id,
        "config": {
            "estimator_type": "hist_gradient_boosting",
            "training_mode": "fast",
            "split": {"method": "time", "ratio": 0.8, "random_seed": 42, "stratify_by_product": False},
            "features": {
                "include_power": True,
                "include_main_gas": True,
                "include_main_gas_alt": True,
                "include_segment_gas": True,
                "include_context_numeric": True,
                "include_context_categorical": True,
                "include_context_keyword_allowlist": True,
            },
        },
    }
    tr = client.post("/api/train", json=train_payload)
    train_job = wait_job(tr.json()["job_id"])
    assert train_job["status"] == "done", train_job
    return dataset_id, train_job["result"]
