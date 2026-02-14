from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn


def start_server() -> None:
    uvicorn.run(
        "coater_ui_v6_full_architecture.backend.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:8000")
    thread.join()
