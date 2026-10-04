from uuid import UUID

from core.exceptions import ShowNotFoundError
from core.incoming_ports import UserPort
from core.outgoing_ports import DBPort
from models.api import ShowResponse


class UserFacade(UserPort):
    """UserPort implementation."""

    def __init__(self, db: DBPort) -> None:
        self._db = db

    async def get_show(self, show_id: UUID) -> ShowResponse:
        found = await self._db.get_show_with_seats(show_id)
        if found is None:
            raise ShowNotFoundError(show_id)
        show, seats = found
        return ShowResponse.from_models(show, seats)
