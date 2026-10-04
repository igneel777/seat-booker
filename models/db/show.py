from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlmodel import Field, SQLModel


class Show(SQLModel, table=True):
    __tablename__ = "shows"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(nullable=False)
    created_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
