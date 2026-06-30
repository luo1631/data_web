from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.districts import router as districts_router
from app.api.v1.listings import router as listings_router
from app.api.v1.communities import router as communities_router
from app.api.v1.crawl import router as crawl_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(districts_router)
api_router.include_router(listings_router)
api_router.include_router(communities_router)
api_router.include_router(crawl_router)
