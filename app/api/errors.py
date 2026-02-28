from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


def api_error(
    *,
    code: str,
    message: str,
    details: Any | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details,
        },
    )
