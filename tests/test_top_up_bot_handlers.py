from datetime import datetime
from decimal import Decimal

from app.bot.handlers.top_up import (
    _build_bybit_submit_result_text,
    _format_bybit_transfer_instructions,
    _format_top_up_request_details,
    _is_bybit_retry_allowed,
    _is_bybit_auto_verify_ready,
    _is_bybit_available,
    _parse_bybit_sender_reference,
    _parse_retry_request_id,
)
from app.bot.keyboards.top_up import top_up_main_keyboard
from app.models.enums import Currency, Language, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest


def test_top_up_request_details_view_uses_request_data() -> None:
    request = TopUpRequest(
        id=42,
        user_id=1,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("125.50"),
        net_amount=Decimal("125.50"),
        fee_amount=Decimal("3.77"),
        gross_amount=Decimal("129.27"),
        currency=Currency.USD,
        status=TopUpStatus.WAITING_VERIFICATION,
        txid="abc123txid",
        sender_uid="12345678",
        external_reference="USDT TRC20",
        created_at=datetime(2026, 1, 2, 3, 4, 5),
        reviewed_at=datetime(2026, 1, 3, 4, 5, 6),
        verification_note="manual review",
    )

    message = _format_top_up_request_details(request, Language.EN)

    assert "#42" in message
    assert "Crypto Pay" in message
    assert "$125.50" in message
    assert "Under verification" in message
    assert "abc123txid" in message
    assert "12345678" in message
    assert "USDT TRC20" in message
    assert "2026-01-02 03:04:05" in message
    assert "2026-01-03 04:05:06" in message
    assert "manual review" in message


def test_parse_bybit_sender_reference_uid_or_external_reference() -> None:
    assert _parse_bybit_sender_reference("123456") == ("123456", None)
    assert _parse_bybit_sender_reference("bybit-transfer-ref") == (None, "bybit-transfer-ref")
    assert _parse_bybit_sender_reference("  ") == (None, None)


def test_top_up_request_details_bybit_uses_bybit_coin_for_display(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_DEPOSIT_COIN", "USDT")
    from app.core.config import get_settings

    get_settings.cache_clear()
    request = TopUpRequest(
        id=46,
        user_id=1,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("50.00"),
        net_amount=Decimal("50.00"),
        fee_amount=Decimal("0.00"),
        gross_amount=Decimal("50.00"),
        currency=Currency.RUB,
        status=TopUpStatus.WAITING_VERIFICATION,
        created_at=datetime(2026, 1, 4, 5, 6, 7),
    )

    message = _format_top_up_request_details(request, Language.EN)
    assert "$50" in message


def test_bybit_instruction_includes_recipient_uid_and_gross(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_ENABLED", "true")
    monkeypatch.setenv("BYBIT_RECIPIENT_UID", "99887766")
    monkeypatch.setenv("BYBIT_RECIPIENT_NOTE", "Use transfer note: SHOP")
    monkeypatch.setenv("BYBIT_DEPOSIT_COIN", "USDT")

    from app.core.config import get_settings

    get_settings.cache_clear()

    request = TopUpRequest(
        id=43,
        user_id=1,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        fee_amount=Decimal("0.00"),
        gross_amount=Decimal("100.00"),
        currency=Currency.USD,
        status=TopUpStatus.PENDING,
    )

    message = _format_bybit_transfer_instructions(request=request, language=Language.EN)

    assert "$100" in message
    assert "99887766" in message
    assert "SHOP" in message


def test_bybit_can_be_marked_unavailable_when_uid_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_ENABLED", "true")
    monkeypatch.delenv("BYBIT_RECIPIENT_UID", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()

    assert _is_bybit_available() is False


def test_crypto_method_label_is_cryptopay_invoice_text() -> None:
    from app.bot.i18n import t

    assert "TXID" not in t("top_up_method_crypto", Language.EN)
    assert "Crypto Pay" in t("top_up_method_crypto", Language.EN)


def test_bybit_auto_verify_ready_requires_credentials(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_AUTO_VERIFY_ENABLED", "true")
    monkeypatch.setenv("BYBIT_RECIPIENT_UID", "99887766")
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()
    assert _is_bybit_auto_verify_ready() is False

    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    get_settings.cache_clear()
    assert _is_bybit_auto_verify_ready() is True


def test_bybit_submit_message_success_has_no_manual_waiting_text() -> None:
    request = TopUpRequest(
        id=44,
        user_id=1,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        fee_amount=Decimal("0.00"),
        gross_amount=Decimal("100.00"),
        currency=Currency.USD,
        status=TopUpStatus.VERIFIED,
    )
    message = _build_bybit_submit_result_text(
        language=Language.EN,
        request=request,
        submitted_reference="123456",
        auto_verified=True,
        auto_attempted=True,
    )
    assert "Automatic payment verification has started." in message
    assert "verified automatically" in message
    assert "sent for review" not in message
    assert "manually by an operator" not in message


def test_bybit_submit_message_pending_has_no_success_text() -> None:
    request = TopUpRequest(
        id=45,
        user_id=1,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        fee_amount=Decimal("0.00"),
        gross_amount=Decimal("100.00"),
        currency=Currency.USD,
        status=TopUpStatus.WAITING_VERIFICATION,
    )
    message = _build_bybit_submit_result_text(
        language=Language.EN,
        request=request,
        submitted_reference="123456",
        auto_verified=False,
        auto_attempted=True,
    )
    assert "Automatic payment verification has started." in message
    assert "sent for review" in message
    assert "verified automatically" not in message


def test_parse_retry_request_id_supports_retry_button_text() -> None:
    assert _parse_retry_request_id("Проверить снова #12") == 12
    assert _parse_retry_request_id("Check again #44") == 44
    assert _parse_retry_request_id("#9") == 9


def test_bybit_retry_allowed_only_for_pending_auto_waiting_status() -> None:
    base = TopUpRequest(
        id=50,
        user_id=1,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        fee_amount=Decimal("0.00"),
        gross_amount=Decimal("100.00"),
        currency=Currency.USD,
        status=TopUpStatus.WAITING_VERIFICATION,
        verification_source="pending_auto_bybit",
    )
    assert _is_bybit_retry_allowed(base) is True

    base.verification_source = "auto_bybit"
    assert _is_bybit_retry_allowed(base) is False


def test_top_up_keyboard_has_manual_contact_button() -> None:
    keyboard = top_up_main_keyboard(Language.RU, show_bybit=True)
    labels = [button.text for row in keyboard.keyboard for button in row]
    assert "Связаться с админом по оплате" in labels
