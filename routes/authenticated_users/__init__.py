from fastapi import APIRouter, Depends

from routes.authenticated_users.shows import router as shows_router
from utils.auth import Role, require_role

router = APIRouter(dependencies=[Depends(require_role(Role.USER))])
router.include_router(shows_router)
