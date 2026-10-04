from abc import ABC, abstractmethod
from enum import StrEnum
from uuid import UUID

from models.api import SeatStatus


class Operation(StrEnum):
    HOLD = "hold"
    RESERVE = "reserve"
    UNKNOWN = "unknown"  # raised below core, e.g. the integrity backstop


class DeclineReason(StrEnum):
    SEAT_TAKEN = "seat_taken"
    PER_USER_LIMIT = "per_user_limit"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    SEAT_NOT_FOUND = "seat_not_found"
    CONFLICT = "conflict"


class MetricsPort(ABC):
    """What core reports about outcomes. Counters are in-process and reset on
    restart; seat counts come from the DB at scrape time."""

    @abstractmethod
    def reservation_confirmed(self, seats: int) -> None:
        """A new booking committed. Call only after COMMIT."""

    @abstractmethod
    def reservation_declined(self, operation: Operation, reason: DeclineReason) -> None:
        """A hold/reserve request that created nothing."""

    @abstractmethod
    def booking_cancelled(self) -> None:
        """A booking actually cancelled. Call only after COMMIT."""

    @abstractmethod
    def set_seat_counts(self, counts: list[tuple[UUID, SeatStatus, int]]) -> None:
        """Replace the seats gauge with this snapshot."""

    @abstractmethod
    def render(self) -> tuple[bytes, str]:
        """Exposition body and its content type."""
