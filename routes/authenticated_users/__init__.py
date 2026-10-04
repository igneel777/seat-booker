from fastapi import APIRouter, Depends

from routes.authenticated_users.holds import router as holds_router
from routes.authenticated_users.shows import router as shows_router
from utils.auth import Role, require_role

router = APIRouter(dependencies=[Depends(require_role(Role.USER))])
router.include_router(shows_router)
router.include_router(holds_router)
