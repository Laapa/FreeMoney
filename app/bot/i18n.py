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
