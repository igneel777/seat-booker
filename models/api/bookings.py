from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator

from models.api.shows import NonEmptyStr, reject_duplicate_labels
from settings import get_booking_settings

IdempotencyKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class ReserveSeatsRequest(BaseModel):
    seats: list[NonEmptyStr] = Field(
        min_length=1, max_length=get_booking_settings().per_hold_limit
    )
    idempotency_key: IdempotencyKey

    @field_validator("seats")
    @classmethod
    def seats_unique(cls, seats: list[str]) -> list[str]:
        return reject_duplicate_labels(seats)


class BookingResponse(BaseModel):
    booking_id: UUID
    show_id: UUID
    seats: list[str]
    amount_paise: int
    idempotency_key: str
