import os

from pydantic_settings import BaseSettings

# 数据库路径始终相对于 backend/ 目录，不受 CWD 影响
_DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_ABS_PATH = os.path.join(_DB_DIR, "cq_house.db").replace("\\", "/")


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{_DB_ABS_PATH}"

    class Config:
        # 不指定 env_file — 数据库路径由代码自动计算
        env_prefix = ""


settings = Settings()
