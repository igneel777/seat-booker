from abc import ABC, abstractmethod

from models.db import Seat, Show


class DBPort(ABC):
    """What core needs from storage. Each method is atomic on its own."""

    @abstractmethod
    async def create_show_with_seats(self, show: Show, seats: list[Seat]) -> None: ...
