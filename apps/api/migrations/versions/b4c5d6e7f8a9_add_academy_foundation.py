"""Add Start Shape Ship Academy purchase, event inbox, and refunds.

Revision ID: b4c5d6e7f8a9
Revises: a2b3c4d5e6f7, r5s6t7u8v9w0
Create Date: 2026-07-24

The Academy card offer is intentionally separate from LearnHouse's existing
organization billing tables. Event rows contain identifiers and processing
metadata only; Stripe payloads and card data are not persisted.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = (
    "a2b3c4d5e6f7",
    "r5s6t7u8v9w0",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academy_purchase",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purchase_uuid", sa.String(length=36), nullable=False),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("price_id", sa.String(length=255), nullable=False),
        sa.Column("product_id", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payment_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("enrollment_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("charge_id", sa.String(length=255), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_academy_purchase_amount_positive"),
        sa.CheckConstraint("quantity > 0", name="ck_academy_purchase_quantity_positive"),
        sa.ForeignKeyConstraint(["learner_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_uuid", name="uq_academy_purchase_purchase_uuid"),
        sa.UniqueConstraint("checkout_session_id", name="uq_academy_purchase_checkout_session"),
        sa.UniqueConstraint("payment_intent_id", name="uq_academy_purchase_payment_intent"),
        sa.UniqueConstraint("charge_id", name="uq_academy_purchase_charge"),
    )
    op.create_index("ix_academy_purchase_learner", "academy_purchase", ["learner_id"])
    op.create_index("ix_academy_purchase_course_org", "academy_purchase", ["course_id", "org_id"])
    op.create_index("ix_academy_purchase_payment_status", "academy_purchase", ["payment_status"])

    op.create_table(
        "academy_stripe_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("purchase_id", sa.Integer(), nullable=True),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("charge_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_refund_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="received", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["purchase_id"], ["academy_purchase.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id", name="uq_academy_stripe_event_event_id"),
    )
    op.create_index("ix_academy_stripe_event_purchase", "academy_stripe_event", ["purchase_id"])
    op.create_index("ix_academy_stripe_event_status", "academy_stripe_event", ["status"])
    op.create_index("ix_academy_stripe_event_refund", "academy_stripe_event", ["stripe_refund_id"])

    op.create_table(
        "academy_refund",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stripe_refund_id", sa.String(length=255), nullable=False),
        sa.Column("purchase_id", sa.Integer(), nullable=True),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("charge_id", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_academy_refund_amount_positive"),
        sa.ForeignKeyConstraint(["purchase_id"], ["academy_purchase.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_refund_id", name="uq_academy_refund_refund_id"),
    )
    op.create_index("ix_academy_refund_purchase", "academy_refund", ["purchase_id"])
    op.create_index("ix_academy_refund_payment_intent", "academy_refund", ["payment_intent_id"])
    op.create_index("ix_academy_refund_charge", "academy_refund", ["charge_id"])


def downgrade() -> None:
    op.drop_index("ix_academy_refund_charge", table_name="academy_refund")
    op.drop_index("ix_academy_refund_payment_intent", table_name="academy_refund")
    op.drop_index("ix_academy_refund_purchase", table_name="academy_refund")
    op.drop_table("academy_refund")
    op.drop_index("ix_academy_stripe_event_refund", table_name="academy_stripe_event")
    op.drop_index("ix_academy_stripe_event_status", table_name="academy_stripe_event")
    op.drop_index("ix_academy_stripe_event_purchase", table_name="academy_stripe_event")
    op.drop_table("academy_stripe_event")
    op.drop_index("ix_academy_purchase_payment_status", table_name="academy_purchase")
    op.drop_index("ix_academy_purchase_course_org", table_name="academy_purchase")
    op.drop_index("ix_academy_purchase_learner", table_name="academy_purchase")
    op.drop_table("academy_purchase")
