from datetime import datetime
from decimal import Decimal

from app.bot.handlers.top_up import _format_top_up_request_details
from app.models.enums import Currency, Language, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest


def test_top_up_request_details_view_uses_request_data() -> None:
    request = TopUpRequest(
        id=42,
        user_id=1,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("125.50"),
        currency=Currency.USD,
        status=TopUpStatus.WAITING_VERIFICATION,
        txid="abc123txid",
        external_reference="USDT TRC20",
        created_at=datetime(2026, 1, 2, 3, 4, 5),
        reviewed_at=datetime(2026, 1, 3, 4, 5, 6),
        verification_note="manual review",
    )

    message = _format_top_up_request_details(request, Language.EN)

    assert "#42" in message
    assert "Crypto by TXID" in message
    assert "125.50 USD" in message
    assert "Under verification" in message
    assert "abc123txid" in message
    assert "2026-01-02 03:04:05" in message
    assert "2026-01-03 04:05:06" in message
    assert "manual review" in message
