from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from backend.app.main import app
from backend.app.core import get_importance, scan_files, train_model
from backend.app.services.dataset_service import load_datasets, resolve_paths


if __name__ == '__main__':
    print('OK: app import succeeded')
    print('OK: core exports resolved', callable(scan_files), callable(train_model), callable(get_importance))
    print('OK: dataset_service imports resolved', callable(load_datasets), callable(resolve_paths))
    print('routes:', len(app.routes))
