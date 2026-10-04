from fastapi import APIRouter, Depends

from routes.admin.shows import router as shows_router
from utils.auth import Role, require_role

router = APIRouter(dependencies=[Depends(require_role(Role.ADMIN))])
router.include_router(shows_router)
