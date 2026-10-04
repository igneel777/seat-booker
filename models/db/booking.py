from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class Booking(SQLModel, table=True):
    """One confirmed booking; its seats are the BOOKED seat_reservations rows."""

    __tablename__ = "bookings"
    __table_args__ = (
        # Keys are scoped per user; also the backstop for concurrent replays.
        UniqueConstraint(
            "booked_by", "idempotency_key", name="uq_bookings_user_idempotency_key"
        ),
        CheckConstraint("amount_paise >= 0", name="ck_bookings_amount_non_negative"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    show_id: UUID = Field(foreign_key="shows.id", nullable=False)
    idempotency_key: str = Field(nullable=False)
    booked_by: str = Field(nullable=False)
    booked_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    amount_paise: int = Field(nullable=False)
