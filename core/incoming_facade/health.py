from core.incoming_ports import HealthPort
from core.outgoing_ports import DBPort, MetricsPort
from utils.logging import get_logger

logger = get_logger("seat_booker.health")


class HealthFacade(HealthPort):
    """HealthPort implementation."""

    def __init__(self, db: DBPort, metrics: MetricsPort) -> None:
        self._db = db
        self._metrics = metrics

    async def is_db_alive(self) -> bool:
        try:
            await self._db.ping()
        except Exception:
            logger.error("db ping failed", exc_info=True)
            return False
        return True

    async def render_metrics(self) -> tuple[bytes, str]:
        # Seat counts are read now rather than tracked: holds expire by the
        # clock with no request, so only the DB knows the current number.
        self._metrics.set_seat_counts(await self._db.count_seats_by_status())
        return self._metrics.render()
