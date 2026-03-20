from app.core.config import Settings


def test_default_database_url_is_sqlite() -> None:
    settings = Settings()

    assert settings.database_url == "sqlite:///./webster_shop.db"
