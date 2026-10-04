from fastapi import APIRouter, Depends

from utils.auth import Role, require_role

# Empty for now; seat view / hold / book endpoints land here.
router = APIRouter(dependencies=[Depends(require_role(Role.USER))])
