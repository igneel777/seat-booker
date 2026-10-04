from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from core.incoming_ports import UserPort
from models.api import ShowResponse
from routes.dependencies import get_user_facade

router = APIRouter(tags=["users"])


@router.get("/shows/{show_id}")
async def get_show(
    show_id: UUID,
    facade: Annotated[UserPort, Depends(get_user_facade)],
) -> ShowResponse:
    return await facade.get_show(show_id)
