import pytest
from sqlalchemy import CheckConstraint, Column, Integer, Table, UniqueConstraint, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from config.config import AcademyOfferConfig, get_learnhouse_config
from src.db.academy import (
    AcademyEnrollmentStatus,
    AcademyEventStatus,
    AcademyPaymentStatus,
    AcademyPurchase,
    AcademyRefund,
    AcademyRefundStatus,
    AcademyStripeEvent,
)


def test_academy_offer_defaults_disabled_and_card_only():
    offer = AcademyOfferConfig()
    assert offer.enabled is False
    assert offer.payment_method_types == ["card"]


def test_enabled_academy_offer_requires_deployment_values():
    with pytest.raises(ValueError, match="Enabled Academy offer is incomplete"):
        AcademyOfferConfig(enabled=True)

def test_enabled_academy_offer_hides_and_validates_credentials():
    secret_key = "sk_test_do_not_log"
    webhook_secret = "whsec_do_not_log"
    with pytest.raises(ValueError) as exc_info:
        AcademyOfferConfig(
            enabled=True,
            stripe_secret_key=secret_key,
            stripe_webhook_secret=webhook_secret,
            stripe_price_id="price_academy",
            org_id=1,
            course_id=2,
            amount=-1,
            currency="usd",
        )
    error = str(exc_info.value)
    assert secret_key not in error
    assert webhook_secret not in error

    with pytest.raises(ValueError, match="Enabled Academy offer is incomplete"):
        AcademyOfferConfig(
            enabled=True,
            stripe_secret_key=" ",
            stripe_webhook_secret="\t",
            stripe_price_id=" price_academy ",
            org_id=1,
            course_id=2,
            amount=4900,
            currency=" usd ",
        )


def test_loader_fails_closed_for_enabled_incomplete_offer(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("LEARNHOUSE_AUTH_JWT_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("LEARNHOUSE_ACADEMY_ENABLED", "true")
    for name in (
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_ID",
        "ORG_ID",
        "COURSE_ID",
        "AMOUNT",
        "CURRENCY",
    ):
        monkeypatch.delenv(f"LEARNHOUSE_ACADEMY_{name}", raising=False)
    with pytest.raises(ValueError, match="Enabled Academy offer is incomplete"):
        get_learnhouse_config()


def test_enabled_academy_offer_rejects_non_card_methods():
    with pytest.raises(ValueError, match="card payments only"):
        AcademyOfferConfig(
            enabled=True,
            stripe_secret_key="sk_test_academy",
            stripe_webhook_secret="whsec_academy",
            stripe_price_id="price_academy",
            org_id=1,
            course_id=2,
            amount=4900,
            currency="usd",
            payment_method_types=["card", "cashapp"],
        )


def test_academy_models_capture_processing_and_correlation_fields():
    purchase_columns = {column.name for column in inspect(AcademyPurchase).columns}
    assert {
        "purchase_uuid",
        "checkout_session_id",
        "learner_id",
        "course_id",
        "org_id",
        "price_id",
        "amount",
        "currency",
        "quantity",
        "payment_status",
        "enrollment_status",
        "last_error",
        "error_retryable",
        "next_retry_at",
    } <= purchase_columns

    event = AcademyStripeEvent(
        stripe_event_id="evt_123",
        event_type="refund.created",
        stripe_refund_id="re_123",
        payment_intent_id="pi_123",
        charge_id="ch_123",
        status=AcademyEventStatus.RECEIVED,
    )
    refund = AcademyRefund(
        stripe_refund_id="re_123",
        payment_intent_id="pi_123",
        charge_id="ch_123",
        amount=4900,
        currency="usd",
        status=AcademyRefundStatus.PENDING,
    )
    assert event.checkout_session_id is None
    assert refund.purchase_id is None
    assert AcademyPurchase(
        checkout_session_id="cs_123",
        learner_id=1,
        course_id=2,
        org_id=3,
        price_id="price_123",
        amount=4900,
        currency="usd",
        payment_status=AcademyPaymentStatus.PENDING,
        enrollment_status=AcademyEnrollmentStatus.PENDING,
    ).quantity == 1


def test_local_purchase_attempts_have_uuid_before_checkout_session():
    kwargs = dict(
        learner_id=1,
        course_id=2,
        org_id=3,
        price_id="price_123",
        amount=4900,
        currency="usd",
    )
    first = AcademyPurchase(**kwargs)
    second = AcademyPurchase(**kwargs)
    assert first.checkout_session_id is None
    assert second.checkout_session_id is None
    assert first.purchase_uuid != second.purchase_uuid


def test_non_null_checkout_session_id_is_unique():
    metadata = AcademyPurchase.metadata
    reference_tables = [
        Table(name, metadata, Column("id", Integer, primary_key=True))
        for name in ("user", "course", "organization")
        if name not in metadata.tables
    ]
    engine = create_engine("sqlite://")
    metadata.create_all(engine, tables=reference_tables + [AcademyPurchase.__table__])
    kwargs = dict(
        learner_id=1,
        course_id=2,
        org_id=3,
        price_id="price_123",
        amount=4900,
        currency="usd",
        checkout_session_id="cs_duplicate",
    )
    with Session(engine) as session:
        session.add_all([AcademyPurchase(**kwargs), AcademyPurchase(**kwargs)])
        with pytest.raises(IntegrityError):
            session.commit()


def test_database_uniqueness_is_scoped_to_external_identities():
    for model, constraint_name in (
        (AcademyPurchase, "uq_academy_purchase_purchase_uuid"),
        (AcademyPurchase, "uq_academy_purchase_checkout_session"),
        (AcademyStripeEvent, "uq_academy_stripe_event_event_id"),
        (AcademyRefund, "uq_academy_refund_refund_id"),
    ):
        names = {constraint.name for constraint in model.__table__.constraints}
        assert constraint_name in names

    expected_checks = {
        AcademyPurchase: {
            "ck_academy_purchase_amount_positive",
            "ck_academy_purchase_quantity_positive",
        },
        AcademyRefund: {"ck_academy_refund_amount_positive"},
    }
    for model, expected_names in expected_checks.items():
        names = {
            constraint.name
            for constraint in model.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }
        assert expected_names <= names

    # TrailRun is progress persistence, but its identity is
    # (trail_id, course_id, user_id), not a stable Academy enrollment key.
    # Trail itself has no unique (org_id, user_id), so the foundation does not
    # invent a learner/course uniqueness key.
    purchase_unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in AcademyPurchase.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("learner_id", "course_id", "org_id") not in purchase_unique_columns

    stored_names = set(AcademyPurchase.__table__.columns.keys())
    assert not any("card" in name or "cvc" in name or "credential" in name for name in stored_names)
