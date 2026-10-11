"""FastAPI application: ``python -m uvicorn qmint.api.app:app --port 8787``.

All routes live under ``/api/v1``. Every error (validation, HTTP, internal) uses the
:class:`~qmint.api.schemas.ApiError` body.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .common import API_VERSION
from .routes import benchmarks, certificates, evidence, lab, meta, protocols, research
from .schemas import ApiError, ApiErrorBody

PREFIX = "/api/v1"
log = logging.getLogger("qmint.api")


def _error(status: int, code: str, message: str, detail: object = None) -> JSONResponse:
    body = ApiError(error=ApiErrorBody(code=code, message=message, detail=jsonable_encoder(detail)))
    return JSONResponse(status_code=status, content=body.model_dump())


def create_app() -> FastAPI:
    app = FastAPI(
        title="QMint Research API",
        version=API_VERSION,
        description="Evidence-labelled research API over merged QMint lanes. Research platform only: "
        "not money, not a payment service.",
        separate_input_output_schemas=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "validation_error", "request validation failed", exc.errors())

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 422: "validation_error"}.get(exc.status_code, "http_error")
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _internal(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled API error")
        return _error(500, "internal_error", f"{type(exc).__name__}: {exc}")

    for r in (meta, protocols, lab, benchmarks, certificates, research, evidence):
        app.include_router(r.router, prefix=PREFIX)
    return app


app = create_app()
