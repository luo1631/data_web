from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：APScheduler 占位，后续 Phase 6 注册定时任务
    yield
    # 关闭时：清理资源


app = FastAPI(
    title="重庆二手房数据分析系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
