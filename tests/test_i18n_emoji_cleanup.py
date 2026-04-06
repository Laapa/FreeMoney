from app.bot.i18n import t
from app.models.enums import Language


def test_orders_user_facing_strings_have_no_extra_emoji() -> None:
    assert "🛍" not in t("orders_item_line", Language.RU)
    assert "💳" not in t("orders_action_top_up", Language.RU)
    assert "💳" not in t("orders_action_open_payment", Language.RU)

    assert "🛍" not in t("orders_item_line", Language.EN)
    assert "💳" not in t("orders_action_top_up", Language.EN)
    assert "💳" not in t("orders_action_open_payment", Language.EN)
