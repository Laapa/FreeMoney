from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.core.config import get_settings

_MONEY_Q = Decimal("0.01")


@dataclass(frozen=True)
class FeeBreakdown:
    net_amount: Decimal
    fee_amount: Decimal
    gross_amount: Decimal
    fee_percent: Decimal


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_MONEY_Q, rounding=ROUND_HALF_UP)


def calculate_external_fee(net_amount: Decimal, *, fee_percent: Decimal | None = None) -> FeeBreakdown:
    percent = fee_percent if fee_percent is not None else get_settings().transaction_fee_percent
    net = quantize_money(net_amount)
    fee = quantize_money((net * Decimal(percent)) / Decimal("100"))
    gross = quantize_money(net + fee)
    return FeeBreakdown(net_amount=net, fee_amount=fee, gross_amount=gross, fee_percent=Decimal(percent))
