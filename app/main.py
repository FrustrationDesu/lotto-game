from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.games import router as games_router
from app.api.schemas import ErrorResponse

app = FastAPI(title="Lotto Game API", version="1.0.0")
app.include_router(games_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    error = ErrorResponse(
        code="validation_error",
        message="Некорректные входные данные",
        details=exc.errors(),
    )
    return JSONResponse(status_code=422, content=error.model_dump())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message"}.issubset(exc.detail.keys()):
        payload = ErrorResponse(
            code=exc.detail["code"],
            message=exc.detail["message"],
            details=exc.detail.get("details"),
        )
    else:
        payload = ErrorResponse(code="http_error", message=str(exc.detail), details=None)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
