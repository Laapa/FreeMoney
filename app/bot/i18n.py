from app.models.enums import Language

TEXTS: dict[str, dict[Language, str]] = {
    "start": {
        Language.RU: "Добро пожаловать в WEBSTER-SHOP! Выберите действие в меню ниже.",
        Language.EN: "Welcome to WEBSTER-SHOP! Choose an action from the menu below.",
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
    "menu_admin": {Language.RU: "🛠 Админка", Language.EN: "🛠 Admin"},
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
    "orders_item_line": {
        Language.RU: "🛍 Товар: {item}",
        Language.EN: "🛍 Item: {item}",
    },
    "orders_details_delivered_at": {
        Language.RU: "✅ Доставлен: {delivered_at}",
        Language.EN: "✅ Delivered: {delivered_at}",
    },
    "orders_action_pay": {
        Language.RU: "💸 Внешняя оплата",
        Language.EN: "💸 External pay",
    },
    "orders_action_pay_balance": {
        Language.RU: "💰 Оплатить с баланса",
        Language.EN: "💰 Pay with balance",
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
    "orders_status_processing": {Language.RU: "В обработке", Language.EN: "Processing"},
    "orders_status_delivered": {Language.RU: "Доставлен", Language.EN: "Delivered"},
    "orders_status_canceled": {Language.RU: "Отменен", Language.EN: "Canceled"},
    "orders_action_check_payment": {Language.RU: "🔄 Проверить оплату", Language.EN: "🔄 Check payment"},
    "orders_action_open_payment": {Language.RU: "💳 Перейти к оплате", Language.EN: "💳 Proceed to payment"},
    "orders_action_open_activation": {Language.RU: "🚀 Открыть активатор", Language.EN: "🚀 Open activation page"},
    "orders_action_cancel_payment": {Language.RU: "❌ Отменить оплату", Language.EN: "❌ Cancel payment"},
    "orders_payment_screen": {
        Language.RU: "Оплата заказа #{id}\nТовар: {title}\nЦена товара (net): {amount} {currency}\nКомиссия: {fee_amount} {currency}\nК оплате (gross): {gross_amount} {currency}\nМетод: {method}\nСоздан: {created_at}\nОплатить до: {deadline}",
        Language.EN: "Order #{id} payment\nItem: {title}\nItem price (net): {amount} {currency}\nFee: {fee_amount} {currency}\nTo pay (gross): {gross_amount} {currency}\nMethod: {method}\nCreated: {created_at}\nPay until: {deadline}",
    },
    "orders_bybit_via_balance_hint": {
        Language.RU: "Bybit: пополните баланс через раздел «💳 Пополнить», затем оплатите заказ кнопкой «💰 Оплатить с баланса».",
        Language.EN: "Bybit: top up balance in “💳 Top Up”, then pay order with “💰 Pay with balance”.",
    },
    "orders_payment_pending": {
        Language.RU: "Оплата еще не подтверждена.",
        Language.EN: "Payment is not confirmed yet.",
    },
    "orders_payment_expired": {
        Language.RU: "Счет истек. Создайте оплату заново.",
        Language.EN: "Invoice expired. Please create payment again.",
    },
    "orders_payment_invalid": {
        Language.RU: "Счет недействителен или не найден.",
        Language.EN: "Invoice is invalid or was not found.",
    },
    "orders_payment_unavailable": {
        Language.RU: "Провайдер оплаты временно недоступен. Попробуйте позже.",
        Language.EN: "Payment provider is temporarily unavailable. Please retry later.",
    },
    "orders_payment_canceled": {
        Language.RU: "Оплата отменена.",
        Language.EN: "Payment canceled.",
    },
    "orders_fulfillment_direct_stock": {Language.RU: "мгновенная выдача", Language.EN: "instant delivery"},
    "orders_fulfillment_activation_task": {Language.RU: "активация", Language.EN: "activation"},
    "orders_fulfillment_manual_supplier": {Language.RU: "под заказ", Language.EN: "manual supplier"},
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
    "products_fulfillment_line": {
        Language.RU: "Исполнение: {fulfillment}",
        Language.EN: "Fulfillment: {fulfillment}",
    },
    "products_availability_line": {
        Language.RU: "Наличие: {availability}",
        Language.EN: "Availability: {availability}",
    },
    "products_availability_activation": {Language.RU: "по активации", Language.EN: "activation queue"},
    "products_availability_supplier": {Language.RU: "под заказ", Language.EN: "supplier order"},
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
    "products_offer_view": {
        Language.RU: "Товар: {title}\nОписание: {description}\nЦена: {price}\nИсполнение: {fulfillment}\nДоступность: {availability}",
        Language.EN: "Offer: {title}\nDescription: {description}\nPrice: {price}\nFulfillment: {fulfillment}\nAvailability: {availability}",
    },
    "products_product_not_available": {
        Language.RU: "Товар уже недоступен. Выберите другой из списка.",
        Language.EN: "This product is no longer available. Please choose another one.",
    },
    "products_reservation_success": {
        Language.RU: (
            "Резерв создан ✅\n"
            "Категория: {title}\n"
            "Reservation ID: {reservation_id}\n"
            "Order ID: {order_id}\n"
            "Цена: {price}\n\n"
            "Резерв действует {ttl_minutes} минут.\n"
            "Откройте раздел заказов и оплатите резерв в течение {ttl_minutes} минут."
        ),
        Language.EN: (
            "Reservation created ✅\n"
            "Category: {title}\n"
            "Reservation ID: {reservation_id}\n"
            "Order ID: {order_id}\n"
            "Price: {price}\n\n"
            "Reservation is valid for {ttl_minutes} minutes.\n"
            "Open Orders and pay this reservation within {ttl_minutes} minutes."
        ),
    },
    "products_order_created_success": {
        Language.RU: (
            "Заказ создан ✅\n"
            "Категория: {title}\n"
            "Order ID: {order_id}\n"
            "Цена: {price}\n\n"
            "Откройте раздел заказов и оплатите заказ."
        ),
        Language.EN: (
            "Order created ✅\n"
            "Category: {title}\n"
            "Order ID: {order_id}\n"
            "Price: {price}\n\n"
            "Open Orders and pay for this order."
        ),
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
        Language.RU: "Детали заявки #{id}\nМетод: {method}\nК зачислению (net): {amount} {currency}\nКомиссия: {fee_amount} {currency}\nК оплате (gross): {gross_amount} {currency}\nСтатус: {status}\nTXID: {txid}\nUID отправителя: {sender_uid}\nВнешняя ссылка/референс: {external_reference}\nПроверенная сеть: {verified_network}\nПроверенный токен: {verified_token}\nПроверенная сумма: {verified_amount}\nКошелек получателя: {verified_recipient}\nСоздана: {created_at}\nПроверена: {reviewed_at}\nПримечание проверки: {verification_note}",
        Language.EN: "Request #{id} details\nMethod: {method}\nTo credit (net): {amount} {currency}\nFee: {fee_amount} {currency}\nTo pay (gross): {gross_amount} {currency}\nStatus: {status}\nTXID: {txid}\nSender UID: {sender_uid}\nExternal reference: {external_reference}\nVerified network: {verified_network}\nVerified token: {verified_token}\nVerified amount: {verified_amount}\nRecipient wallet: {verified_recipient}\nCreated at: {created_at}\nReviewed at: {reviewed_at}\nVerification note: {verification_note}",
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
    "top_up_method_crypto": {Language.RU: "🧾 Crypto Pay", Language.EN: "🧾 Crypto Pay"},
    "top_up_method_bybit": {Language.RU: "🏦 Bybit UID", Language.EN: "🏦 Bybit UID"},
    "top_up_cancel": {Language.RU: "❌ Отменить", Language.EN: "❌ Cancel"},
    "top_up_crypto_intro": {
        Language.RU: "Пополнение через Crypto Pay invoice. Введите сумму, которую хотите получить на баланс (net).",
        Language.EN: "Top up via Crypto Pay invoice. Enter amount you want to receive on balance (net).",
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
        Language.RU: "Заявка на пополнение создана ✅\nID: #{id}\nМетод: {method}\nК зачислению (net): {amount} {currency}\nКомиссия: {fee_amount} {currency}\nК оплате (gross): {gross_amount} {currency}\nСтатус: {status}\nПримечание: {note}",
        Language.EN: "Top-up request created ✅\nID: #{id}\nMethod: {method}\nTo credit (net): {amount} {currency}\nFee: {fee_amount} {currency}\nTo pay (gross): {gross_amount} {currency}\nStatus: {status}\nNote: {note}",
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
        Language.RU: "Пополнение через Bybit. Введите сумму, которую хотите получить на баланс (net).",
        Language.EN: "Top up via Bybit. Enter amount you want to receive on balance (net).",
    },

    "top_up_crypto_invoice_created": {
        Language.RU: "Откройте ссылку в примечании и оплатите Crypto Pay invoice. После оплаты откройте заявку снова (#ID), статус обновится автоматически.",
        Language.EN: "Open the link in note and pay the Crypto Pay invoice. After payment open request again (#ID), status will auto-refresh.",
    },
    "top_up_crypto_invoice_failed": {
        Language.RU: "Не удалось создать invoice Crypto Pay. Проверьте настройки и попробуйте позже.",
        Language.EN: "Failed to create Crypto Pay invoice. Check settings and try later.",
    },

    "top_up_bybit_unavailable": {
        Language.RU: "Пополнение Bybit временно недоступно: не настроен UID получателя.",
        Language.EN: "Bybit top up is temporarily unavailable: recipient UID is not configured.",
    },
    "top_up_bybit_transfer_instruction": {
        Language.RU: "Переведите ровно {gross_amount} {currency} на Bybit UID получателя: {recipient_uid}\nКомментарий/инструкция: {recipient_note}",
        Language.EN: "Send exactly {gross_amount} {currency} to recipient Bybit UID: {recipient_uid}\nComment/instruction: {recipient_note}",
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
    "top_up_bybit_auto_verified": {
        Language.RU: "Bybit auto-verify: заявка #{id} подтверждена автоматически, зачислено {amount} {currency}.",
        Language.EN: "Bybit auto-verify: request #{id} was verified automatically, credited {amount} {currency}.",
    },
    "top_up_bybit_auto_pending": {
        Language.RU: "Bybit auto-verify включен, но платеж пока не найден. Заявка остается на проверке.",
        Language.EN: "Bybit auto-verify is enabled, but payment is not found yet. Request stays under verification.",
    },
    "top_up_bybit_reference_submitted": {
        Language.RU: "UID/референс сохранен: {reference}. Запущена автоматическая проверка платежа.",
        Language.EN: "UID/reference saved: {reference}. Automatic payment verification has started.",
    },
    "rules_placeholder": {
        Language.RU: "Правила WEBSTER-SHOP будут опубликованы здесь.",
        Language.EN: "WEBSTER-SHOP rules will be published here.",
    },
    "support_placeholder": {
        Language.RU: "Поддержка WEBSTER-SHOP: @support",
        Language.EN: "WEBSTER-SHOP support: @support",
    },
}


def t(key: str, language: Language) -> str:
    return TEXTS[key].get(language, TEXTS[key][Language.EN])
