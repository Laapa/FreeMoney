from __future__ import annotations

from decimal import Decimal


def format_money(value: Decimal | int | float | str) -> str:
    amount = Decimal(str(value))
    normalized = amount.normalize()
    if normalized == normalized.to_integral():
        return f"${int(normalized)}"
    return f"${amount.quantize(Decimal('0.01'))}"
