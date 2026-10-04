from typing import Annotated

from fastapi import APIRouter, Depends, status

from core.incoming_ports import AdminPort
from models.api import CreateShowRequest, ShowResponse
from routes.dependencies import get_admin_facade

router = APIRouter(tags=["admin"])


@router.post("/shows", status_code=status.HTTP_201_CREATED)
async def create_show(
    body: CreateShowRequest,
    facade: Annotated[AdminPort, Depends(get_admin_facade)],
) -> ShowResponse:
    return await facade.create_show(body.name, body.seats, body.price_paise)
