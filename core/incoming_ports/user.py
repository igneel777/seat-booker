from abc import ABC, abstractmethod
from uuid import UUID

from models.api import HoldResponse, ShowResponse


class UserPort(ABC):
    """Operations exposed to authenticated user routes."""

    @abstractmethod
    async def get_show(self, show_id: UUID) -> ShowResponse:
        """Raises HTTPException(404) if no show has this id."""

    @abstractmethod
    async def hold_seats(
        self, show_id: UUID, seat_labels: list[str], held_by: str
    ) -> HoldResponse:
        """All-or-nothing hold. Raises HTTPException 403 / 404 / 409."""
