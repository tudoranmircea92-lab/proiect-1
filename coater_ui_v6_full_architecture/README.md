# coater_ui_v6_full_architecture

FastAPI backend + minimal UI for Optimizer workflows.

## Structure

- `backend/app.py` — FastAPI app entrypoint + static UI serving
- `backend/static/index.html` — minimalist web interface
- `backend/config.py` + `backend/config.json` — runtime config loading
- `backend/routers/optimizer_routes.py` — optimizer API endpoints (`/run`, `/verify`)
- `backend/services/` — data, feature, train, optimizer, model registry services
- `backend/utils/logging.py` — logger helper
- `run_optimizer_app.py` — launcher that starts server and opens browser
- `scripts/build_exe.sh` — builds one-file executable with PyInstaller

## Run locally

```bash
python -m pip install -r coater_ui_v6_full_architecture/requirements.txt
python coater_ui_v6_full_architecture/run_optimizer_app.py
```

Then open `http://127.0.0.1:8000`.

## Build executable

```bash
bash coater_ui_v6_full_architecture/scripts/build_exe.sh
```

Executable output:
- `dist/coater_optimizer.exe`

> Note: the generated executable format depends on the build OS.
> Building on Linux produces a Linux executable (even if named `.exe`).
> For a native Windows `.exe`, run the build script on Windows.

## Executabil inclus

- `dist/coater_optimizer.exe` (launcher local)
- Rulează direct: `./dist/coater_optimizer.exe`

Acest launcher deschide interfața GUI minimală (`tkinter`) fără dependințe externe.
