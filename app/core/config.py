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
    cryptopay_api_token: str | None = Field(default=None, alias="CRYPTOPAY_API_TOKEN")
    cryptopay_use_testnet: bool = Field(default=False, alias="CRYPTOPAY_USE_TESTNET")
    cryptopay_api_base_url: str | None = Field(default=None, alias="CRYPTOPAY_API_BASE_URL")
    cryptopay_asset: str = Field(default="USDT", alias="CRYPTOPAY_ASSET")
    cryptopay_invoice_expires_in: int = Field(default=1800, alias="CRYPTOPAY_INVOICE_EXPIRES_IN")

    transaction_fee_percent: Decimal = Field(default=Decimal("3.00"), alias="TRANSACTION_FEE_PERCENT")

    bybit_enabled: bool = Field(default=False, alias="BYBIT_ENABLED")
    bybit_payments_enabled: bool = Field(default=False, alias="BYBIT_PAYMENTS_ENABLED")
    bybit_recipient_uid: str | None = Field(default=None, alias="BYBIT_RECIPIENT_UID")
    bybit_recipient_note: str | None = Field(default=None, alias="BYBIT_RECIPIENT_NOTE")

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
    activation_public_url: str | None = Field(default=None, alias="ACTIVATION_PUBLIC_URL")
    admin_telegram_ids_raw: str = Field(default="", alias="ADMIN_TELEGRAM_IDS")

    @property
    def cryptopay_effective_api_base_url(self) -> str:
        if self.cryptopay_api_base_url:
            return self.cryptopay_api_base_url.rstrip("/")
        if self.cryptopay_use_testnet:
            return "https://testnet-pay.crypt.bot/api"
        return "https://pay.crypt.bot/api"

    @property
    def admin_telegram_ids(self) -> set[int]:
        parsed: set[int] = set()
        for value in self.admin_telegram_ids_raw.split(","):
            stripped = value.strip()
            if not stripped:
                continue
            if stripped.isdigit():
                parsed.add(int(stripped))
        return parsed


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
