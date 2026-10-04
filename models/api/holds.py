from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from models.api.shows import NonEmptyStr
from settings import get_booking_settings


class HoldSeatsRequest(BaseModel):
    # Cap is read from config at import time; changing it needs a restart.
    seats: list[NonEmptyStr] = Field(
        min_length=1, max_length=get_booking_settings().per_hold_limit
    )

    @field_validator("seats")
    @classmethod
    def seats_unique(cls, seats: list[str]) -> list[str]:
        duplicates = sorted({s for s in seats if seats.count(s) > 1})
        if duplicates:
            raise ValueError(f"duplicate seat labels: {duplicates}")
        return seats


class HoldResponse(BaseModel):
    hold_id: UUID
    hold_expires_at: datetime
    seats: list[str]
