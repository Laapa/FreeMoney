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
        Language.RU: "ID: {id}\nUsername: {username}\nЯзык: {language}\nБаланс: {balance} {currency}",
        Language.EN: "ID: {id}\nUsername: {username}\nLanguage: {language}\nBalance: {balance} {currency}",
    },
    "orders_empty": {Language.RU: "У вас пока нет заказов.", Language.EN: "You have no orders yet."},
    "orders_title": {Language.RU: "Ваши заказы:", Language.EN: "Your orders:"},
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
    "top_up_placeholder": {
        Language.RU: "Пополнение будет добавлено на следующем этапе.",
        Language.EN: "Top up will be added in the next step.",
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
