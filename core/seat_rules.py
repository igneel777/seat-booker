from datetime import datetime

from models.api import SeatStatus
from models.db import ReservationStatus, SeatReservation


def seat_status(reservation: SeatReservation | None, now: datetime) -> SeatStatus:
    """No row or an expired hold -> AVAILABLE."""
    if reservation is None:
        return SeatStatus.AVAILABLE
    if reservation.status == ReservationStatus.BOOKED:
        return SeatStatus.BOOKED
    if reservation.hold_expires_at is not None and reservation.hold_expires_at > now:
        return SeatStatus.HELD
    return SeatStatus.AVAILABLE


def is_taken_for(reservation: SeatReservation, user_id: str, now: datetime) -> bool:
    """Taken for this user: BOOKED by anyone, or held unexpired by someone else."""
    status = seat_status(reservation, now)
    if status == SeatStatus.HELD:
        return reservation.held_by != user_id
    return status == SeatStatus.BOOKED
