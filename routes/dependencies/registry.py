from typing import cast

from core.incoming_facade import AdminFacade, HealthFacade, UserFacade
from core.incoming_ports import AdminPort, HealthPort, UserPort
from core.outgoing_facade import DBFacade
from infra.db_client import DBClient

# Facades are built once at startup and shared across requests.
_registry: dict[str, object] = {}


def init_facades(db_client: DBClient) -> None:
    db_facade = DBFacade(db_client)
    _registry["admin"] = AdminFacade(db_facade)
    _registry["user"] = UserFacade(db_facade)
    _registry["health"] = HealthFacade(db_facade)


def get_admin_facade() -> AdminPort:
    # KeyError here means the app was started without its lifespan.
    return cast(AdminPort, _registry["admin"])


def get_user_facade() -> UserPort:
    return cast(UserPort, _registry["user"])


def get_health_facade() -> HealthPort:
    return cast(HealthPort, _registry["health"])
