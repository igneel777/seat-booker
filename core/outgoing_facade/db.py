from uuid import UUID

from sqlmodel import col, select

from core.outgoing_ports import DBPort
from infra.db_client import DBClient
from models.db import Seat, Show


class DBFacade(DBPort):
    """Postgres implementation of DBPort. Owns the transaction boundary."""

    def __init__(self, client: DBClient) -> None:
        self._client = client

    async def create_show_with_seats(self, show: Show, seats: list[Seat]) -> None:
        # Show and seats commit together, or not at all.
        async with self._client.transaction() as session:
            session.add(show)
            await session.flush()  # show row must exist before seats reference it
            session.add_all(seats)

    async def get_show_with_seats(
        self, show_id: UUID
    ) -> tuple[Show, list[Seat]] | None:
        # No transaction needed: show + seats are inserted atomically, and all
        # seat statuses come from a single statement.
        async with self._client.connection() as session:
            show = await session.get(Show, show_id)
            if show is None:
                return None
            result = await session.exec(
                select(Seat).where(Seat.show_id == show_id).order_by(col(Seat.label))
            )
            return show, list(result.all())
