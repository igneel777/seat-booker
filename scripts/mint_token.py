"""Mint a JWT for local testing.

Run from the repo root:
    uv run python -m scripts.mint_token --role admin
"""

import argparse
import time

import jwt

from settings import get_auth_settings
from utils.auth import Role


def mint_token(role: Role, sub: str, ttl_seconds: int) -> str:
    settings = get_auth_settings()
    payload = {"sub": sub, "role": role.value, "exp": int(time.time()) + ttl_seconds}
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint a JWT for local testing.")
    parser.add_argument("--role", type=Role, choices=list(Role), default=Role.USER)
    parser.add_argument("--sub", default="user-1", help="user id (default: user-1)")
    parser.add_argument("--ttl", type=int, default=3600, help="seconds (default: 3600)")
    args = parser.parse_args()
    print(mint_token(args.role, args.sub, args.ttl))


if __name__ == "__main__":
    main()
