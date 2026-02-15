from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("backend/app/data/sample_merged.parquet")


def main() -> None:
    n = 300
    rng = np.random.default_rng(42)
    timestamps = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame(
        {
            "plate": [f"P{i//5:03d}" for i in range(n)],
            "timestamp": timestamps,
            "product_name": rng.choice(["PROD_A", "PROD_B"], size=n),
            "actVacuumPressure": rng.normal(50, 5, n),
            "actProcessSpeed_mm": rng.normal(100, 10, n),
            "nomProcessSpeed_mm": rng.normal(102, 6, n),
            "actFreq": rng.normal(60, 2, n),
        }
    )
    for comp in ["c4", "c5", "c7"]:
        df[f"{comp}.pwr"] = rng.uniform(30, 90, n)
        for g in ["m1g", "m2g", "m3g"]:
            df[f"{comp}.{g}"] = rng.uniform(5, 80, n)
        for i in range(1, 12):
            df[f"{comp}.s{i}g"] = rng.uniform(2, 40, n)
        for suffix in ["voltage", "current", "ppmf", "imf", "umf"]:
            df[f"{comp}.{suffix}"] = rng.uniform(1, 20, n)

    df["L_star_RG_mean"] = 60 + 0.04 * df["c4.pwr"] - 0.02 * df["c5.m1g"] + rng.normal(0, 1, n)
    df["a_star_RG_mean"] = 10 + 0.03 * df["c7.m2g"] - 0.01 * df["actVacuumPressure"] + rng.normal(0, 0.8, n)
    df["b_star_RG_mean"] = 8 + 0.02 * df["c5.pwr"] + 0.01 * df["c4.m3g"] + rng.normal(0, 0.9, n)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, engine="fastparquet")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
