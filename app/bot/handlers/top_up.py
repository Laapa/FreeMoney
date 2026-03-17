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
    top_up_network_keyboard,
)
from app.db.session import SessionLocal
from app.models.enums import Language, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.top_up_requests import (
    create_top_up_request,
    get_top_up_request,
    list_user_top_up_requests,
    set_top_up_txid,
    set_top_up_waiting_verification,
)
from app.services.top_up_statuses import TopUpRequestTransitionError
from app.services.users import get_user_by_telegram_id, init_or_update_user

router = Router(name="top_up")

NETWORK_CHOICES = {"top_up_network_trc20", "top_up_network_erc20"}


class TopUpStates(StatesGroup):
    choosing_method = State()
    crypto_network = State()
    crypto_amount = State()
    crypto_txid = State()
    bybit_amount = State()


def _resolve_or_create_user(tg_user) -> User:
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )
        return user


async def _show_top_up_main(message: Message, *, user: User, state: FSMContext) -> None:
    await state.set_state(TopUpStates.choosing_method)
    await message.answer(
        t("top_up_main", user.language).format(balance=user.balance, currency=user.currency.value),
        reply_markup=top_up_main_keyboard(user.language),
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
    await message.answer(t("start", user.language), reply_markup=main_menu_keyboard(user.language))


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
        await message.answer(t("top_up_no_requests", user.language), reply_markup=top_up_main_keyboard(user.language))
        return

    lines = [t("top_up_status_list_title", user.language)]
    for request in requests:
        lines.append(
            f"#{request.id} • {request.amount} {request.currency.value} • {_status_text(request, user.language)}"
        )
    lines.append("")
    lines.append(t("top_up_open_request_hint", user.language))

    await state.set_state(TopUpStates.choosing_method)
    await message.answer("\n".join(lines), reply_markup=top_up_main_keyboard(user.language))


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

    if request is None:
        await message.answer(t("top_up_request_not_found", user.language), reply_markup=top_up_main_keyboard(user.language))
        return

    await state.set_state(TopUpStates.choosing_method)
    await message.answer(_format_top_up_request_details(request, user.language), reply_markup=top_up_main_keyboard(user.language))


@router.message(TopUpStates.choosing_method, F.text.in_({t(TOP_UP_METHOD_CRYPTO, Language.RU), t(TOP_UP_METHOD_CRYPTO, Language.EN)}))
async def top_up_crypto_intro(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = _resolve_or_create_user(message.from_user)
    await state.set_state(TopUpStates.crypto_network)
    await message.answer(
        t("top_up_crypto_intro", user.language),
        reply_markup=top_up_network_keyboard(user.language),
    )


@router.message(TopUpStates.crypto_network)
async def top_up_crypto_network(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    user = _resolve_or_create_user(message.from_user)

    if message.text in {t(TOP_UP_CANCEL, user.language), t("nav_back", user.language)}:
        await _show_top_up_main(message, user=user, state=state)
        return

    network_key = None
    for candidate in NETWORK_CHOICES:
        if message.text == t(candidate, user.language):
            network_key = candidate
            break

    if network_key is None:
        await message.answer(t("top_up_network_invalid", user.language), reply_markup=top_up_network_keyboard(user.language))
        return

    await state.update_data(network=t(network_key, user.language))
    await state.set_state(TopUpStates.crypto_amount)
    await message.answer(t("top_up_enter_amount", user.language), reply_markup=top_up_cancel_keyboard(user.language))


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

    data = await state.get_data()
    with SessionLocal() as db:
        request = create_top_up_request(
            db,
            user_id=user.id,
            method=TopUpMethod.CRYPTO_TXID,
            amount=amount,
            currency=user.currency,
            external_reference=data.get("network"),
        )

    await state.update_data(top_up_request_id=request.id)
    await state.set_state(TopUpStates.crypto_txid)
    await message.answer(
        t("top_up_request_summary", user.language).format(
            id=request.id,
            method=t("top_up_method_crypto", user.language),
            amount=request.amount,
            currency=request.currency.value,
            status=_status_text(request, user.language),
            note=request.external_reference or "-",
        )
        + "\n\n"
        + t("top_up_enter_txid", user.language),
        reply_markup=top_up_cancel_keyboard(user.language),
    )


@router.message(TopUpStates.crypto_txid)
async def top_up_crypto_txid(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    user = _resolve_or_create_user(message.from_user)
    if message.text in {t(TOP_UP_CANCEL, user.language), t("nav_back", user.language)}:
        await _show_top_up_main(message, user=user, state=state)
        return

    txid = message.text.strip()
    if len(txid) < 8 or " " in txid:
        await message.answer(t("top_up_txid_invalid", user.language), reply_markup=top_up_cancel_keyboard(user.language))
        return

    data = await state.get_data()
    request_id = data.get("top_up_request_id")
    if not request_id:
        await _show_top_up_main(message, user=user, state=state)
        return

    with SessionLocal() as db:
        request = get_top_up_request(db, request_id=request_id, user_id=user.id)
        if request is None:
            await message.answer(t("top_up_request_not_found", user.language), reply_markup=top_up_main_keyboard(user.language))
            await _show_top_up_main(message, user=user, state=state)
            return
        try:
            request = set_top_up_txid(db, request=request, txid=txid)
        except TopUpRequestTransitionError:
            await message.answer(t("top_up_txid_state_invalid", user.language), reply_markup=top_up_main_keyboard(user.language))
            await _show_top_up_main(message, user=user, state=state)
            return

    await message.answer(
        t("top_up_waiting_verification", user.language).format(id=request.id, status=_status_text(request, user.language)),
        reply_markup=top_up_main_keyboard(user.language),
    )
    await state.set_state(TopUpStates.choosing_method)


@router.message(TopUpStates.choosing_method, F.text.in_({t(TOP_UP_METHOD_BYBIT, Language.RU), t(TOP_UP_METHOD_BYBIT, Language.EN)}))
async def top_up_bybit_intro(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = _resolve_or_create_user(message.from_user)
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
        request = create_top_up_request(
            db,
            user_id=user.id,
            method=TopUpMethod.BYBIT_UID,
            amount=amount,
            currency=user.currency,
        )
        request = set_top_up_waiting_verification(db, request=request, reference="bybit_uid_payment")

    await message.answer(
        t("top_up_request_summary", user.language).format(
            id=request.id,
            method=t("top_up_method_bybit", user.language),
            amount=request.amount,
            currency=request.currency.value,
            status=_status_text(request, user.language),
            note=request.external_reference or "-",
        )
        + "\n\n"
        + t("top_up_bybit_instructions", user.language)
        + "\n\n"
        + t("top_up_waiting_verification", user.language).format(id=request.id, status=_status_text(request, user.language)),
        reply_markup=top_up_main_keyboard(user.language),
    )
    await state.set_state(TopUpStates.choosing_method)


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
    reviewed_at_value = _format_optional_datetime(request.reviewed_at, language)
    verification_note_value = request.verification_note or t("top_up_not_provided", language)
    return t("top_up_request_details", language).format(
        id=request.id,
        method=t(f"top_up_method_{'crypto' if request.method == TopUpMethod.CRYPTO_TXID else 'bybit'}", language),
        amount=request.amount,
        currency=request.currency.value,
        status=_status_text(request, language),
        txid=txid_value,
        created_at=request.created_at.isoformat(sep=" ", timespec="seconds"),
        reviewed_at=reviewed_at_value,
        verification_note=verification_note_value,
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
