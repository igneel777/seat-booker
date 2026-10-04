from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel


class Seat(SQLModel, table=True):
    """Static seat per show. Still the lock target for holds: it always exists,
    whereas a free seat has no reservation row to lock."""

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("show_id", "label", name="uq_seats_show_label"),
        CheckConstraint("price_paise >= 0", name="ck_seats_price_non_negative"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    show_id: UUID = Field(foreign_key="shows.id", index=True, nullable=False)
    label: str = Field(nullable=False)
    price_paise: int = Field(nullable=False)
