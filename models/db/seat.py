from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class SeatStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    BOOKED = "BOOKED"


class Seat(SQLModel, table=True):
    """One row per seat per show; the row is the lock target for hold/book."""

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("show_id", "label", name="uq_seats_show_label"),
        CheckConstraint(
            "status = 'AVAILABLE' OR "
            "(hold_id IS NOT NULL AND held_by IS NOT NULL AND held_at IS NOT NULL)",
            name="ck_seats_hold_fields",
        ),
        CheckConstraint(
            "status <> 'BOOKED' OR booked_at IS NOT NULL",
            name="ck_seats_booked_at",
        ),
        CheckConstraint("price_paise >= 0", name="ck_seats_price_non_negative"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    show_id: UUID = Field(foreign_key="shows.id", index=True, nullable=False)
    label: str = Field(nullable=False)
    price_paise: int = Field(nullable=False)
    status: SeatStatus = Field(
        default=SeatStatus.AVAILABLE,
        sa_type=SAEnum(SeatStatus, name="seat_status"),
        sa_column_kwargs={"server_default": SeatStatus.AVAILABLE.value},
        nullable=False,
    )
    hold_id: UUID | None = Field(default=None, index=True)
    held_by: str | None = None
    held_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    booked_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        nullable=False,
    )
