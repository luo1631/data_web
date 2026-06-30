from fastapi import APIRouter

from app.utils.response import ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return ok(data={"status": "ok", "db": "connected"})
