from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator

from models.db import Seat, Show

MAX_SEATS_PER_SHOW = 500

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def reject_duplicate_labels(seats: list[str]) -> list[str]:
    duplicates = sorted({s for s in seats if seats.count(s) > 1})
    if duplicates:
        raise ValueError(f"duplicate seat labels: {duplicates}")
    return seats


class SeatStatus(StrEnum):
    """Computed per read from seat_reservations; never stored."""

    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    BOOKED = "BOOKED"


class CreateShowRequest(BaseModel):
    name: NonEmptyStr
    seats: list[NonEmptyStr] = Field(min_length=1, max_length=MAX_SEATS_PER_SHOW)
    price_paise: int = Field(ge=0)

    @field_validator("seats")
    @classmethod
    def seats_unique(cls, seats: list[str]) -> list[str]:
        return reject_duplicate_labels(seats)


class SeatResponse(BaseModel):
    id: UUID
    label: str
    status: SeatStatus
    price_paise: int


class ShowResponse(BaseModel):
    id: UUID
    name: str
    seats: list[SeatResponse]

    @classmethod
    def from_models(
        cls, show: Show, seats: list[tuple[Seat, SeatStatus]]
    ) -> "ShowResponse":
        return cls(
            id=show.id,
            name=show.name,
            seats=[
                SeatResponse(
                    id=s.id, label=s.label, status=st, price_paise=s.price_paise
                )
                for s, st in seats
            ],
        )
