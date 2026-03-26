"""
Standardized JSON response helpers.
"""

from fastapi.responses import JSONResponse


def success(data: dict = None, message: str = "OK", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "message": message, "data": data},
    )


def error(message: str = "An error occurred", status_code: int = 400, details: dict = None) -> JSONResponse:
    content = {"success": False, "message": message}
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content)
