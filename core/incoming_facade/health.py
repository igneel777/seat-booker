from core.incoming_ports import HealthPort
from core.outgoing_ports import DBPort
from utils.logging import get_logger

logger = get_logger("seat_booker.health")


class HealthFacade(HealthPort):
    """HealthPort implementation."""

    def __init__(self, db: DBPort) -> None:
        self._db = db

    async def is_db_alive(self) -> bool:
        try:
            await self._db.ping()
        except Exception:
            logger.error("db ping failed", exc_info=True)
            return False
        return True
