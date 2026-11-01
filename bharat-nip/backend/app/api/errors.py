"""RFC 9457 problem+json error responses (API_DESIGN.md §1)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.state import InvalidTransition
from app.schemas.problem import Problem
from app.services.errors import DomainError

PROBLEM_BASE = "https://bnip.local/problems/"
MEDIA_TYPE = "application/problem+json"


def _problem(
    request: Request, status: int, title: str, detail: str | None, **extra
) -> JSONResponse:
    body = Problem(
        type=extra.pop("type", "about:blank"),
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        **extra,
    )
    return JSONResponse(
        status_code=status,
        content=jsonable_encoder(body.model_dump(exclude_none=True)),
        media_type=MEDIA_TYPE,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = {401: "Unauthorized", 403: "Forbidden", 404: "Not Found"}.get(
            exc.status_code, "HTTP error"
        )
        return _problem(request, exc.status_code, title, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return _problem(
            request,
            422,
            "Validation error",
            "The request did not match the expected schema.",
            type=PROBLEM_BASE + "validation",
            errors=errors,
        )

    @app.exception_handler(InvalidTransition)
    async def invalid_transition(request: Request, exc: InvalidTransition) -> JSONResponse:
        return _problem(
            request,
            409,
            "Invalid state transition",
            str(exc),
            type=PROBLEM_BASE + "invalid-transition",
        )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(request, exc.status_code, exc.title, exc.detail)
