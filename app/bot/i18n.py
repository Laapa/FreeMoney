from app.models.enums import Language

TEXTS: dict[str, dict[Language, str]] = {
    "start": {
        Language.RU: "Добро пожаловать в FreeMoney! Выберите действие в меню ниже.",
        Language.EN: "Welcome to FreeMoney! Choose an action from the menu below.",
    },
    "menu_products": {Language.RU: "🛍 Товары", Language.EN: "🛍 Products"},
    "menu_top_up": {Language.RU: "💳 Пополнить", Language.EN: "💳 Top Up"},
    "menu_profile": {Language.RU: "👤 Профиль", Language.EN: "👤 Profile"},
    "menu_orders": {Language.RU: "📦 Заказы", Language.EN: "📦 Orders"},
    "menu_rules": {Language.RU: "📜 Правила", Language.EN: "📜 Rules"},
    "menu_support": {Language.RU: "🛟 Поддержка", Language.EN: "🛟 Support"},
    "profile_title": {Language.RU: "Ваш профиль", Language.EN: "Your profile"},
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
    "products_reservation_success": {
        Language.RU: "Резерв создан ✅\nКатегория: {title}\nReservation ID: {reservation_id}\nOrder ID: {order_id}\nЦена: {price}\n\nСледующий шаг: оплата (будет добавлена на следующем этапе).",
        Language.EN: "Reservation created ✅\nCategory: {title}\nReservation ID: {reservation_id}\nOrder ID: {order_id}\nPrice: {price}\n\nNext step: payment (placeholder for next iteration).",
    },
    "products_reserved_toast": {
        Language.RU: "Товар зарезервирован",
        Language.EN: "Product reserved",
    },
    "top_up_main": {
        Language.RU: "💳 Пополнение\n\nТекущий баланс: {balance} {currency}\nВыберите способ пополнения:",
        Language.EN: "💳 Top Up\n\nCurrent balance: {balance} {currency}\nChoose a top-up method:",
    },
    "top_up_method_crypto": {Language.RU: "🧾 Crypto by TXID", Language.EN: "🧾 Crypto by TXID"},
    "top_up_method_bybit": {Language.RU: "🏦 Bybit UID", Language.EN: "🏦 Bybit UID"},
    "top_up_cancel": {Language.RU: "❌ Отменить", Language.EN: "❌ Cancel"},
    "top_up_crypto_intro": {
        Language.RU: "Отправьте перевод и укажите TXID. Сначала выберите сеть/токен:",
        Language.EN: "Send a transfer and provide TXID. First choose network/token:",
    },
    "top_up_network_trc20": {Language.RU: "USDT TRC20", Language.EN: "USDT TRC20"},
    "top_up_network_erc20": {Language.RU: "USDT ERC20", Language.EN: "USDT ERC20"},
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
    "top_up_request_not_found": {
        Language.RU: "Заявка не найдена. Попробуйте начать заново.",
        Language.EN: "Request not found. Please start again.",
    },
    "top_up_waiting_verification": {
        Language.RU: "Заявка #{id} переведена в статус {status}. Проверка платежа будет добавлена позже.",
        Language.EN: "Request #{id} is now in {status} status. Payment verification will be implemented later.",
    },
    "top_up_bybit_intro": {
        Language.RU: "Пополнение через Bybit UID. Введите сумму, и мы создадим заявку.",
        Language.EN: "Top up via Bybit UID. Enter the amount and we will create a request.",
    },
    "top_up_bybit_instructions": {
        Language.RU: "Инструкция (заглушка): отправьте перевод на наш Bybit UID. Подтверждение будет добавлено позже.",
        Language.EN: "Instructions (placeholder): send transfer to our Bybit UID. Verification will be added later.",
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
