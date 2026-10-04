from abc import ABC, abstractmethod
from uuid import UUID

from models.db import Seat, Show


class DBPort(ABC):
    """What core needs from storage. Each method is atomic on its own."""

    @abstractmethod
    async def create_show_with_seats(self, show: Show, seats: list[Seat]) -> None: ...

    @abstractmethod
    async def get_show_with_seats(
        self, show_id: UUID
    ) -> tuple[Show, list[Seat]] | None:
        """Show plus its seats ordered by label; None if the show doesn't exist."""
