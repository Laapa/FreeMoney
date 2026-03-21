from app.core.config import Settings


def test_default_database_url_is_sqlite() -> None:
    settings = Settings()

    assert settings.database_url == "sqlite:///./webster_shop.db"


def test_cryptopay_base_url_defaults_mainnet() -> None:
    settings = Settings()
    assert settings.cryptopay_effective_api_base_url == "https://pay.crypt.bot/api"


def test_cryptopay_base_url_defaults_testnet(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_USE_TESTNET", "true")
    settings = Settings()
    assert settings.cryptopay_effective_api_base_url == "https://testnet-pay.crypt.bot/api"


def test_cryptopay_base_url_override(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_BASE_URL", "https://custom-pay.example/api/")
    settings = Settings()
    assert settings.cryptopay_effective_api_base_url == "https://custom-pay.example/api"
