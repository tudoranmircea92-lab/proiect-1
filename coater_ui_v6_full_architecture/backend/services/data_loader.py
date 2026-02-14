from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


@dataclass
class DataRepository:
    dataset_path: Path

    def load(self) -> pd.DataFrame:
        if not self.dataset_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.dataset_path)

    def filter_context(
        self,
        df: pd.DataFrame,
        product: str,
        day: Optional[str] = None,
        plates: Optional[Iterable[str]] = None,
    ) -> pd.DataFrame:
        if df.empty:
            return df
        filtered = df[df["product"] == product] if "product" in df.columns else df
        if day and "day" in filtered.columns:
            filtered = filtered[filtered["day"] == day]
        if plates and "plate_id" in filtered.columns:
            filtered = filtered[filtered["plate_id"].isin(list(plates))]
        return filtered
