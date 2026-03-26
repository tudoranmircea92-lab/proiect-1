from __future__ import annotations

"""Manifest service to discover process/optoplex/lambda files by date folders."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class FileManifest:
    process: list[Path]
    optoplex: list[Path]
    lambda950: list[Path]


class ManifestService:
    def __init__(self, process_root: Path, optoplex_root: Path, lambda_root: Path):
        self.process_root = process_root
        self.optoplex_root = optoplex_root
        self.lambda_root = lambda_root

    @staticmethod
    def _day_dir(root: Path, day: str) -> Path:
        y, m, d = day.split("-")
        return root / y / m / d

    def list_day(self, day: str) -> FileManifest:
        pdir = self._day_dir(self.process_root, day)
        odir = self._day_dir(self.optoplex_root, day)
        ldir = self._day_dir(self.lambda_root, day)
        return FileManifest(
            process=sorted(pdir.glob("*_glassFile.csv")) if pdir.exists() else [],
            optoplex=sorted(odir.glob("*_Plate-*.csv")) if odir.exists() else [],
            lambda950=sorted([*ldir.glob("*.xml"), *ldir.glob("*.fxml")]) if ldir.exists() else [],
        )
