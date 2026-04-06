import asyncio
from decimal import Decimal

from app.bot.money import format_money
from app.bot.state_utils import clear_admin_state


def test_format_money_uses_dollar_symbol() -> None:
    assert format_money(Decimal("10.00")) == "$10"
    assert format_money(Decimal("10.50")) == "$10.50"
    assert format_money("125") == "$125"


def test_clear_admin_state_only_for_admin_states() -> None:
    class DummyState:
        def __init__(self, state: str | None) -> None:
            self._state = state
            self.cleared = False

        async def get_state(self):
            return self._state

        async def clear(self):
            self.cleared = True

    admin_state = DummyState("AdminStates:wait_offers")
    asyncio.run(clear_admin_state(admin_state))
    assert admin_state.cleared is True

    top_up_state = DummyState("TopUpStates:choosing_method")
    asyncio.run(clear_admin_state(top_up_state))
    assert top_up_state.cleared is False
