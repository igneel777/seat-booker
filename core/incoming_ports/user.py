from abc import ABC, abstractmethod
from uuid import UUID

from models.api import ShowResponse


class UserPort(ABC):
    """Operations exposed to authenticated user routes."""

    @abstractmethod
    async def get_show(self, show_id: UUID) -> ShowResponse:
        """Raises ShowNotFoundError if no show has this id."""
