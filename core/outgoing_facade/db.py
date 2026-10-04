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
