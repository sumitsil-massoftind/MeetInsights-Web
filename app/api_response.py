"""Standard JSON API response envelope."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def api_payload(
    data: Any = None,
    *,
    msg: str = "Success",
    action_status: bool = True,
) -> dict[str, Any]:
    return {
        "response": {
            "data": {} if data is None else data,
            "status": {
                "msg": msg,
                "action_status": action_status,
            },
        }
    }


def api_success(
    data: Any = None,
    *,
    msg: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=api_payload(data, msg=msg, action_status=True),
    )


def api_error(
    msg: str,
    *,
    status_code: int = 400,
    data: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=api_payload(data, msg=msg, action_status=False),
    )
