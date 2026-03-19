from functools import lru_cache
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="WEBSTER-SHOP Backend", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(default="sqlite:///./webster_shop.db", alias="DATABASE_URL")
    sql_echo: bool = Field(default=False, alias="SQL_ECHO")

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")

    blockchain_explorer_base_urls: dict[str, str] = Field(
        default={"bsc": "https://api.bscscan.com/api"},
        alias="BLOCKCHAIN_EXPLORER_BASE_URLS",
    )
    blockchain_explorer_api_keys: dict[str, str] = Field(default_factory=dict, alias="BLOCKCHAIN_EXPLORER_API_KEYS")
    blockchain_supported_crypto_options: dict[str, dict[str, str | int | bool]] = Field(
        default={
            "bsc_usdt": {
                "network": "bsc",
                "display_label": "USDT BSC (BEP20)",
                "token_symbol": "usdt",
                "token_contract": "0x55d398326f99059ff775485246999027b3197955",
                "token_decimals": 18,
                "recipient_wallet": "",
                "is_native_coin": False,
            }
        },
        alias="BLOCKCHAIN_SUPPORTED_CRYPTO_OPTIONS",
    )
    blockchain_amount_tolerance: Decimal = Field(default=Decimal("0"), alias="BLOCKCHAIN_AMOUNT_TOLERANCE")

    activation_api_base_url: str = Field(default="http://127.0.0.1:9000", alias="ACTIVATION_API_BASE_URL")
    activation_api_timeout_seconds: float = Field(default=10.0, alias="ACTIVATION_API_TIMEOUT_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
