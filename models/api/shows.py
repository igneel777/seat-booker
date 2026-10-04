from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator

from models.db import SeatStatus

MAX_SEATS_PER_SHOW = 500

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CreateShowRequest(BaseModel):
    name: NonEmptyStr
    seats: list[NonEmptyStr] = Field(min_length=1, max_length=MAX_SEATS_PER_SHOW)
    price_paise: int = Field(ge=0)

    @field_validator("seats")
    @classmethod
    def seats_unique(cls, seats: list[str]) -> list[str]:
        duplicates = sorted({s for s in seats if seats.count(s) > 1})
        if duplicates:
            raise ValueError(f"duplicate seat labels: {duplicates}")
        return seats


class SeatResponse(BaseModel):
    id: UUID
    label: str
    status: SeatStatus
    price_paise: int


class ShowResponse(BaseModel):
    id: UUID
    name: str
    seats: list[SeatResponse]
