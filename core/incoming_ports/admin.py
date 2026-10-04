from abc import ABC, abstractmethod

from models.api import ShowResponse


class AdminPort(ABC):
    """Operations exposed to admin routes."""

    @abstractmethod
    async def create_show(
        self, show_name: str, seat_labels: list[str], price_paise: int
    ) -> ShowResponse: ...
