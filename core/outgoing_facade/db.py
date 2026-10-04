from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.outgoing_ports import DBPort, Transaction
from core.seat_rules import seat_status
from infra.db_client import DBClient
from models.api import SeatStatus
from models.db import Booking, ReservationStatus, Seat, SeatReservation, Show


class _PgTransaction(Transaction):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session


def _session(txn: Transaction) -> AsyncSession:
    assert isinstance(txn, _PgTransaction), "txn must come from DBFacade.transaction()"
    return txn.session


class DBFacade(DBPort):
    """Postgres implementation of DBPort. Executes statements; no business rules."""

    def __init__(self, client: DBClient) -> None:
        self._client = client

    # --- standalone, each atomic -------------------------------------------

    async def create_show_with_seats(self, show: Show, seats: list[Seat]) -> None:
        # Show and seats commit together, or not at all.
        async with self._client.transaction() as session:
            session.add(show)
            await session.flush()  # show row must exist before seats reference it
            session.add_all(seats)

    async def get_show_with_seats(
        self, show_id: UUID
    ) -> tuple[Show, list[tuple[Seat, SeatStatus]]] | None:
        # One statement for all seat states, so no transaction needed. The
        # partial unique index guarantees at most one reservation row per seat.
        async with self._client.connection() as session:
            show = await session.get(Show, show_id)
            if show is None:
                return None
            rows = (
                await session.exec(
                    select(Seat, SeatReservation)
                    .outerjoin(SeatReservation, col(SeatReservation.seat_id) == Seat.id)
                    .where(Seat.show_id == show_id)
                    .order_by(col(Seat.label))
                )
            ).all()
            now = (await session.exec(select(func.now()))).one()
        return show, [(seat, seat_status(res, now)) for seat, res in rows]

    async def release_hold(self, hold_id: UUID, held_by: str) -> int:
        # Single statement, so atomic. held_by: only the holder can release.
        # status = HELD: a booked seat is never released; if a booking holds the
        # rows, this waits, re-checks the WHERE and deletes nothing.
        async with self._client.connection() as session:
            result = await session.exec(
                delete(SeatReservation).where(
                    SeatReservation.hold_id == hold_id,
                    SeatReservation.held_by == held_by,
                    SeatReservation.status == ReservationStatus.HELD,
                )
            )
            return result.rowcount

    async def release_expired_holds(self) -> int:
        # Single statement, so atomic on its own.
        async with self._client.connection() as session:
            result = await session.exec(
                delete(SeatReservation).where(
                    SeatReservation.status == ReservationStatus.HELD,
                    col(SeatReservation.hold_expires_at) < func.now(),
                )
            )
            return result.rowcount

    # --- transaction + primitives ------------------------------------------

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Transaction]:
        try:
            async with self._client.transaction() as session:
                yield _PgTransaction(session)
        except IntegrityError as e:
            # A unique backstop fired under a race (seat index / user+key).
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Error processing request"
            ) from e

    async def advisory_lock(self, txn: Transaction, key: str) -> None:
        # Released automatically on COMMIT/ROLLBACK. Hash collisions only
        # serialise unrelated keys; never incorrect.
        await _session(txn).exec(
            select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0)))
        )

    async def now(self, txn: Transaction) -> datetime:
        return (await _session(txn).exec(select(func.now()))).one()

    async def count_active_holds(
        self, txn: Transaction, show_id: UUID, user_id: str
    ) -> int:
        return (
            await _session(txn).exec(
                select(func.count())
                .select_from(SeatReservation)
                .join(Seat, col(Seat.id) == SeatReservation.seat_id)
                .where(
                    Seat.show_id == show_id,
                    SeatReservation.held_by == user_id,
                    SeatReservation.status == ReservationStatus.HELD,
                    col(SeatReservation.hold_expires_at) > func.now(),
                )
            )
        ).one()

    async def lock_seats(
        self, txn: Transaction, show_id: UUID, labels: list[str]
    ) -> list[Seat]:
        # Label order: every transaction locks in the same order, so no deadlocks.
        return list(
            (
                await _session(txn).exec(
                    select(Seat)
                    .where(Seat.show_id == show_id, col(Seat.label).in_(labels))
                    .order_by(col(Seat.label))
                    .with_for_update()
                )
            ).all()
        )

    async def get_reservations(
        self, txn: Transaction, seat_ids: list[UUID]
    ) -> list[SeatReservation]:
        return list(
            (
                await _session(txn).exec(
                    select(SeatReservation).where(
                        col(SeatReservation.seat_id).in_(seat_ids)
                    )
                )
            ).all()
        )

    async def replace_reservations(
        self, txn: Transaction, seat_ids: list[UUID], rows: list[SeatReservation]
    ) -> None:
        session = _session(txn)
        await session.exec(
            delete(SeatReservation).where(col(SeatReservation.seat_id).in_(seat_ids))
        )
        session.add_all(rows)
        await session.flush()

    async def find_booking(
        self, txn: Transaction, user_id: str, idempotency_key: str
    ) -> Booking | None:
        return (
            await _session(txn).exec(
                select(Booking).where(
                    Booking.booked_by == user_id,
                    Booking.idempotency_key == idempotency_key,
                )
            )
        ).first()

    async def get_booking_labels(self, txn: Transaction, booking_id: UUID) -> list[str]:
        return list(
            (
                await _session(txn).exec(
                    select(Seat.label)
                    .join(SeatReservation, col(SeatReservation.seat_id) == Seat.id)
                    .where(SeatReservation.booking_id == booking_id)
                    .order_by(col(Seat.label))
                )
            ).all()
        )

    async def insert_booking(self, txn: Transaction, booking: Booking) -> None:
        session = _session(txn)
        session.add(booking)
        await session.flush()  # booking row must exist before reservations FK it
