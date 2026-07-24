"""Persistence models for the Start Shape Ship Academy card offer.

These tables intentionally do not store Stripe payloads, credentials, payment
method details, or card data. Stripe's identifiers are enough to reconcile the
inbox and refunds without duplicating sensitive payment records.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcademyPaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class AcademyEnrollmentStatus(str, Enum):
    PENDING = "pending"
    ENROLLED = "enrolled"
    FAILED = "failed"


class AcademyEventStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class AcademyRefundStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class AcademyPurchase(SQLModel, table=True):
    """One logical Academy purchase, optionally linked to a Stripe Checkout Session."""

    __tablename__ = "academy_purchase"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_academy_purchase_amount_positive"),
        CheckConstraint("quantity > 0", name="ck_academy_purchase_quantity_positive"),
        UniqueConstraint("purchase_uuid", name="uq_academy_purchase_purchase_uuid"),
        UniqueConstraint("checkout_session_id", name="uq_academy_purchase_checkout_session"),
        UniqueConstraint("payment_intent_id", name="uq_academy_purchase_payment_intent"),
        UniqueConstraint("charge_id", name="uq_academy_purchase_charge"),
        Index("ix_academy_purchase_learner", "learner_id"),
        Index("ix_academy_purchase_course_org", "course_id", "org_id"),
        Index("ix_academy_purchase_payment_status", "payment_status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_uuid: str = Field(
        default_factory=lambda: str(uuid4()),
        sa_column=Column(String(36), nullable=False),
    )
    checkout_session_id: Optional[str] = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    learner_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="RESTRICT"), nullable=False)
    )
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="RESTRICT"), nullable=False)
    )

    # Immutable offer snapshot: later catalog/config changes must not alter the
    # amount or entitlement represented by this purchase.
    price_id: str = Field(sa_column=Column(String(255), nullable=False))
    product_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    amount: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False))
    quantity: int = Field(default=1, sa_column=Column(Integer, nullable=False, server_default="1"))

    payment_status: AcademyPaymentStatus = Field(
        default=AcademyPaymentStatus.PENDING,
        sa_column=Column(String(32), nullable=False, server_default="pending"),
    )
    enrollment_status: AcademyEnrollmentStatus = Field(
        default=AcademyEnrollmentStatus.PENDING,
        sa_column=Column(String(32), nullable=False, server_default="pending"),
    )
    payment_intent_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    charge_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))

    retry_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    last_error: Optional[str] = Field(default=None, sa_column=Column(String(2000), nullable=True))
    error_retryable: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    next_retry_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    paid_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    enrolled_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class AcademyStripeEvent(SQLModel, table=True):
    """Inbox row for each Stripe event; multiple events may reference a purchase."""

    __tablename__ = "academy_stripe_event"
    __table_args__ = (
        UniqueConstraint("stripe_event_id", name="uq_academy_stripe_event_event_id"),
        Index("ix_academy_stripe_event_purchase", "purchase_id"),
        Index("ix_academy_stripe_event_status", "status"),
        Index("ix_academy_stripe_event_refund", "stripe_refund_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    stripe_event_id: str = Field(sa_column=Column(String(255), nullable=False))
    event_type: str = Field(sa_column=Column(String(100), nullable=False))
    purchase_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("academy_purchase.id", ondelete="SET NULL"), nullable=True),
    )
    checkout_session_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    payment_intent_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    charge_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    stripe_refund_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))

    status: AcademyEventStatus = Field(
        default=AcademyEventStatus.RECEIVED,
        sa_column=Column(String(32), nullable=False, server_default="received"),
    )
    retry_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    last_error: Optional[str] = Field(default=None, sa_column=Column(String(2000), nullable=True))
    error_retryable: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    next_retry_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    received_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    processed_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    updated_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AcademyRefund(SQLModel, table=True):
    """Refund correlation record; refunds do not require a Checkout Session ID."""

    __tablename__ = "academy_refund"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_academy_refund_amount_positive"),
        UniqueConstraint("stripe_refund_id", name="uq_academy_refund_refund_id"),
        Index("ix_academy_refund_purchase", "purchase_id"),
        Index("ix_academy_refund_payment_intent", "payment_intent_id"),
        Index("ix_academy_refund_charge", "charge_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    stripe_refund_id: str = Field(sa_column=Column(String(255), nullable=False))
    purchase_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("academy_purchase.id", ondelete="SET NULL"), nullable=True),
    )
    payment_intent_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    charge_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    amount: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False))
    status: AcademyRefundStatus = Field(
        default=AcademyRefundStatus.PENDING,
        sa_column=Column(String(32), nullable=False, server_default="pending"),
    )
    retry_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    last_error: Optional[str] = Field(default=None, sa_column=Column(String(2000), nullable=True))
    error_retryable: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    next_retry_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    refunded_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
