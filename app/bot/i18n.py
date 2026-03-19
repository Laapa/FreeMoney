from app.models.enums import Language

TEXTS: dict[str, dict[Language, str]] = {
    "start": {
        Language.RU: "Добро пожаловать в FreeMoney! Выберите действие в меню ниже.",
        Language.EN: "Welcome to FreeMoney! Choose an action from the menu below.",
    },
    "language_prompt": {
        Language.RU: "🌐 Выберите язык / Choose your language",
        Language.EN: "🌐 Choose your language / Выберите язык",
    },
    "language_saved": {
        Language.RU: "Язык сохранен: Русский ✅",
        Language.EN: "Language saved: English ✅",
    },
    "language_option_ru": {Language.RU: "Русский", Language.EN: "Русский"},
    "language_option_en": {Language.RU: "English", Language.EN: "English"},
    "menu_products": {Language.RU: "🛍 Товары", Language.EN: "🛍 Products"},
    "menu_top_up": {Language.RU: "💳 Пополнить", Language.EN: "💳 Top Up"},
    "menu_profile": {Language.RU: "👤 Профиль", Language.EN: "👤 Profile"},
    "menu_orders": {Language.RU: "📦 Заказы", Language.EN: "📦 Orders"},
    "menu_rules": {Language.RU: "📜 Правила", Language.EN: "📜 Rules"},
    "menu_support": {Language.RU: "🛟 Поддержка", Language.EN: "🛟 Support"},
    "profile_title": {Language.RU: "Ваш профиль", Language.EN: "Your profile"},
    "profile_change_language": {Language.RU: "🌐 Сменить язык", Language.EN: "🌐 Change language"},
    "profile_body": {
        Language.RU: (
            "🆔 Telegram ID: {id}\n"
            "👤 Username: {username}\n"
            "📅 Дата регистрации: {registered_at}\n"
            "💰 Баланс: {balance} {currency}\n"
            "🌐 Язык: {language}\n"
            "📦 Всего заказов: {total_orders}\n"
            "✅ Доставлено: {delivered_orders}\n"
            "💸 Потрачено: {total_spent} {currency}"
        ),
        Language.EN: (
            "🆔 Telegram ID: {id}\n"
            "👤 Username: {username}\n"
            "📅 Registered: {registered_at}\n"
            "💰 Balance: {balance} {currency}\n"
            "🌐 Language: {language}\n"
            "📦 Total orders: {total_orders}\n"
            "✅ Delivered: {delivered_orders}\n"
            "💸 Total spent: {total_spent} {currency}"
        ),
    },
    "orders_empty": {Language.RU: "У вас пока нет заказов.", Language.EN: "You have no orders yet."},
    "orders_title": {
        Language.RU: "📦 Ваши заказы (страница {page}/{pages})",
        Language.EN: "📦 Your orders (page {page}/{pages})",
    },
    "orders_card": {
        Language.RU: "Заказ #{id}\n📅 Создан: {created_at}\n📌 Статус: {status}\n💵 Цена: {price} {currency}",
        Language.EN: "Order #{id}\n📅 Created: {created_at}\n📌 Status: {status}\n💵 Price: {price} {currency}",
    },
    "orders_open": {
        Language.RU: "🔎 Заказ #{id}",
        Language.EN: "🔎 Order #{id}",
    },
    "orders_not_found": {
        Language.RU: "Заказ не найден.",
        Language.EN: "Order not found.",
    },
    "orders_details_title": {
        Language.RU: "📦 Детали заказа #{id}",
        Language.EN: "📦 Order #{id} details",
    },
    "orders_details_created": {
        Language.RU: "📅 Создан: {created_at}",
        Language.EN: "📅 Created: {created_at}",
    },
    "orders_details_status": {
        Language.RU: "📌 Статус: {status}",
        Language.EN: "📌 Status: {status}",
    },
    "orders_details_price": {
        Language.RU: "💵 Цена: {price} {currency}",
        Language.EN: "💵 Price: {price} {currency}",
    },
    "orders_details_delivered_at": {
        Language.RU: "✅ Доставлен: {delivered_at}",
        Language.EN: "✅ Delivered: {delivered_at}",
    },
    "orders_action_pay": {
        Language.RU: "💸 Оплатить",
        Language.EN: "💸 Pay",
    },
    "orders_action_top_up": {
        Language.RU: "💳 Пополнить",
        Language.EN: "💳 Top Up",
    },
    "orders_payment_insufficient_balance": {
        Language.RU: "Недостаточно средств для оплаты заказа.\nТекущий баланс: {balance} {currency}\nНажмите «💳 Пополнить», затем повторите оплату.",
        Language.EN: "Insufficient balance for this order.\nCurrent balance: {balance} {currency}\nTap “💳 Top Up” and then retry payment.",
    },
    "orders_payment_not_available": {
        Language.RU: "Оплата недоступна для этого заказа.",
        Language.EN: "Payment is not available for this order.",
    },
    "orders_payment_success": {
        Language.RU: "Оплата прошла успешно и товар доставлен ✅",
        Language.EN: "Payment successful and product delivered ✅",
    },
    "orders_payment_success_toast": {
        Language.RU: "Заказ оплачен",
        Language.EN: "Order paid",
    },
    "orders_delivery_message": {
        Language.RU: "🔑 Ваш товар:\n{payload}",
        Language.EN: "🔑 Your product:\n{payload}",
    },
    "orders_payload": {
        Language.RU: "🔑 Данные:\n{payload}",
        Language.EN: "🔑 Payload:\n{payload}",
    },
    "orders_status_pending": {Language.RU: "Ожидает оплаты", Language.EN: "Pending"},
    "orders_status_paid": {Language.RU: "Оплачен", Language.EN: "Paid"},
    "orders_status_delivered": {Language.RU: "Доставлен", Language.EN: "Delivered"},
    "orders_status_canceled": {Language.RU: "Отменен", Language.EN: "Canceled"},
    "nav_back": {Language.RU: "⬅️ Назад", Language.EN: "⬅️ Back"},
    "nav_main_menu": {Language.RU: "🏠 Главное меню", Language.EN: "🏠 Main menu"},
    "nav_next": {Language.RU: "➡️ Далее", Language.EN: "➡️ Next"},
    "nav_prev": {Language.RU: "⬅️ Назад", Language.EN: "⬅️ Prev"},
    "products_placeholder": {
        Language.RU: "Раздел товаров скоро будет доступен.",
        Language.EN: "Products section is coming soon.",
    },
    "products_empty": {
        Language.RU: "Категории пока не добавлены.",
        Language.EN: "No categories added yet.",
    },
    "products_root_title": {
        Language.RU: "Выберите категорию:",
        Language.EN: "Choose a category:",
    },
    "products_open_list": {
        Language.RU: "📋 Показать товары",
        Language.EN: "📋 Show products",
    },
    "products_back": {Language.RU: "⬅️ Назад", Language.EN: "⬅️ Back"},
    "products_main_menu": {Language.RU: "🏠 Главное меню", Language.EN: "🏠 Main menu"},
    "products_back_to_category": {Language.RU: "⬅️ К категории", Language.EN: "⬅️ Category"},
    "products_back_to_products": {Language.RU: "⬅️ К товарам", Language.EN: "⬅️ Back to products"},
    "products_buy": {Language.RU: "🛒 Купить", Language.EN: "🛒 Buy"},
    "products_open_product": {Language.RU: "🔎 Открыть", Language.EN: "🔎 Open"},
    "products_reserve_item": {Language.RU: "🛒 Резерв", Language.EN: "🛒 Reserve"},
    "products_category_not_found": {
        Language.RU: "Категория не найдена.",
        Language.EN: "Category not found.",
    },
    "products_price_missing": {
        Language.RU: "цена не задана",
        Language.EN: "price is not set",
    },
    "products_category_view": {
        Language.RU: "Категория: {title}\nПуть: {breadcrumb}\nТекущая цена: {price}\nОстаток: {stock}",
        Language.EN: "Category: {title}\nPath: {breadcrumb}\nCurrent price: {price}\nStock: {stock}",
    },
    "products_list_title": {
        Language.RU: "Товары в категории: {title}",
        Language.EN: "Products in category: {title}",
    },
    "products_breadcrumb_line": {
        Language.RU: "Путь: {path}",
        Language.EN: "Path: {path}",
    },
    "products_price_line": {
        Language.RU: "Цена: {price}",
        Language.EN: "Price: {price}",
    },
    "products_stock_line": {
        Language.RU: "Доступно: {stock}",
        Language.EN: "Available: {stock}",
    },
    "products_no_stock": {
        Language.RU: "Нет доступных товаров в наличии.",
        Language.EN: "No products available in stock.",
    },
    "products_card_line": {
        Language.RU: "{idx}. Товар #{product_id} · цена {price}",
        Language.EN: "{idx}. Product #{product_id} · price {price}",
    },
    "products_product_view": {
        Language.RU: "Товар #{product_id}\nКатегория: {title}\nПуть: {breadcrumb}\nЦена: {price}\nСтатус: доступен",
        Language.EN: "Product #{product_id}\nCategory: {title}\nPath: {breadcrumb}\nPrice: {price}\nStatus: available",
    },
    "products_product_not_available": {
        Language.RU: "Товар уже недоступен. Выберите другой из списка.",
        Language.EN: "This product is no longer available. Please choose another one.",
    },
    "products_reservation_success": {
        Language.RU: "Резерв создан ✅\nКатегория: {title}\nReservation ID: {reservation_id}\nOrder ID: {order_id}\nЦена: {price}\n\nСледующий шаг: откройте раздел заказов и оплатите резерв с баланса.",
        Language.EN: "Reservation created ✅\nCategory: {title}\nReservation ID: {reservation_id}\nOrder ID: {order_id}\nPrice: {price}\n\nNext step: open Orders and pay from balance.",
    },
    "products_reserved_toast": {
        Language.RU: "Товар зарезервирован",
        Language.EN: "Product reserved",
    },
    "top_up_main": {
        Language.RU: "💳 Пополнение\n\nТекущий баланс: {balance} {currency}\nВыберите действие:",
        Language.EN: "💳 Top Up\n\nCurrent balance: {balance} {currency}\nChoose an action:",
    },

    "top_up_my_requests": {Language.RU: "📄 Мои заявки", Language.EN: "📄 My requests"},
    "top_up_no_requests": {
        Language.RU: "У вас пока нет заявок на пополнение.",
        Language.EN: "You do not have top-up requests yet.",
    },
    "top_up_status_list_title": {
        Language.RU: "Последние заявки на пополнение:",
        Language.EN: "Recent top-up requests:",
    },
    "top_up_open_request_hint": {
        Language.RU: "Отправьте ID заявки (например, #12), чтобы увидеть детали.",
        Language.EN: "Send a request ID (for example, #12) to view details.",
    },
    "top_up_request_details": {
        Language.RU: "Детали заявки #{id}\nМетод: {method}\nСумма: {amount} {currency}\nСтатус: {status}\nTXID: {txid}\nUID отправителя: {sender_uid}\nВнешняя ссылка/референс: {external_reference}\nПроверенная сеть: {verified_network}\nПроверенный токен: {verified_token}\nПроверенная сумма: {verified_amount}\nКошелек получателя: {verified_recipient}\nСоздана: {created_at}\nПроверена: {reviewed_at}\nПримечание проверки: {verification_note}",
        Language.EN: "Request #{id} details\nMethod: {method}\nAmount: {amount} {currency}\nStatus: {status}\nTXID: {txid}\nSender UID: {sender_uid}\nExternal reference: {external_reference}\nVerified network: {verified_network}\nVerified token: {verified_token}\nVerified amount: {verified_amount}\nRecipient wallet: {verified_recipient}\nCreated at: {created_at}\nReviewed at: {reviewed_at}\nVerification note: {verification_note}",
    },
    "top_up_not_provided": {
        Language.RU: "—",
        Language.EN: "—",
    },
    "top_up_status_waiting_txid": {Language.RU: "Ожидает TXID", Language.EN: "Waiting for TXID"},
    "top_up_status_waiting_verification": {Language.RU: "На проверке", Language.EN: "Under verification"},
    "top_up_status_verified": {Language.RU: "Подтверждено", Language.EN: "Verified"},
    "top_up_status_rejected": {Language.RU: "Отклонено", Language.EN: "Rejected"},
    "top_up_status_expired": {Language.RU: "Истекло", Language.EN: "Expired"},
    "top_up_status_pending": {Language.RU: "В обработке", Language.EN: "Pending"},
    "top_up_method_crypto": {Language.RU: "🧾 Crypto by TXID", Language.EN: "🧾 Crypto by TXID"},
    "top_up_method_bybit": {Language.RU: "🏦 Bybit UID", Language.EN: "🏦 Bybit UID"},
    "top_up_cancel": {Language.RU: "❌ Отменить", Language.EN: "❌ Cancel"},
    "top_up_crypto_intro": {
        Language.RU: "Отправьте перевод и укажите TXID. Сначала выберите сеть/токен:",
        Language.EN: "Send a transfer and provide TXID. First choose network/token:",
    },
    "top_up_network_bsc_usdt": {Language.RU: "USDT BSC (BEP20)", Language.EN: "USDT BSC (BEP20)"},
    "top_up_network_invalid": {
        Language.RU: "Выберите сеть из кнопок ниже.",
        Language.EN: "Please choose a network from the buttons below.",
    },
    "top_up_enter_amount": {
        Language.RU: "Введите сумму пополнения (например, 1000 или 25.50):",
        Language.EN: "Enter top-up amount (for example, 1000 or 25.50):",
    },
    "top_up_amount_invalid": {
        Language.RU: "Некорректная сумма. Укажите число больше 0 с точностью до 2 знаков.",
        Language.EN: "Invalid amount. Enter a number greater than 0 with up to 2 decimal places.",
    },
    "top_up_request_summary": {
        Language.RU: "Заявка на пополнение создана ✅\nID: #{id}\nМетод: {method}\nСумма: {amount} {currency}\nСтатус: {status}\nПримечание: {note}",
        Language.EN: "Top-up request created ✅\nID: #{id}\nMethod: {method}\nAmount: {amount} {currency}\nStatus: {status}\nNote: {note}",
    },
    "top_up_enter_txid": {
        Language.RU: "Теперь отправьте TXID транзакции.",
        Language.EN: "Now send the transaction TXID.",
    },
    "top_up_txid_invalid": {
        Language.RU: "Некорректный TXID. Укажите строку без пробелов (минимум 8 символов).",
        Language.EN: "Invalid TXID. Enter a string without spaces (at least 8 characters).",
    },
    "top_up_txid_state_invalid": {
        Language.RU: "Нельзя обновить TXID: заявка уже не в статусе ожидания TXID.",
        Language.EN: "Cannot update TXID: request is no longer waiting for TXID.",
    },
    "top_up_request_not_found": {
        Language.RU: "Заявка не найдена. Попробуйте начать заново.",
        Language.EN: "Request not found. Please start again.",
    },
    "top_up_waiting_verification": {
        Language.RU: "Заявка #{id} отправлена на проверку. Текущий статус: {status}. Мы уведомим вас после проверки.",
        Language.EN: "Request #{id} was sent for review. Current status: {status}. We will notify you after verification.",
    },
    "top_up_bybit_intro": {
        Language.RU: "Пополнение через Bybit UID. Введите сумму, и мы создадим заявку.",
        Language.EN: "Top up via Bybit UID. Enter the amount and we will create a request.",
    },
    "top_up_bybit_reference_prompt": {
        Language.RU: "Отправьте UID отправителя Bybit (только цифры) или внешний референс платежа (минимум 6 символов).",
        Language.EN: "Send sender Bybit UID (digits only) or a payment external reference (at least 6 characters).",
    },
    "top_up_bybit_reference_invalid": {
        Language.RU: "Некорректный UID/референс. UID должен содержать 6-20 цифр, референс — 6-255 символов.",
        Language.EN: "Invalid UID/reference. UID must be 6-20 digits, reference must be 6-255 characters.",
    },
    "top_up_bybit_reference_state_invalid": {
        Language.RU: "Нельзя обновить Bybit UID/референс: заявка уже не в ожидаемом статусе.",
        Language.EN: "Cannot update Bybit UID/reference: request is no longer in expected status.",
    },
    "top_up_bybit_reference_submitted": {
        Language.RU: "UID/референс сохранен: {reference}",
        Language.EN: "UID/reference saved: {reference}",
    },
    "rules_placeholder": {
        Language.RU: "Правила будут опубликованы здесь.",
        Language.EN: "Rules will be published here.",
    },
    "support_placeholder": {
        Language.RU: "Поддержка: @support",
        Language.EN: "Support: @support",
    },
}


def t(key: str, language: Language) -> str:
    return TEXTS[key].get(language, TEXTS[key][Language.EN])
