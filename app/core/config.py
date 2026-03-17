from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FreeMoney Backend"
    app_env: str = "dev"
    database_url: str = Field(default="sqlite:///./freemoney.db", alias="DATABASE_URL")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
