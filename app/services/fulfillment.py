from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.activation.client import ActivationAPIClient, ActivationClientError
from app.core.config import get_settings
from app.models.enums import FulfillmentStatus, FulfillmentType, OrderStatus
from app.models.order import Order
from app.services.activation import _extract_task_id, _extract_task_status, ActivationStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActivationDispatchResult:
    ok: bool
    reason: str


def _activation_client() -> ActivationAPIClient:
    settings = get_settings()
    return ActivationAPIClient(
        base_url=settings.activation_api_base_url,
        timeout_seconds=settings.activation_api_timeout_seconds,
    )


def dispatch_activation_task_for_order(
    db: Session,
    *,
    order: Order,
    client: ActivationAPIClient | None = None,
) -> ActivationDispatchResult:
    if order.fulfillment_type != FulfillmentType.ACTIVATION_TASK:
        return ActivationDispatchResult(ok=False, reason="not_activation_order")
    if order.external_task_id:
        return ActivationDispatchResult(ok=True, reason="already_dispatched")

    activation_client = client or _activation_client()
    payload = {
        "order_id": order.id,
        "user_id": order.user_id,
        "offer_id": order.offer_id,
    }
    try:
        response = activation_client.create_task(code_hash=f"order-{order.id}", user_token=payload)
    except ActivationClientError as exc:
        logger.warning("Activation task create failed | order_id=%s error=%s", order.id, str(exc))
        order.supplier_note = "Activation supplier unavailable; order kept in processing."
        db.commit()
        return ActivationDispatchResult(ok=False, reason="supplier_unavailable")

    task_id = _extract_task_id(response)
    if not task_id:
        logger.warning("Activation task id missing | order_id=%s payload=%s", order.id, response.payload)
        order.supplier_note = response.message or "Activation task was not accepted by supplier."
        db.commit()
        return ActivationDispatchResult(ok=False, reason="task_id_missing")

    order.external_task_id = task_id
    order.supplier_note = "Activation task created and queued."
    db.commit()
    return ActivationDispatchResult(ok=True, reason="dispatched")


def refresh_activation_task_status(
    db: Session,
    *,
    order: Order,
    client: ActivationAPIClient | None = None,
    now: datetime | None = None,
) -> ActivationDispatchResult:
    if order.fulfillment_type != FulfillmentType.ACTIVATION_TASK:
        return ActivationDispatchResult(ok=False, reason="not_activation_order")
    if not order.external_task_id:
        return ActivationDispatchResult(ok=False, reason="task_id_missing")

    activation_client = client or _activation_client()
    try:
        response = activation_client.check_task(order.external_task_id)
    except ActivationClientError as exc:
        logger.warning("Activation task check failed | order_id=%s task_id=%s error=%s", order.id, order.external_task_id, str(exc))
        return ActivationDispatchResult(ok=False, reason="supplier_unavailable")

    task_status = _extract_task_status(response)
    if task_status == ActivationStatus.SUCCESS:
        order.status = OrderStatus.DELIVERED
        order.fulfillment_status = FulfillmentStatus.DELIVERED
        order.delivered_at = now or datetime.utcnow()
        order.supplier_note = response.message or "Activation completed by supplier."
        db.commit()
        return ActivationDispatchResult(ok=True, reason="completed")

    if task_status == ActivationStatus.FAILED:
        order.fulfillment_status = FulfillmentStatus.FAILED
        order.supplier_note = response.message or "Activation failed at supplier side."
        db.commit()
        return ActivationDispatchResult(ok=False, reason="failed")

    order.status = OrderStatus.PROCESSING
    order.fulfillment_status = FulfillmentStatus.PROCESSING
    order.supplier_note = response.message or "Activation task is still processing."
    db.commit()
    return ActivationDispatchResult(ok=False, reason="pending")
