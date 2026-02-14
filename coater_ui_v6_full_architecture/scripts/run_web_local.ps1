Set-Location "$PSScriptRoot\..\.."
Start-Process "http://localhost:8000"
python -m uvicorn coater_ui_v6_full_architecture.backend.app:app --host 0.0.0.0 --port 8000
