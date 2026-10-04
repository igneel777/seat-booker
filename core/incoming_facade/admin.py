from core.incoming_ports import AdminPort
from core.outgoing_ports import DBPort
from models.api import SeatStatus, ShowResponse
from models.db import Seat, Show


class AdminFacade(AdminPort):
    """AdminPort implementation."""

    def __init__(self, db: DBPort) -> None:
        self._db = db

    async def create_show(
        self, show_name: str, seat_labels: list[str], price_paise: int
    ) -> ShowResponse:
        show = Show(name=show_name)
        seats = [
            Seat(show_id=show.id, label=label, price_paise=price_paise)
            for label in seat_labels
        ]
        await self._db.create_show_with_seats(show, seats)
        return ShowResponse.from_models(
            show, [(s, SeatStatus.AVAILABLE) for s in seats]
        )
