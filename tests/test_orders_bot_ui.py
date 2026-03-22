from app.bot.keyboards.account import order_details_keyboard
from app.bot.i18n import t
from app.models.enums import Language


def test_activation_link_button_is_present_when_url_provided() -> None:
    keyboard = order_details_keyboard(
        language=Language.EN,
        order_id=1,
        can_pay=False,
        show_top_up=False,
        activation_url="https://shop.example/activation",
    )

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    activation_button = next((button for button in buttons if button.text == t("orders_action_open_activation", Language.EN)), None)
    assert activation_button is not None
    assert activation_button.url == "https://shop.example/activation"


def test_activation_link_button_absent_when_url_missing() -> None:
    keyboard = order_details_keyboard(
        language=Language.RU,
        order_id=1,
        can_pay=False,
        show_top_up=False,
    )

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert all(button.text != t("orders_action_open_activation", Language.RU) for button in buttons)
