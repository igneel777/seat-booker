from abc import ABC, abstractmethod
from uuid import UUID

from models.api import BookingResponse, HoldResponse, ShowResponse


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

    @abstractmethod
    async def release_hold(self, hold_id: UUID, held_by: str) -> None:
        """Idempotent: a missing, expired or someone else's hold is a no-op."""

    @abstractmethod
    async def reserve_seats(
        self,
        show_id: UUID,
        seat_labels: list[str],
        idempotency_key: str,
        booked_by: str,
    ) -> BookingResponse:
        """All-or-nothing booking. Same key + same seats replays the original.

        Raises HTTPException: 404 unknown labels, 409 seats taken or key reused.
        """
