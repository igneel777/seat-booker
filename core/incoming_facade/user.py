from uuid import UUID, uuid4

from fastapi import HTTPException, status

from core.incoming_ports import UserPort
from core.outgoing_ports import DBPort
from models.api import HoldResponse, ShowResponse
from settings import get_booking_settings


class UserFacade(UserPort):
    """UserPort implementation."""

    def __init__(self, db: DBPort) -> None:
        self._db = db

    async def get_show(self, show_id: UUID) -> ShowResponse:
        found = await self._db.get_show_with_seats(show_id)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"show {show_id} not found")
        show, seats = found
        return ShowResponse.from_models(show, seats)

    async def hold_seats(
        self, show_id: UUID, seat_labels: list[str], held_by: str
    ) -> HoldResponse:
        settings = get_booking_settings()
        hold_id = uuid4()
        # Cleanup only: hold_seats still treats expired holds as available itself.
        await self._db.release_expired_holds()
        expires_at = await self._db.hold_seats(
            show_id,
            seat_labels,
            held_by,
            hold_id,
            settings.hold_ttl,
            settings.per_hold_limit,
        )
        return HoldResponse(
            hold_id=hold_id, hold_expires_at=expires_at, seats=sorted(seat_labels)
        )
