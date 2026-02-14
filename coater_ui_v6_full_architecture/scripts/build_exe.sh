#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install pyinstaller

pyinstaller \
  --onefile \
  --name coater_optimizer.exe \
  --add-data "coater_ui_v6_full_architecture/backend/static:coater_ui_v6_full_architecture/backend/static" \
  coater_ui_v6_full_architecture/run_optimizer_app.py

echo "Built executable at: dist/coater_optimizer.exe"
