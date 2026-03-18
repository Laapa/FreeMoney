from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings


@dataclass(frozen=True)
class SupportedCryptoOption:
    key: str
    network: str
    display_label: str
    token_symbol: str | None
    token_contract: str | None
    token_decimals: int
    recipient_wallet: str
    is_native_coin: bool


@lru_cache(maxsize=1)
def get_supported_crypto_options() -> dict[str, SupportedCryptoOption]:
    settings = get_settings()
    options: dict[str, SupportedCryptoOption] = {}

    for key, raw in settings.blockchain_supported_crypto_options.items():
        normalized_key = key.strip().lower()
        option = SupportedCryptoOption(
            key=normalized_key,
            network=str(raw["network"]).strip().lower(),
            display_label=str(raw["display_label"]).strip(),
            token_symbol=_optional_lower(raw.get("token_symbol")),
            token_contract=_optional_lower(raw.get("token_contract")),
            token_decimals=int(raw.get("token_decimals", 18)),
            recipient_wallet=str(raw.get("recipient_wallet", "")).strip().lower(),
            is_native_coin=bool(raw.get("is_native_coin", False)),
        )
        options[normalized_key] = option

    return options


def find_crypto_option(*, network: str, token_symbol: str | None) -> SupportedCryptoOption | None:
    normalized_network = (network or "").strip().lower()
    normalized_token = _optional_lower(token_symbol)
    for option in get_supported_crypto_options().values():
        if option.network != normalized_network:
            continue
        if option.token_symbol != normalized_token:
            continue
        return option
    return None


def _optional_lower(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lower()
