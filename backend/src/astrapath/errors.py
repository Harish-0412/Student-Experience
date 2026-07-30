from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def error_payload(
    request: Request,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(request, exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for error in exc.errors():
            normalized = dict(error)
            if "ctx" in normalized:
                normalized["ctx"] = {
                    key: str(value) if isinstance(value, Exception) else value
                    for key, value in normalized["ctx"].items()
                }
            details.append(normalized)
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                error_payload(
                    request,
                    "validation_error",
                    "Request validation failed",
                    details,
                )
            ),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, _exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=error_payload(
                request,
                "conflict",
                "The request conflicts with an existing record",
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_payload(
                request,
                "internal_error",
                "The service could not complete the request",
            ),
        )
