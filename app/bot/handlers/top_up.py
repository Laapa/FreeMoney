from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.bot.i18n import t
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.top_up import (
    TOP_UP_CANCEL,
    TOP_UP_METHOD_BYBIT,
    TOP_UP_METHOD_CRYPTO,
    TOP_UP_MY_REQUESTS,
    top_up_cancel_keyboard,
    top_up_main_keyboard,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import Language, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.admin import is_admin_telegram_id
from app.services.top_up_payments import check_crypto_pay_top_up, create_crypto_pay_top_up_invoice
from app.services.bybit_top_up_verification import try_auto_verify_bybit_top_up
from app.services.top_up_requests import create_top_up_request, get_top_up_request, list_user_top_up_requests, set_bybit_sender_reference
from app.services.top_up_statuses import TopUpRequestTransitionError
from app.services.users import get_user_by_telegram_id, init_or_update_user

router = Router(name="top_up")


class TopUpStates(StatesGroup):
    choosing_method = State()
    crypto_amount = State()
    bybit_amount = State()
    bybit_sender_reference = State()


def _resolve_or_create_user(tg_user) -> User:
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(db, telegram_id=tg_user.id, username=tg_user.username, language_code=tg_user.language_code)
        return user


async def _show_top_up_main(message: Message, *, user: User, state: FSMContext) -> None:
    await state.set_state(TopUpStates.choosing_method)
    await message.answer(
        t("top_up_main", user.language).format(balance=user.balance, currency=user.currency.value),
        reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()),
    )


@router.message(F.text.in_({t("menu_top_up", Language.RU), t("menu_top_up", Language.EN)}))
async def top_up_entry(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = _resolve_or_create_user(message.from_user)
    await _show_top_up_main(message, user=user, state=state)


@router.message(F.text.in_({t("nav_main_menu", Language.RU), t("nav_main_menu", Language.EN)}))
async def back_to_main_menu(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = _resolve_or_create_user(message.from_user)
    await state.clear()
    await message.answer(
        t("start", user.language),
        reply_markup=main_menu_keyboard(
            user.language,
            is_admin=is_admin_telegram_id(user.telegram_id, get_settings().admin_telegram_ids),
        ),
    )


@router.message(TopUpStates.choosing_method, F.text.in_({t("nav_back", Language.RU), t("nav_back", Language.EN)}))
async def top_up_back_to_main(message: Message, state: FSMContext) -> None:
    await back_to_main_menu(message, state)


@router.message(TopUpStates.choosing_method, F.text.in_({t(TOP_UP_MY_REQUESTS, Language.RU), t(TOP_UP_MY_REQUESTS, Language.EN)}))
async def top_up_show_requests(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = _resolve_or_create_user(message.from_user)

    with SessionLocal() as db:
        requests = list_user_top_up_requests(db, user_id=user.id)

    if not requests:
        await message.answer(t("top_up_no_requests", user.language), reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()))
        return

    lines = [t("top_up_status_list_title", user.language)]
    for request in requests:
        lines.append(f"#{request.id} • net={request.net_amount} / gross={request.gross_amount} {request.currency.value} • {_status_text(request, user.language)}")
    lines.append("")
    lines.append(t("top_up_open_request_hint", user.language))

    await state.set_state(TopUpStates.choosing_method)
    await message.answer("\n".join(lines), reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()))


@router.message(TopUpStates.choosing_method, F.text.regexp(r"^#?\d+$"))
async def top_up_request_details(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    user = _resolve_or_create_user(message.from_user)
    request_id = _parse_top_up_request_id(message.text)
    if request_id is None:
        return

    with SessionLocal() as db:
        request = get_top_up_request(db, request_id=request_id, user_id=user.id)
        if request is not None and request.method == TopUpMethod.CRYPTO_PAY and request.status == TopUpStatus.PENDING:
            check_crypto_pay_top_up(db, request_id=request.id)
            request = get_top_up_request(db, request_id=request_id, user_id=user.id)
        if request is not None and request.method == TopUpMethod.BYBIT_UID and request.status == TopUpStatus.WAITING_VERIFICATION and _is_bybit_auto_verify_ready():
            try_auto_verify_bybit_top_up(db, request_id=request.id)
            request = get_top_up_request(db, request_id=request_id, user_id=user.id)

    if request is None:
        await message.answer(t("top_up_request_not_found", user.language), reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()))
        return

    await state.set_state(TopUpStates.choosing_method)
    await message.answer(_format_top_up_request_details(request, user.language), reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()))


@router.message(TopUpStates.choosing_method, F.text.in_({t(TOP_UP_METHOD_CRYPTO, Language.RU), t(TOP_UP_METHOD_CRYPTO, Language.EN)}))
async def top_up_crypto_intro(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = _resolve_or_create_user(message.from_user)
    await state.set_state(TopUpStates.crypto_amount)
    await message.answer(t("top_up_crypto_intro", user.language), reply_markup=top_up_cancel_keyboard(user.language))


@router.message(TopUpStates.crypto_amount)
async def top_up_crypto_amount(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    user = _resolve_or_create_user(message.from_user)

    if message.text in {t(TOP_UP_CANCEL, user.language), t("nav_back", user.language)}:
        await _show_top_up_main(message, user=user, state=state)
        return

    amount = _parse_amount(message.text)
    if amount is None:
        await message.answer(t("top_up_amount_invalid", user.language), reply_markup=top_up_cancel_keyboard(user.language))
        return

    with SessionLocal() as db:
        request = create_top_up_request(db, user_id=user.id, method=TopUpMethod.CRYPTO_PAY, amount=amount, currency=user.currency)
        invoice_result = create_crypto_pay_top_up_invoice(db, request_id=request.id)
        request = invoice_result.request or request

    summary = t("top_up_request_summary", user.language).format(
        id=request.id,
        method=t("top_up_method_crypto", user.language),
        amount=request.net_amount,
        fee_amount=request.fee_amount,
        gross_amount=request.gross_amount,
        currency=request.currency.value,
        status=_status_text(request, user.language),
        note=request.provider_payment_url or request.provider_invoice_url or t("top_up_not_provided", user.language),
    )
    summary += "\n\n" + (
        t("top_up_crypto_invoice_created", user.language)
        if invoice_result.ok
        else t("top_up_crypto_invoice_failed", user.language)
    )
    await message.answer(summary, reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()))
    await state.set_state(TopUpStates.choosing_method)


@router.message(TopUpStates.choosing_method, F.text.in_({t(TOP_UP_METHOD_BYBIT, Language.RU), t(TOP_UP_METHOD_BYBIT, Language.EN)}))
async def top_up_bybit_intro(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = _resolve_or_create_user(message.from_user)
    if not _is_bybit_available():
        await message.answer(t("top_up_bybit_unavailable", user.language), reply_markup=top_up_main_keyboard(user.language, show_bybit=False))
        await state.set_state(TopUpStates.choosing_method)
        return
    await state.set_state(TopUpStates.bybit_amount)
    await message.answer(t("top_up_bybit_intro", user.language), reply_markup=top_up_cancel_keyboard(user.language))


@router.message(TopUpStates.bybit_amount)
async def top_up_bybit_amount(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    user = _resolve_or_create_user(message.from_user)

    if message.text in {t(TOP_UP_CANCEL, user.language), t("nav_back", user.language)}:
        await _show_top_up_main(message, user=user, state=state)
        return

    amount = _parse_amount(message.text)
    if amount is None:
        await message.answer(t("top_up_amount_invalid", user.language), reply_markup=top_up_cancel_keyboard(user.language))
        return

    with SessionLocal() as db:
        request = create_top_up_request(db, user_id=user.id, method=TopUpMethod.BYBIT_UID, amount=amount, currency=user.currency)

    await state.update_data(top_up_request_id=request.id)
    await state.set_state(TopUpStates.bybit_sender_reference)

    await message.answer(
        t("top_up_request_summary", user.language).format(
            id=request.id,
            method=t("top_up_method_bybit", user.language),
            amount=request.net_amount,
            fee_amount=request.fee_amount,
            gross_amount=request.gross_amount,
            currency=request.currency.value,
            status=_status_text(request, user.language),
            note=t("top_up_not_provided", user.language),
        )
        + "\n\n"
        + _format_bybit_transfer_instructions(request=request, language=user.language),
        reply_markup=top_up_cancel_keyboard(user.language),
    )


@router.message(TopUpStates.bybit_sender_reference)
async def top_up_bybit_sender_reference(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    user = _resolve_or_create_user(message.from_user)
    if message.text in {t(TOP_UP_CANCEL, user.language), t("nav_back", user.language)}:
        await _show_top_up_main(message, user=user, state=state)
        return

    sender_uid, external_reference = _parse_bybit_sender_reference(message.text)
    if sender_uid is None and external_reference is None:
        await message.answer(t("top_up_bybit_reference_invalid", user.language), reply_markup=top_up_cancel_keyboard(user.language))
        return

    data = await state.get_data()
    request_id = data.get("top_up_request_id")
    if not request_id:
        await _show_top_up_main(message, user=user, state=state)
        return

    with SessionLocal() as db:
        request = get_top_up_request(db, request_id=request_id, user_id=user.id)
        if request is None:
            await message.answer(t("top_up_request_not_found", user.language), reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()))
            await _show_top_up_main(message, user=user, state=state)
            return
        try:
            request = set_bybit_sender_reference(
                db,
                request=request,
                sender_uid=sender_uid,
                external_reference=external_reference,
            )
        except TopUpRequestTransitionError:
            await message.answer(
                t("top_up_bybit_reference_state_invalid", user.language), reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available())
            )
            await _show_top_up_main(message, user=user, state=state)
            return

    submitted_reference = sender_uid or external_reference or t("top_up_not_provided", user.language)
    auto_verified = False
    auto_attempted = False
    with SessionLocal() as db:
        latest = get_top_up_request(db, request_id=request.id, user_id=user.id)
        if latest is not None and _is_bybit_auto_verify_ready():
            auto_attempted = True
            auto_result = try_auto_verify_bybit_top_up(db, request_id=latest.id)
            latest = get_top_up_request(db, request_id=latest.id, user_id=user.id)
            if auto_result.ok and latest is not None and latest.status == TopUpStatus.VERIFIED:
                auto_verified = True

    reply_text = _build_bybit_submit_result_text(
        language=user.language,
        request=request,
        submitted_reference=submitted_reference,
        auto_verified=auto_verified,
        auto_attempted=auto_attempted,
    )
    await message.answer(reply_text, reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available()))
    await state.set_state(TopUpStates.choosing_method)


def _is_bybit_available() -> bool:
    settings = get_settings()
    return settings.bybit_enabled and bool((settings.bybit_recipient_uid or "").strip())


def _is_bybit_auto_verify_ready() -> bool:
    settings = get_settings()
    return bool(
        settings.bybit_auto_verify_enabled
        and settings.bybit_api_key
        and settings.bybit_api_secret
        and (settings.bybit_recipient_uid or "").strip()
    )


def _format_bybit_transfer_instructions(*, request: TopUpRequest, language: Language) -> str:
    settings = get_settings()
    recipient_uid = (settings.bybit_recipient_uid or "").strip() or t("top_up_not_provided", language)
    recipient_note = (settings.bybit_recipient_note or "").strip() or t("top_up_not_provided", language)
    return t("top_up_bybit_transfer_instruction", language).format(
        gross_amount=request.gross_amount,
        currency=request.currency.value,
        recipient_uid=recipient_uid,
        recipient_note=recipient_note,
    ) + "\n\n" + t("top_up_bybit_reference_prompt", language)


def _build_bybit_submit_result_text(
    *,
    language: Language,
    request: TopUpRequest,
    submitted_reference: str,
    auto_verified: bool,
    auto_attempted: bool,
) -> str:
    submitted = t("top_up_bybit_reference_submitted", language).format(reference=submitted_reference)
    if auto_verified:
        return submitted + "\n\n" + t("top_up_bybit_auto_verified", language).format(
            id=request.id,
            amount=request.net_amount,
            currency=request.currency.value,
        )
    waiting = t("top_up_waiting_verification", language).format(id=request.id, status=_status_text(request, language))
    if auto_attempted:
        return submitted + "\n\n" + waiting + "\n\n" + t("top_up_bybit_auto_pending", language)
    return submitted + "\n\n" + waiting



def _parse_amount(raw_amount: str) -> Decimal | None:
    normalized = raw_amount.replace(",", ".").strip()
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None

    if amount <= 0:
        return None
    if amount.as_tuple().exponent < -2:
        return None
    return amount.quantize(Decimal("0.01"))


def _status_text(request: TopUpRequest, language: Language) -> str:
    key = f"top_up_status_{request.status.value}"
    return t(key, language)


def _format_top_up_request_details(request: TopUpRequest, language: Language) -> str:
    txid_value = request.txid or t("top_up_not_provided", language)
    sender_uid_value = request.sender_uid or t("top_up_not_provided", language)
    external_reference_value = request.external_reference or t("top_up_not_provided", language)
    reviewed_at_value = _format_optional_datetime(request.reviewed_at, language)
    verification_note_value = request.verification_note or t("top_up_not_provided", language)
    verified_network_value = request.verified_network or t("top_up_not_provided", language)
    verified_token_value = request.verified_token or t("top_up_not_provided", language)
    verified_amount_value = request.verified_amount if request.verified_amount is not None else t("top_up_not_provided", language)
    verified_recipient_value = request.verified_recipient or t("top_up_not_provided", language)
    method_key = "top_up_method_bybit" if request.method == TopUpMethod.BYBIT_UID else "top_up_method_crypto"
    return t("top_up_request_details", language).format(
        id=request.id,
        method=t(method_key, language),
        amount=request.net_amount,
        fee_amount=request.fee_amount,
        gross_amount=request.gross_amount,
        currency=request.currency.value,
        status=_status_text(request, language),
        txid=txid_value,
        sender_uid=sender_uid_value,
        external_reference=external_reference_value,
        created_at=request.created_at.isoformat(sep=" ", timespec="seconds"),
        reviewed_at=reviewed_at_value,
        verification_note=verification_note_value,
        verified_network=verified_network_value,
        verified_token=verified_token_value,
        verified_amount=verified_amount_value,
        verified_recipient=verified_recipient_value,
    )


def _format_optional_datetime(value, language: Language) -> str:
    if value is None:
        return t("top_up_not_provided", language)
    return value.isoformat(sep=" ", timespec="seconds")


def _parse_top_up_request_id(raw_text: str) -> int | None:
    normalized = raw_text.strip()
    if normalized.startswith("#"):
        normalized = normalized[1:]
    if not normalized.isdigit():
        return None
    return int(normalized)


def _parse_bybit_sender_reference(raw_value: str) -> tuple[str | None, str | None]:
    value = raw_value.strip()
    if not value:
        return None, None

    if value.isdigit() and 6 <= len(value) <= 20:
        return value, None

    if 6 <= len(value) <= 255 and "\n" not in value:
        return None, value

    return None, None
