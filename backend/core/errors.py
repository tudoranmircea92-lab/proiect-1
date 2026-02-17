from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


class PlasmaApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PlasmaApiError)
    async def _plasma_api_error_handler(_: Request, exc: PlasmaApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "PLASMA_VALIDATION_ERROR",
                "Request validation failed",
                {
                    "url": str(request.url),
                    "hint": "Check request payload fields and formats",
                    "issues": exc.errors(),
                },
            ),
        )
