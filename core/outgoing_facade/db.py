from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.outgoing_ports import DBPort
from infra.db_client import DBClient
from models.db import Seat, SeatStatus, Show


def _is_taken(seat: Seat, now: datetime) -> bool:
    """BOOKED, or HELD with an unexpired hold. Expired holds count as AVAILABLE."""
    if seat.status == SeatStatus.BOOKED:
        return True
    return (
        seat.status == SeatStatus.HELD
        and seat.hold_expires_at is not None
        and seat.hold_expires_at > now
    )


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
    ) -> tuple[Show, list[Seat]] | None:
        # No transaction needed: show + seats are inserted atomically, and all
        # seat statuses come from a single statement.
        async with self._client.connection() as session:
            show = await session.get(Show, show_id)
            if show is None:
                return None
            result = await session.exec(
                select(Seat).where(Seat.show_id == show_id).order_by(col(Seat.label))
            )
            seats = list(result.all())
            now = await _db_now(session)
            # Detach so the status rewrite below can never be flushed back.
            session.expunge_all()
        for seat in seats:
            if seat.status == SeatStatus.HELD and not _is_taken(seat, now):
                seat.status = SeatStatus.AVAILABLE
        return show, seats

    async def hold_seats(
        self,
        show_id: UUID,
        seat_labels: list[str],
        held_by: str,
        hold_id: UUID,
        hold_ttl: timedelta,
        per_hold_limit: int,
    ) -> datetime:
        # Any HTTPException raised inside rolls the whole transaction back.
        async with self._client.transaction() as session:
            # Serialise this user's holds on this show, so parallel requests for
            # different seats can't each pass the limit check. Released on
            # COMMIT/ROLLBACK.
            lock_key = func.hashtextextended(f"{show_id}:{held_by}", 0)
            await session.exec(select(func.pg_advisory_xact_lock(lock_key)))

            already_held = (
                await session.exec(
                    select(func.count())
                    .select_from(Seat)
                    .where(
                        Seat.show_id == show_id,
                        Seat.held_by == held_by,
                        Seat.status == SeatStatus.HELD,
                        col(Seat.hold_expires_at) > func.now(),
                    )
                )
            ).one()
            if already_held + len(seat_labels) > per_hold_limit:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    f"Cannot hold more than {per_hold_limit} seats at a time",
                )

            # Lock rows in label order so overlapping holds can't deadlock.
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
            now = await _db_now(session)
            taken = [s.label for s in seats if _is_taken(s, now)]
            if taken:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, f"seats not available: {taken}"
                )

            expires_at = now + hold_ttl
            await session.exec(
                update(Seat)
                .where(col(Seat.id).in_([s.id for s in seats]))
                .values(
                    status=SeatStatus.HELD,
                    hold_id=hold_id,
                    held_by=held_by,
                    hold_expires_at=expires_at,
                )
            )
            return expires_at

    async def release_expired_holds(self) -> int:
        # Single statement, so atomic on its own. Rows locked by an in-flight
        # hold are waited on, then re-checked against the new expiry.
        async with self._client.connection() as session:
            result = await session.exec(
                update(Seat)
                .where(
                    Seat.status == SeatStatus.HELD,
                    col(Seat.hold_expires_at) < func.now(),
                )
                .values(
                    status=SeatStatus.AVAILABLE,
                    hold_id=None,
                    held_by=None,
                    hold_expires_at=None,
                )
            )
            return result.rowcount
