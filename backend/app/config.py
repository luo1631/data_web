from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "mysql+asyncmy://admin:admin123456@localhost:3306/cq_house"

    class Config:
        env_file = ".env"
        env_prefix = ""


settings = Settings()
