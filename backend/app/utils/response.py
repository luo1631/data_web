from app.schemas.common import APIResponse


def ok(data=None, message: str = "success") -> dict:
    return APIResponse(code=200, message=message, data=data).model_dump()


def error(code: int = 500, message: str = "error", data=None) -> dict:
    return APIResponse(code=code, message=message, data=data).model_dump()
