"""Helpers for the tester scripts: async API client + step checks.

Swap BASE_URL to point the test scripts at another deployment. For a deployed app,
export AUTH_JWT_SECRET to match the server's secret.
"""

import asyncio
import sys
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any

import httpx

from scripts.mint_token import mint_token
from utils.auth import Role

BASE_URL = "http://localhost:8000"
ADMIN = "admin-1"


@dataclass
class Result:
    status: int
    latency_ms: float
    body: Any


class Api:
    def __init__(self, base_url: str = BASE_URL) -> None:
        # pool=None: requests queued client-side wait for a free connection
        # instead of failing; only the server's answer (or a read timeout) counts.
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(60, pool=None),
            # keepalive < uvicorn's 5s, so we never reuse a socket it's closing.
            limits=httpx.Limits(max_connections=200, keepalive_expiry=1),
        )
        self._tokens: dict[str, str] = {}

    async def __aenter__(self) -> "Api":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    def _token(self, user: str) -> str:
        if user not in self._tokens:
            role = Role.ADMIN if user == ADMIN else Role.USER
            self._tokens[user] = mint_token(role, user, ttl_seconds=3600)
        return self._tokens[user]

    async def request(
        self,
        method: str,
        path: str,
        user: str | None = None,
        json: Any = None,
        token: str | None = None,
    ) -> Result:
        """Authenticates as `user`, or with a raw `token` if given; else no auth."""
        token = token or (self._token(user) if user else None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        start = time.perf_counter()
        resp = await self._client.request(method, path, json=json, headers=headers)
        latency_ms = (time.perf_counter() - start) * 1000
        body = resp.json() if resp.content else None
        return Result(resp.status_code, latency_ms, body)

    # --- endpoint helpers -------------------------------------------------

    async def health(self) -> Result:
        return await self.request("GET", "/health")

    async def create_show(self, seats: list[str], price_paise: int = 25_000) -> Result:
        body = {"name": "tester-show", "seats": seats, "price_paise": price_paise}
        return await self.request("POST", "/shows", ADMIN, body)

    async def get_show(self, show_id: str, user: str) -> Result:
        return await self.request("GET", f"/shows/{show_id}", user)

    async def hold(self, show_id: str, seats: list[str], user: str) -> Result:
        return await self.request(
            "POST", f"/shows/{show_id}/hold", user, {"seats": seats}
        )

    async def release(self, hold_id: str, user: str) -> Result:
        return await self.request("DELETE", f"/holds/{hold_id}", user)

    async def reserve(
        self, show_id: str, seats: list[str], key: str, user: str
    ) -> Result:
        body = {"seats": seats, "idempotency_key": key}
        return await self.request("POST", f"/shows/{show_id}/reserve", user, body)

    async def cancel(self, booking_id: str, user: str) -> Result:
        return await self.request("DELETE", f"/bookings/{booking_id}", user)


async def burst(calls: list[Awaitable[Result]]) -> list[Result]:
    """Fire all calls at once; a client-side error becomes status 0 instead of
    crashing the burst. Results come back in the same order as `calls`."""
    results = await asyncio.gather(*calls, return_exceptions=True)
    return [r if isinstance(r, Result) else Result(0, 0.0, repr(r)) for r in results]


# --- step checks ------------------------------------------------------------


def check(result: Result, expected: int) -> None:
    """Print success, or print what went wrong and stop the script."""
    if result.status == expected:
        detail = result.body.get("detail") if result.status >= 400 else None
        if isinstance(detail, list):  # pydantic 422: keep just the messages
            detail = "; ".join(err["msg"] for err in detail)
        reason = f" -> {detail}" if detail else ""
        print(f"success ({result.status}, {result.latency_ms:.0f}ms){reason}\n")
        return
    print(f"FAILED: expected {expected}, got {result.status}: {result.body}")
    sys.exit(1)


async def expect_seats(
    api: Api, user: str, show_id: str, labels: list[str], status: str
) -> None:
    print(f"checking seats {labels} are {status}")
    show = await api.get_show(show_id, user)
    check(show, 200)
    actual = {s["label"]: s["status"] for s in show.body["seats"]}
    wrong = {label: actual[label] for label in labels if actual[label] != status}
    if wrong:
        print(f"FAILED: seats not {status}: {wrong}")
        sys.exit(1)
