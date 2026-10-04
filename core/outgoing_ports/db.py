from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from uuid import UUID

from models.api import SeatStatus
from models.db import Booking, Seat, SeatReservation, Show


class Transaction(ABC):  # noqa: B024  marker type, intentionally empty
    """Opaque handle to an open DB transaction. Core passes it, never looks inside."""


class DBPort(ABC):
    """What core needs from storage.

    Methods without a `txn` are atomic on their own. Methods taking a `txn`
    run one statement inside a transaction opened by `transaction()`.
    """

    # --- standalone, each atomic -------------------------------------------

    @abstractmethod
    async def create_show_with_seats(self, show: Show, seats: list[Seat]) -> None: ...

    @abstractmethod
    async def get_show_with_seats(
        self, show_id: UUID
    ) -> tuple[Show, list[tuple[Seat, SeatStatus]]] | None:
        """Show plus its seats (ordered by label) with their computed status.

        None if the show doesn't exist.
        """

    @abstractmethod
    async def release_hold(self, hold_id: UUID, held_by: str) -> int:
        """Delete this user's HELD rows for the hold; returns rows deleted."""

    @abstractmethod
    async def release_expired_holds(self) -> int:
        """Delete expired HELD reservations; returns rows released."""

    # --- transaction + primitives ------------------------------------------

    @abstractmethod
    def transaction(self) -> AbstractAsyncContextManager[Transaction]:
        """BEGIN on enter; COMMIT on clean exit; ROLLBACK if anything raises.

        A unique-constraint violation surfaces as HTTPException(409).
        """

    @abstractmethod
    async def advisory_lock(self, txn: Transaction, key: str) -> None:
        """Lock `key` until the transaction ends; same key waits, others don't."""

    @abstractmethod
    async def now(self, txn: Transaction) -> datetime:
        """DB clock; fixed for the whole transaction."""

    @abstractmethod
    async def count_active_holds(
        self, txn: Transaction, show_id: UUID, user_id: str
    ) -> int:
        """Unexpired HELD seats this user has on this show."""

    @abstractmethod
    async def lock_seats(
        self, txn: Transaction, show_id: UUID, labels: list[str]
    ) -> list[Seat]:
        """Existing seats among `labels`, locked FOR UPDATE in label order."""

    @abstractmethod
    async def get_reservations(
        self, txn: Transaction, seat_ids: list[UUID]
    ) -> list[SeatReservation]: ...

    @abstractmethod
    async def replace_reservations(
        self, txn: Transaction, seat_ids: list[UUID], rows: list[SeatReservation]
    ) -> None:
        """Delete every reservation on `seat_ids`, then insert `rows`."""

    @abstractmethod
    async def find_booking(
        self, txn: Transaction, user_id: str, idempotency_key: str
    ) -> Booking | None: ...

    @abstractmethod
    async def get_booking_labels(self, txn: Transaction, booking_id: UUID) -> list[str]:
        """Seat labels of the booking, sorted."""

    @abstractmethod
    async def insert_booking(self, txn: Transaction, booking: Booking) -> None: ...
