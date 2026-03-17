from app.models.enums import TopUpStatus
from app.models.top_up_request import TopUpRequest


class TopUpRequestTransitionError(ValueError):
    pass


_ALLOWED_STATUS_TRANSITIONS: dict[TopUpStatus, set[TopUpStatus]] = {
    TopUpStatus.PENDING: {TopUpStatus.WAITING_VERIFICATION},
    TopUpStatus.WAITING_TXID: {TopUpStatus.WAITING_VERIFICATION},
    TopUpStatus.WAITING_VERIFICATION: {
        TopUpStatus.VERIFIED,
        TopUpStatus.REJECTED,
        TopUpStatus.EXPIRED,
    },
    TopUpStatus.VERIFIED: set(),
    TopUpStatus.REJECTED: set(),
    TopUpStatus.EXPIRED: set(),
}


def ensure_top_up_status_transition(request: TopUpRequest, target_status: TopUpStatus) -> None:
    allowed_targets = _ALLOWED_STATUS_TRANSITIONS.get(request.status, set())
    if target_status not in allowed_targets:
        raise TopUpRequestTransitionError(
            f"Invalid top-up status transition: {request.status.value} -> {target_status.value}"
        )

