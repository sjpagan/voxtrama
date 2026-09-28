"""Request-side failures, rendered as application/problem+json.

Only a route can know it failed the request rather than the work it started
(the central distinction of the error model), so the exception is raised there and
translated here, once, instead of every route formatting its own body.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ProblemException(Exception):
    """A request that cannot be satisfied: bad input, missing resource, and so on."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        title: str,
        detail: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.title = title
        self.detail = detail
        # 416 needs Content-Range on the error itself (RFC 9110); most
        # callers have nothing extra to say here, hence the empty default.
        self.headers = headers or {}


def _problem_response(request: Request, exc: ProblemException) -> JSONResponse:
    """Render `exc` as the RFC 9457 body every request failure shares."""
    body = {
        "type": f"https://voxtrama.dev/errors/{exc.code.replace('_', '-')}",
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "instance": request.url.path,
        "code": exc.code,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        media_type="application/problem+json",
        headers=exc.headers,
    )


def _as_problem(exc: RequestValidationError) -> ProblemException:
    """Turn FastAPI's own validation error into the ProblemException every route raises by hand.

    FastAPI answers a malformed query, path, or body parameter itself, before
    a route ever runs: the same check a route would otherwise write with
    ProblemException. Without this, that path produces a plain
    application/json body with no `code`: a second error shape next to
    every one raised by hand (the closed error taxonomy would not hold).

    Neither a stack trace nor the value received in full reaches `detail`,
    for the same reason neither is allowed on an `internal` error.
    """
    summary = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
    )
    return ProblemException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_failed",
        title="The request does not match the expected schema",
        detail=summary,
    )


def register_problem_handler(app: FastAPI) -> None:
    """Register the handlers that turn a request failure into RFC 9457 JSON."""

    @app.exception_handler(ProblemException)
    def _handle_problem(request: Request, exc: ProblemException) -> JSONResponse:
        return _problem_response(request, exc)

    @app.exception_handler(RequestValidationError)
    def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem_response(request, _as_problem(exc))
