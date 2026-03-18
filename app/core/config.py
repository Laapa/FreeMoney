from functools import lru_cache
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FreeMoney Backend"
    app_env: str = "dev"
    database_url: str = Field(default="sqlite:///./freemoney.db", alias="DATABASE_URL")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    blockchain_explorer_base_urls: dict[str, str] = Field(
        default={"bsc": "https://api.bscscan.com/api"},
        alias="BLOCKCHAIN_EXPLORER_BASE_URLS",
    )
    blockchain_explorer_api_keys: dict[str, str] = Field(default_factory=dict, alias="BLOCKCHAIN_EXPLORER_API_KEYS")
    blockchain_expected_recipient_wallets: dict[str, str] = Field(
        default_factory=dict,
        alias="BLOCKCHAIN_EXPECTED_RECIPIENT_WALLETS",
    )
    blockchain_amount_tolerance: Decimal = Field(default=Decimal("0"), alias="BLOCKCHAIN_AMOUNT_TOLERANCE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
