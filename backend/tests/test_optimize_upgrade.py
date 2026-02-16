from __future__ import annotations

import pandas as pd

from app.models.schemas import OptimizeRequest
from app.services.data_repository import DataRepository
from app.services.optimization_service import OptimizationService
from app.services.training_service import TrainingService


def test_knob_schema_discovery_by_cathode():
    df = pd.DataFrame(
        {
            "c1.pwr": [10, 11],
            "c1.on": [1, 1],
            "c2.pwr": [0, 0],
            "c2.on": [0, 0],
            "mainGas1": [5, 5],
            "mainGas2": [7, 7],
            "c1.mainGas1": [1, 1],
            "c2.mainGas1": [2, 2],
            "a_RG_p1": [3, 3],
            "b_RG_p1": [-2, -2],
        }
    )
    repo = DataRepository()
    schema = repo.discover_knob_schema(df, row=df.iloc[0])
    assert schema["gases_segmented"]["mode"] == "by_cathode"
    assert "main1" in schema["gases_main"]["keys"]
    c1 = next(c for c in schema["cathodes"] if c["id"] == "c1")
    assert c1["on"] is True


def test_optimize_request_new_fields_validation():
    req = OptimizeRequest(dataset_id="d1", targets={"b": -2})
    assert req.guardrails.on_only_cathodes is True
    assert req.measurement.source in {"last_plate", "median_n", "stable_window"}


def test_coupling_enforcement():
    svc = OptimizationService(TrainingService(), DataRepository())
    req = OptimizeRequest(dataset_id="d1", targets={"b": -2})
    req.strategy.gas_coupling = "segmented_le_main"
    knob_schema = {
        "gases_main": {"cols": {"main1": "mainGas1"}},
        "gases_segmented": {"cols": {"c1": {"main1": "c1.mainGas1"}}},
    }
    cand = {"mainGas1": 4.0, "c1.mainGas1": 9.0}
    ranges = {"mainGas1": (0.0, 10.0), "c1.mainGas1": (0.0, 10.0)}
    svc._enforce_coupling(cand, req, knob_schema, ranges)
    assert cand["c1.mainGas1"] <= cand["mainGas1"]


def test_in_spec_violations():
    svc = OptimizationService(TrainingService(), DataRepository())
    req = OptimizeRequest(dataset_id="d1", targets={"b": -2})
    violations = svc._violations([1, 2, 3], [-2, -3, 1], req)
    assert any(v["metric"] == "a" for v in violations)
    assert any(v["metric"] == "b" for v in violations)
