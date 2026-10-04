from abc import ABC, abstractmethod


class HealthPort(ABC):
    """Operations exposed to probe routes."""

    @abstractmethod
    async def is_db_alive(self) -> bool: ...
