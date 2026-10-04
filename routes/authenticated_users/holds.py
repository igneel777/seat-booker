from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from core.incoming_ports import UserPort
from models.api import HoldResponse, HoldSeatsRequest
from routes.dependencies import get_user_facade
from utils.auth import get_user_id

router = APIRouter(tags=["users"])


@router.post("/shows/{show_id}/hold", status_code=status.HTTP_201_CREATED)
async def hold_seats(
    show_id: UUID,
    body: HoldSeatsRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    facade: Annotated[UserPort, Depends(get_user_facade)],
) -> HoldResponse:
    return await facade.hold_seats(show_id, body.seats, user_id)
