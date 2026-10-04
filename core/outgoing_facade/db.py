from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.outgoing_ports import DBPort
from infra.db_client import DBClient
from models.api import SeatStatus
from models.db import ReservationStatus, Seat, SeatReservation, Show


def _seat_status(reservation: SeatReservation | None, now: datetime) -> SeatStatus:
    """No row or an expired hold -> AVAILABLE."""
    if reservation is None:
        return SeatStatus.AVAILABLE
    if reservation.status == ReservationStatus.BOOKED:
        return SeatStatus.BOOKED
    if reservation.hold_expires_at is not None and reservation.hold_expires_at > now:
        return SeatStatus.HELD
    return SeatStatus.AVAILABLE


async def _db_now(session: AsyncSession) -> datetime:
    # Postgres now() is fixed for the whole transaction: one clock for all checks.
    return (await session.exec(select(func.now()))).one()


class DBFacade(DBPort):
    """Postgres implementation of DBPort. Owns the transaction boundary."""

    def __init__(self, client: DBClient) -> None:
        self._client = client

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
            now = await _db_now(session)
        return show, [(seat, _seat_status(res, now)) for seat, res in rows]

    async def hold_seats(
        self,
        show_id: UUID,
        seat_labels: list[str],
        held_by: str,
        hold_id: UUID,
        hold_ttl: timedelta,
        per_hold_limit: int,
    ) -> datetime:
        try:
            # Any exception raised inside rolls the whole transaction back.
            async with self._client.transaction() as session:
                return await self._hold_in_txn(
                    session,
                    show_id,
                    seat_labels,
                    held_by,
                    hold_id,
                    hold_ttl,
                    per_hold_limit,
                )
        except IntegrityError as e:
            # Unique index backstop fired: someone else holds one of the seats.
            raise HTTPException(status.HTTP_409_CONFLICT, "seats not available") from e

    async def _hold_in_txn(
        self,
        session: AsyncSession,
        show_id: UUID,
        seat_labels: list[str],
        held_by: str,
        hold_id: UUID,
        hold_ttl: timedelta,
        per_hold_limit: int,
    ) -> datetime:
        # Serialise this user's holds on this show, so parallel requests for
        # different seats can't each pass the limit check. Released on
        # COMMIT/ROLLBACK.
        lock_key = func.hashtextextended(f"{show_id}:{held_by}", 0)
        await session.exec(select(func.pg_advisory_xact_lock(lock_key)))

        already_held = (
            await session.exec(
                select(func.count())
                .select_from(SeatReservation)
                .join(Seat, col(Seat.id) == SeatReservation.seat_id)
                .where(
                    Seat.show_id == show_id,
                    SeatReservation.held_by == held_by,
                    SeatReservation.status == ReservationStatus.HELD,
                    col(SeatReservation.hold_expires_at) > func.now(),
                )
            )
        ).one()
        if already_held + len(seat_labels) > per_hold_limit:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Cannot hold more than {per_hold_limit} seats at a time",
            )

        # Lock the static seat rows (they always exist) in label order so
        # overlapping holds can't deadlock.
        seats = (
            await session.exec(
                select(Seat)
                .where(Seat.show_id == show_id, col(Seat.label).in_(seat_labels))
                .order_by(col(Seat.label))
                .with_for_update()
            )
        ).all()
        missing = sorted(set(seat_labels) - {s.label for s in seats})
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"seats not found: {missing}"
            )

        seat_ids = [s.id for s in seats]
        label_by_id = {s.id: s.label for s in seats}
        now = await _db_now(session)
        reservations = (
            await session.exec(
                select(SeatReservation).where(
                    col(SeatReservation.seat_id).in_(seat_ids)
                )
            )
        ).all()
        taken = sorted(
            label_by_id[r.seat_id]
            for r in reservations
            if _seat_status(r, now) != SeatStatus.AVAILABLE
        )
        if taken:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"seats not available: {taken}"
            )

        # Expired holds still occupy the unique index slot; clear them first.
        await session.exec(
            delete(SeatReservation).where(
                col(SeatReservation.seat_id).in_(seat_ids),
                SeatReservation.status == ReservationStatus.HELD,
                col(SeatReservation.hold_expires_at) <= now,
            )
        )
        expires_at = now + hold_ttl
        session.add_all(
            SeatReservation(
                seat_id=seat_id,
                status=ReservationStatus.HELD,
                hold_id=hold_id,
                held_by=held_by,
                hold_expires_at=expires_at,
            )
            for seat_id in seat_ids
        )
        return expires_at

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
