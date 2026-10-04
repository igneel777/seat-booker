from abc import ABC, abstractmethod


class HealthPort(ABC):
    """Operations exposed to probe routes."""

    @abstractmethod
    async def is_db_alive(self) -> bool: ...

    @abstractmethod
    async def render_metrics(self) -> tuple[bytes, str]:
        """Prometheus exposition (body, content type) with fresh seat counts."""
