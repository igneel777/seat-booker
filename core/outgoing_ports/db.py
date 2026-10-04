from abc import ABC, abstractmethod
from datetime import datetime, timedelta
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

    @abstractmethod
    async def hold_seats(
        self,
        show_id: UUID,
        seat_labels: list[str],
        held_by: str,
        hold_id: UUID,
        hold_ttl: timedelta,
        per_hold_limit: int,
    ) -> datetime:
        """Hold all seats in one transaction; returns hold_expires_at.

        Raises HTTPException: 403 over the limit, 404 unknown labels,
        409 seats booked or held by someone else.
        """

    @abstractmethod
    async def release_expired_holds(self) -> int:
        """Set expired HELD seats back to AVAILABLE; returns rows released."""
