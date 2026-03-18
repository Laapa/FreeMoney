from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.enums import Currency, TopUpMethod, TopUpStatus
from app.models.user import User
from app.services.blockchain.tx_verification import (
    BlockchainVerificationReason,
    BlockchainVerificationResult,
    BlockchainVerificationSuccess,
)
from app.services.top_up_requests import create_top_up_request, set_bybit_sender_reference, set_top_up_txid
from app.services.top_up_verification import TopUpVerificationError, verify_bybit_uid_top_up, verify_crypto_txid_top_up


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _create_waiting_verification_request(db: Session, *, telegram_id: int = 9001) -> tuple[User, int]:
    user = User(telegram_id=telegram_id, balance=Decimal("10.00"))
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("25.00"),
        currency=Currency.USD,
        requested_network="bsc",
        requested_token="usdt",
    )
    request = set_top_up_txid(db, request=request, txid="abcdef12345")
    return user, request.id


class FakeVerifier:
    def __init__(self, result: BlockchainVerificationResult) -> None:
        self._result = result

    def verify_transfer(self, **_kwargs) -> BlockchainVerificationResult:
        return self._result


def _create_waiting_verification_bybit_request(db: Session, *, telegram_id: int = 9101) -> tuple[User, int]:
    user = User(telegram_id=telegram_id, balance=Decimal("10.00"))
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("20.00"),
        currency=Currency.USD,
    )
    request = set_bybit_sender_reference(db, request=request, sender_uid="12345678")
    return user, request.id


def test_verify_top_up_request_credits_balance_once() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=FakeVerifier(
            BlockchainVerificationResult(
                ok=True,
                data=BlockchainVerificationSuccess(
                    tx_hash="abcdef12345",
                    network="bsc",
                    token="usdt",
                    amount=Decimal("25.00"),
                    recipient="0xrecipient",
                    raw_reference="explorer:https://api.bscscan.com/api",
                ),
            )
        ),
    )

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.VERIFIED
    assert result.request.credited_at is not None
    assert result.request.verified_network == "bsc"
    assert result.request.verified_token == "usdt"
    assert result.request.verified_amount == Decimal("25.00")
    assert result.request.verified_recipient == "0xrecipient"
    assert user.balance == Decimal("35.00")


def test_rejected_request_does_not_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.REJECTED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.REJECTED
    assert result.request.credited_at is None
    assert user.balance == Decimal("10.00")


def test_expired_request_does_not_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.EXPIRED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.EXPIRED
    assert result.request.credited_at is None
    assert user.balance == Decimal("10.00")


def test_invalid_status_transition_is_prevented() -> None:
    db = make_session()
    user = User(telegram_id=9002)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("15.00"),
        currency=Currency.USD,
    )

    result = verify_crypto_txid_top_up(db, request_id=request.id, target_status=TopUpStatus.VERIFIED)

    assert result.ok is False
    assert result.error == TopUpVerificationError.TXID_MISSING


def test_duplicate_verification_does_not_double_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    verifier = FakeVerifier(
        BlockchainVerificationResult(
            ok=True,
            data=BlockchainVerificationSuccess(
                tx_hash="abcdef12345",
                network="bsc",
                token="usdt",
                amount=Decimal("25.00"),
                recipient="0xrecipient",
                raw_reference="explorer:https://api.bscscan.com/api",
            ),
        )
    )
    first = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED, evm_verifier=verifier)
    second = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=verifier,
    )

    db.refresh(user)
    assert first.ok is True
    assert second.ok is False
    assert second.error == TopUpVerificationError.ALREADY_CREDITED
    assert user.balance == Decimal("35.00")


def test_verified_request_cannot_be_rejected_or_expired_later() -> None:
    db = make_session()
    _, request_id = _create_waiting_verification_request(db)

    verified = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=FakeVerifier(
            BlockchainVerificationResult(
                ok=True,
                data=BlockchainVerificationSuccess(
                    tx_hash="abcdef12345",
                    network="bsc",
                    token="usdt",
                    amount=Decimal("25.00"),
                    recipient="0xrecipient",
                    raw_reference="explorer:https://api.bscscan.com/api",
                ),
            )
        ),
    )
    rejected = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.REJECTED)
    expired = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.EXPIRED)

    assert verified.ok is True
    assert rejected.ok is False
    assert rejected.error == TopUpVerificationError.INVALID_SOURCE_STATUS
    assert expired.ok is False
    assert expired.error == TopUpVerificationError.INVALID_SOURCE_STATUS


def test_rejected_or_expired_cannot_become_verified() -> None:
    db = make_session()
    _, rejected_request_id = _create_waiting_verification_request(db, telegram_id=9010)
    _, expired_request_id = _create_waiting_verification_request(db, telegram_id=9011)

    rejected = verify_crypto_txid_top_up(db, request_id=rejected_request_id, target_status=TopUpStatus.REJECTED)
    rejected_then_verified = verify_crypto_txid_top_up(
        db,
        request_id=rejected_request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=FakeVerifier(
            BlockchainVerificationResult(
                ok=True,
                data=BlockchainVerificationSuccess(
                    tx_hash="abcdef12345",
                    network="bsc",
                    token="usdt",
                    amount=Decimal("25.00"),
                    recipient="0xrecipient",
                    raw_reference="explorer:https://api.bscscan.com/api",
                ),
            )
        ),
    )

    expired = verify_crypto_txid_top_up(db, request_id=expired_request_id, target_status=TopUpStatus.EXPIRED)
    expired_then_verified = verify_crypto_txid_top_up(
        db,
        request_id=expired_request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=FakeVerifier(
            BlockchainVerificationResult(
                ok=True,
                data=BlockchainVerificationSuccess(
                    tx_hash="abcdef12345",
                    network="bsc",
                    token="usdt",
                    amount=Decimal("25.00"),
                    recipient="0xrecipient",
                    raw_reference="explorer:https://api.bscscan.com/api",
                ),
            )
        ),
    )

    assert rejected.ok is True
    assert rejected_then_verified.ok is False
    assert rejected_then_verified.error == TopUpVerificationError.INVALID_SOURCE_STATUS
    assert expired.ok is True
    assert expired_then_verified.ok is False
    assert expired_then_verified.error == TopUpVerificationError.INVALID_SOURCE_STATUS


def test_user_scope_check_blocks_foreign_request() -> None:
    db = make_session()
    owner, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.REJECTED,
        reviewed_by_user_id=owner.id + 1,
    )

    assert result.ok is False
    assert result.error == TopUpVerificationError.ACCESS_DENIED


def test_crypto_verification_wrong_recipient_fails() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db, telegram_id=9020)

    result = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=FakeVerifier(
            BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.RECIPIENT_MISMATCH,
                note="Unexpected recipient",
            )
        ),
    )

    db.refresh(user)
    assert result.ok is False
    assert result.error == TopUpVerificationError.ON_CHAIN_VERIFICATION_FAILED
    assert user.balance == Decimal("10.00")
    assert result.request is not None
    assert result.request.status == TopUpStatus.WAITING_VERIFICATION


def test_crypto_verification_wrong_amount_fails() -> None:
    db = make_session()
    _, request_id = _create_waiting_verification_request(db, telegram_id=9021)

    result = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=FakeVerifier(
            BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.AMOUNT_TOO_LOW,
                note="Too small amount",
            )
        ),
    )

    assert result.ok is False
    assert result.error == TopUpVerificationError.ON_CHAIN_VERIFICATION_FAILED


def test_crypto_verification_wrong_tx_status_fails() -> None:
    db = make_session()
    _, request_id = _create_waiting_verification_request(db, telegram_id=9022)

    result = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=FakeVerifier(
            BlockchainVerificationResult(
                ok=False,
                reason=BlockchainVerificationReason.TX_FAILED,
                note="status 0x0",
            )
        ),
    )

    assert result.ok is False
    assert result.error == TopUpVerificationError.ON_CHAIN_VERIFICATION_FAILED


def test_verify_bybit_request_credits_balance_once() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_bybit_request(db)

    result = verify_bybit_uid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.VERIFIED
    assert result.request.credited_at is not None
    assert user.balance == Decimal("30.00")


def test_bybit_rejected_request_does_not_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_bybit_request(db)

    result = verify_bybit_uid_top_up(db, request_id=request_id, target_status=TopUpStatus.REJECTED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.REJECTED
    assert result.request.credited_at is None
    assert user.balance == Decimal("10.00")


def test_bybit_expired_request_does_not_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_bybit_request(db)

    result = verify_bybit_uid_top_up(db, request_id=request_id, target_status=TopUpStatus.EXPIRED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.EXPIRED
    assert result.request.credited_at is None
    assert user.balance == Decimal("10.00")


def test_bybit_wrong_method_cannot_use_verification_service() -> None:
    db = make_session()
    _, request_id = _create_waiting_verification_request(db)

    result = verify_bybit_uid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED)

    assert result.ok is False
    assert result.error == TopUpVerificationError.INVALID_METHOD


def test_bybit_duplicate_verification_does_not_double_credit() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_bybit_request(db)

    first = verify_bybit_uid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED)
    second = verify_bybit_uid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED)

    db.refresh(user)
    assert first.ok is True
    assert second.ok is False
    assert second.error == TopUpVerificationError.ALREADY_CREDITED
    assert user.balance == Decimal("30.00")
