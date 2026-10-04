from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from core.incoming_ports import UserPort
from models.api import BookingResponse, BookSeatsRequest
from routes.dependencies import get_user_facade
from utils.auth import get_user_id

router = APIRouter(tags=["users"])


@router.post("/shows/{show_id}/reserve", status_code=status.HTTP_201_CREATED)
async def book_seats(
    show_id: UUID,
    body: BookSeatsRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    facade: Annotated[UserPort, Depends(get_user_facade)],
) -> BookingResponse:
    return await facade.book_seats(show_id, body.seats, body.idempotency_key, user_id)


@router.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: UUID,
    user_id: Annotated[str, Depends(get_user_id)],
    facade: Annotated[UserPort, Depends(get_user_facade)],
) -> Response:
    await facade.cancel_booking(booking_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
