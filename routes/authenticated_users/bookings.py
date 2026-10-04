from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from core.incoming_ports import UserPort
from models.api import BookingResponse, ReserveSeatsRequest
from routes.dependencies import get_user_facade
from utils.auth import get_user_id

router = APIRouter(tags=["users"])


@router.post("/shows/{show_id}/reserve", status_code=status.HTTP_201_CREATED)
async def reserve_seats(
    show_id: UUID,
    body: ReserveSeatsRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    facade: Annotated[UserPort, Depends(get_user_facade)],
) -> BookingResponse:
    return await facade.reserve_seats(
        show_id, body.seats, body.idempotency_key, user_id
    )
