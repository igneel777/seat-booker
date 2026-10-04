from uuid import UUID, uuid4

from fastapi import HTTPException, status

from core.incoming_ports import UserPort
from core.outgoing_ports import DBPort, Transaction
from core.seat_rules import is_taken_for, seat_status
from models.api import BookingResponse, HoldResponse, SeatStatus, ShowResponse
from models.db import Booking, ReservationStatus, Seat, SeatReservation
from settings import get_booking_settings


class UserFacade(UserPort):
    """UserPort implementation. Owns the hold / reserve flows; any raise inside
    a transaction rolls it back."""

    def __init__(self, db: DBPort) -> None:
        self._db = db

    async def get_show(self, show_id: UUID) -> ShowResponse:
        found = await self._db.get_show_with_seats(show_id)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"show {show_id} not found")
        show, seats = found
        return ShowResponse.from_models(show, seats)

    async def hold_seats(
        self, show_id: UUID, seat_labels: list[str], held_by: str
    ) -> HoldResponse:
        settings = get_booking_settings()
        hold_id = uuid4()
        # Cleanup only: the checks below treat expired holds as available anyway.
        await self._db.release_expired_holds()

        async with self._db.transaction() as txn:
            # Serialise this user's holds on this show, so parallel requests for
            # different seats can't each pass the limit check.
            await self._db.advisory_lock(txn, f"hold:{show_id}:{held_by}")

            already_held = await self._db.count_active_holds(txn, show_id, held_by)
            if already_held + len(seat_labels) > settings.per_hold_limit:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    f"Cannot hold more than {settings.per_hold_limit} seats at a time",
                )

            seats = await self._db.lock_seats(txn, show_id, seat_labels)
            self._ensure_all_found(seat_labels, seats)

            now = await self._db.now(txn)
            seat_ids = [s.id for s in seats]
            label_by_id = {s.id: s.label for s in seats}
            reservations = await self._db.get_reservations(txn, seat_ids)
            self._raise_if_taken(
                sorted(
                    label_by_id[r.seat_id]
                    for r in reservations
                    if seat_status(r, now) != SeatStatus.AVAILABLE
                )
            )

            # Only expired holds remain on these seats; replace them.
            expires_at = now + settings.hold_ttl
            await self._db.replace_reservations(
                txn,
                seat_ids,
                [
                    SeatReservation(
                        seat_id=seat_id,
                        status=ReservationStatus.HELD,
                        hold_id=hold_id,
                        held_by=held_by,
                        hold_expires_at=expires_at,
                    )
                    for seat_id in seat_ids
                ],
            )
        return HoldResponse(
            hold_id=hold_id, hold_expires_at=expires_at, seats=sorted(seat_labels)
        )

    async def release_hold(self, hold_id: UUID, held_by: str) -> None:
        await self._db.release_expired_holds()
        await self._db.release_hold(hold_id, held_by)

    async def reserve_seats(
        self,
        show_id: UUID,
        seat_labels: list[str],
        idempotency_key: str,
        booked_by: str,
    ) -> BookingResponse:
        async with self._db.transaction() as txn:
            # Serialise requests with the same (user, key), so a parallel retry
            # waits and then replays instead of failing on the now-booked seats.
            await self._db.advisory_lock(txn, f"reserve:{booked_by}:{idempotency_key}")

            existing = await self._db.find_booking(txn, booked_by, idempotency_key)
            if existing is not None:
                return await self._replay(txn, existing, show_id, seat_labels)

            seats = await self._db.lock_seats(txn, show_id, seat_labels)
            self._ensure_all_found(seat_labels, seats)

            now = await self._db.now(txn)
            seat_ids = [s.id for s in seats]
            label_by_id = {s.id: s.label for s in seats}
            reservations = await self._db.get_reservations(txn, seat_ids)
            self._raise_if_taken(
                sorted(
                    label_by_id[r.seat_id]
                    for r in reservations
                    if is_taken_for(r, booked_by, now)
                )
            )

            booking = Booking(
                show_id=show_id,
                idempotency_key=idempotency_key,
                booked_by=booked_by,
                booked_at=now,
                amount_paise=sum(s.price_paise for s in seats),
            )
            await self._db.insert_booking(txn, booking)
            # Only this user's holds or expired holds remain; replace with BOOKED.
            await self._db.replace_reservations(
                txn,
                seat_ids,
                [
                    SeatReservation(
                        seat_id=seat_id,
                        status=ReservationStatus.BOOKED,
                        booking_id=booking.id,
                    )
                    for seat_id in seat_ids
                ],
            )
        return self._to_booking_response(booking, [s.label for s in seats])

    async def _replay(
        self,
        txn: Transaction,
        existing: Booking,
        show_id: UUID,
        seat_labels: list[str],
    ) -> BookingResponse:
        """Same key: identical request replays the original, anything else is 409."""
        booked_labels = await self._db.get_booking_labels(txn, existing.id)
        if existing.show_id != show_id or set(booked_labels) != set(seat_labels):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "idempotency key already used with a different request",
            )
        return self._to_booking_response(existing, booked_labels)

    @staticmethod
    def _ensure_all_found(labels: list[str], seats: list[Seat]) -> None:
        missing = sorted(set(labels) - {s.label for s in seats})
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"seats not found: {missing}"
            )

    @staticmethod
    def _raise_if_taken(taken: list[str]) -> None:
        if taken:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"seats not available: {taken}"
            )

    @staticmethod
    def _to_booking_response(booking: Booking, labels: list[str]) -> BookingResponse:
        return BookingResponse(
            booking_id=booking.id,
            show_id=booking.show_id,
            seats=labels,
            amount_paise=booking.amount_paise,
            idempotency_key=booking.idempotency_key,
        )
