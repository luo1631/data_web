from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./cq_house.db"

    class Config:
        env_file = "../.env"
        env_prefix = ""


settings = Settings()
