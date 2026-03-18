from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.i18n import t
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.products import (
    CALLBACK_MENU,
    CALLBACK_ROOT,
    CALLBACK_TOP_UP,
    buy_product_callback,
    categories_keyboard,
    category_view_keyboard,
    open_product_callback,
    product_card_keyboard,
    product_list_keyboard,
    reservation_success_keyboard,
    top_up_placeholder_keyboard,
)
from app.db.session import SessionLocal
from app.services.catalog import get_category_breadcrumbs, get_category_view, get_product_card, list_categories, list_product_cards
from app.services.purchase import reserve_product_for_user
from app.services.users import get_user_by_telegram_id, init_or_update_user

router = Router(name="products")


async def _resolve_user(message: Message):
    tg_user = message.from_user
    if tg_user is None:
        return None

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


async def show_root_categories(message: Message) -> None:
    user = await _resolve_user(message)
    if user is None:
        return

    with SessionLocal() as db:
        categories = list_categories(db, user_id=user.id, language=user.language, parent_id=None)

    if not categories:
        await message.answer(t("products_empty", user.language))
        return

    await message.answer(
        t("products_root_title", user.language),
        reply_markup=categories_keyboard(categories, user.language),
    )


@router.callback_query(F.data == CALLBACK_MENU)
async def on_main_menu(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None:
        await callback.answer()
        return

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

    await message.answer(t("start", user.language), reply_markup=main_menu_keyboard(user.language))
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_TOP_UP))
async def on_top_up_placeholder(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None or callback.data is None:
        await callback.answer()
        return

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

    category_id = int(callback.data.split(":")[-1])
    await message.edit_text(
        t("top_up_placeholder", user.language),
        reply_markup=top_up_placeholder_keyboard(category_id=category_id, language=user.language),
    )
    await callback.answer()


@router.callback_query(F.data == CALLBACK_ROOT)
async def on_root(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None:
        await callback.answer()
        return

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )
        categories = list_categories(db, user_id=user.id, language=user.language, parent_id=None)

    if not categories:
        await callback.answer(t("products_empty", user.language), show_alert=True)
        return

    await message.edit_text(
        t("products_root_title", user.language),
        reply_markup=categories_keyboard(categories, user.language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:cat:"))
async def on_category(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None:
        await callback.answer()
        return

    category_id = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

        category = get_category_view(db, user_id=user.id, language=user.language, category_id=category_id)
        if category is None:
            await callback.answer(t("products_category_not_found", user.language), show_alert=True)
            return

        children = list_categories(db, user_id=user.id, language=user.language, parent_id=category.id)
        breadcrumbs = " / ".join(get_category_breadcrumbs(db, category_id=category.id, language=user.language))

    price_text = str(category.price) if category.price is not None else t("products_price_missing", user.language)
    text = t("products_category_view", user.language).format(
        title=category.title,
        breadcrumb=breadcrumbs,
        price=price_text,
        stock=category.stock_count,
    )

    await message.edit_text(
        text,
        reply_markup=category_view_keyboard(category=category, subcategories=children, language=user.language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:list:"))
async def on_product_list(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None:
        await callback.answer()
        return

    category_id = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

        category = get_category_view(db, user_id=user.id, language=user.language, category_id=category_id)
        if category is None:
            await callback.answer(t("products_category_not_found", user.language), show_alert=True)
            return

        cards = list_product_cards(db, category_id=category.id)
        breadcrumbs = " / ".join(get_category_breadcrumbs(db, category_id=category.id, language=user.language))

    lines = [
        t("products_list_title", user.language).format(title=category.title),
        t("products_breadcrumb_line", user.language).format(path=breadcrumbs),
        t("products_price_line", user.language).format(
            price=str(category.price) if category.price is not None else t("products_price_missing", user.language)
        ),
        t("products_stock_line", user.language).format(stock=category.stock_count),
        "",
    ]
    if cards:
        for index, card in enumerate(cards, start=1):
            lines.append(
                t("products_card_line", user.language).format(
                    idx=index,
                    product_id=card.product_id,
                    price=str(category.price) if category.price is not None else t("products_price_missing", user.language),
                )
            )
    else:
        lines.append(t("products_no_stock", user.language))

    product_rows = []
    for card in cards:
        product_rows.append(
            [
                {
                    "text": f"#{card.product_id} · {t('products_open_product', user.language)}",
                    "callback_data": open_product_callback(category.id, card.product_id),
                },
                {
                    "text": t("products_reserve_item", user.language),
                    "callback_data": buy_product_callback(category.id, card.product_id),
                },
            ]
        )

    await message.edit_text(
        "\n".join(lines),
        reply_markup=product_list_keyboard(
            category=category,
            can_buy=category.stock_count > 0 and category.price is not None,
            language=user.language,
            product_rows=product_rows,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:item:"))
async def on_product_view(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None or callback.data is None:
        await callback.answer()
        return

    _, _, raw_category_id, raw_product_id = callback.data.split(":")
    category_id = int(raw_category_id)
    product_id = int(raw_product_id)

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )
        category = get_category_view(db, user_id=user.id, language=user.language, category_id=category_id)
        if category is None:
            await callback.answer(t("products_category_not_found", user.language), show_alert=True)
            return

        card = get_product_card(db, category_id=category.id, product_id=product_id)
        if card is None:
            await callback.answer(t("products_product_not_available", user.language), show_alert=True)
            return

        breadcrumbs = " / ".join(get_category_breadcrumbs(db, category_id=category.id, language=user.language))

    await message.edit_text(
        t("products_product_view", user.language).format(
            product_id=card.product_id,
            title=category.title,
            breadcrumb=breadcrumbs,
            price=str(category.price) if category.price is not None else t("products_price_missing", user.language),
        ),
        reply_markup=product_card_keyboard(category_id=category.id, product_id=card.product_id, language=user.language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:buy:"))
async def on_buy(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None:
        await callback.answer()
        return

    category_id = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

        category = get_category_view(db, user_id=user.id, language=user.language, category_id=category_id)
        if category is None:
            await callback.answer(t("products_category_not_found", user.language), show_alert=True)
            return

        if category.price is None:
            await callback.answer(t("products_price_missing", user.language), show_alert=True)
            return

        language = user.language
        category_title = category.title
        resolved_category_id = category.id
        attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=category.price)

    if not attempt.ok:
        await callback.answer(t("products_no_stock", language), show_alert=True)
        return

    await message.edit_text(
        t("products_reservation_success", language).format(
            title=category_title,
            reservation_id=attempt.reservation.id,
            order_id=attempt.order.id,
            price=attempt.order.price,
        ),
        reply_markup=reservation_success_keyboard(category_id=resolved_category_id, language=language),
    )
    await callback.answer(t("products_reserved_toast", language))


@router.callback_query(F.data.startswith("prod:itembuy:"))
async def on_buy_product(callback: CallbackQuery) -> None:
    message = callback.message
    tg_user = callback.from_user
    if message is None or callback.data is None:
        await callback.answer()
        return

    _, _, raw_category_id, raw_product_id = callback.data.split(":")
    category_id = int(raw_category_id)
    product_id = int(raw_product_id)

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

        category = get_category_view(db, user_id=user.id, language=user.language, category_id=category_id)
        if category is None:
            await callback.answer(t("products_category_not_found", user.language), show_alert=True)
            return

        if category.price is None:
            await callback.answer(t("products_price_missing", user.language), show_alert=True)
            return

        language = user.language
        category_title = category.title
        resolved_category_id = category.id
        attempt = reserve_product_for_user(
            db,
            user_id=user.id,
            category_id=category.id,
            product_id=product_id,
            price=category.price,
        )

    if not attempt.ok:
        await callback.answer(t("products_no_stock", language), show_alert=True)
        return

    await message.edit_text(
        t("products_reservation_success", language).format(
            title=category_title,
            reservation_id=attempt.reservation.id,
            order_id=attempt.order.id,
            price=attempt.order.price,
        ),
        reply_markup=reservation_success_keyboard(category_id=resolved_category_id, language=language),
    )
    await callback.answer(t("products_reserved_toast", language))
