from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class ReservationStatus(StrEnum):
    HELD = "HELD"
    BOOKED = "BOOKED"


class SeatReservation(SQLModel, table=True):
    """Hold/booking state for a seat. No row means the seat is AVAILABLE."""

    __tablename__ = "seat_reservations"
    __table_args__ = (
        CheckConstraint(
            "status <> 'HELD' OR (hold_id IS NOT NULL AND held_by IS NOT NULL "
            "AND hold_expires_at IS NOT NULL)",
            name="ck_seat_reservations_held_fields",
        ),
        CheckConstraint(
            "status <> 'BOOKED' OR booking_id IS NOT NULL",
            name="ck_seat_reservations_booked_fields",
        ),
        # Backstop against double holds: at most one reservation row per seat.
        # Can't include now() (index predicates must be immutable), so expired
        # holds must be deleted before a new hold is inserted.
        Index(
            "uq_seat_reservations_active_seat",
            "seat_id",
            unique=True,
            postgresql_where=text("status IN ('HELD', 'BOOKED')"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    seat_id: UUID = Field(foreign_key="seats.id", nullable=False)
    status: ReservationStatus = Field(
        sa_type=SAEnum(ReservationStatus, name="reservation_status"), nullable=False
    )
    hold_id: UUID | None = Field(default=None, index=True)
    held_by: str | None = None
    hold_expires_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    booking_id: UUID | None = Field(default=None, foreign_key="bookings.id")
