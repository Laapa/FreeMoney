from enum import Enum


class Language(str, Enum):
    RU = "ru"
    EN = "en"


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"


class ProductStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"


class ReservationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CONVERTED = "converted"
    CANCELED = "canceled"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    DELIVERED = "delivered"
    CANCELED = "canceled"


class PaymentStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"


class TopUpMethod(str, Enum):
    CRYPTO_TXID = "crypto_txid"
    BYBIT_UID = "bybit_uid"


class TopUpStatus(str, Enum):
    PENDING = "pending"
    WAITING_TXID = "waiting_txid"
    WAITING_VERIFICATION = "waiting_verification"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class LogEventType(str, Enum):
    RESERVATION_CREATED = "reservation_created"
    RESERVATION_EXPIRED = "reservation_expired"
    PAYMENT_FAILED = "payment_failed"
    SALE_COMPLETED = "sale_completed"
    DELIVERY_COMPLETED = "delivery_completed"
    TOP_UP_REQUEST_CREATED = "top_up_request_created"
    TOP_UP_WAITING_VERIFICATION = "top_up_waiting_verification"
