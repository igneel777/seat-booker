from uuid import UUID

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    disable_created_metrics,
    generate_latest,
)

from core.outgoing_ports import DeclineReason, MetricsPort, Operation
from models.api import SeatStatus

# Drop the per-series *_created timestamps; nothing here reads them.
disable_created_metrics()

# Module level: prometheus_client's default registry rejects duplicate names.
_CONFIRMED = Counter(
    "seatbooker_reservations_confirmed",
    "New bookings committed by POST /reserve (replays excluded).",
)
_SEATS_CONFIRMED = Counter(
    "seatbooker_reservation_seats_confirmed",
    "Seats in committed bookings.",
)
_DECLINED = Counter(
    "seatbooker_reservations_declined",
    "Hold/reserve requests that created nothing, by reason.",
    ["operation", "reason"],
)
_CANCELLED = Counter(
    "seatbooker_bookings_cancelled",
    "Bookings actually cancelled.",
)
_SEATS = Gauge(
    "seatbooker_seats",
    "Seats per show by computed status, read from the DB at scrape time.",
    ["show_id", "status"],
)


class PrometheusMetrics(MetricsPort):
    """MetricsPort backed by prometheus_client's default registry."""

    def reservation_confirmed(self, seats: int) -> None:
        _CONFIRMED.inc()
        _SEATS_CONFIRMED.inc(seats)

    def reservation_declined(self, operation: Operation, reason: DeclineReason) -> None:
        _DECLINED.labels(operation=operation, reason=reason).inc()

    def booking_cancelled(self) -> None:
        _CANCELLED.inc()

    def set_seat_counts(self, counts: list[tuple[UUID, SeatStatus, int]]) -> None:
        # Sync, so no other coroutine can render between clear() and the sets.
        # Every status gets a value: a sold-out show reports AVAILABLE 0, not nothing.
        _SEATS.clear()
        for show_id in {show_id for show_id, _, _ in counts}:
            for seat_status in SeatStatus:
                _SEATS.labels(show_id=str(show_id), status=seat_status).set(0)
        for show_id, seat_status, n in counts:
            _SEATS.labels(show_id=str(show_id), status=seat_status).set(n)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(), CONTENT_TYPE_LATEST
