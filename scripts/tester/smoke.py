"""Smoke test: walks the happy path against a live API, printing each step.

uv run python -m scripts.tester.smoke
"""

import asyncio
import uuid

from scripts.tester.helpers import BASE_URL, Api, check, expect_seats

SEATS = ["A1", "A2", "A3", "A4", "A5"]
PRICE = 25_000
USER = "user-1"


async def main() -> None:
    print(f"initialising smoke test against {BASE_URL}\n")
    async with Api() as api:
        print("checking the API is up")
        check(await api.health(), 200)

        print(f"using admin to create a show with seats {SEATS} at {PRICE} paise")
        created = await api.create_show(SEATS, PRICE)
        check(created, 201)
        show_id = created.body["id"]
        await expect_seats(api, USER, show_id, SEATS, "AVAILABLE")

        picked = ["A1", "A2"]
        print(f"holding seats {picked} as {USER}")
        held = await api.hold(show_id, picked, USER)
        check(held, 201)
        await expect_seats(api, USER, show_id, picked, "HELD")

        print(f"releasing hold {held.body['hold_id']}")
        check(await api.release(held.body["hold_id"], USER), 204)
        await expect_seats(api, USER, show_id, picked, "AVAILABLE")

        print(f"holding seats {picked} again as {USER}")
        check(await api.hold(show_id, picked, USER), 201)

        key = f"smoke-{uuid.uuid4()}"
        print(f"booking seats {picked} as {USER} (idempotency key {key})")
        booked = await api.reserve(show_id, picked, key, USER)
        check(booked, 201)
        print(f"amount charged: {booked.body['amount_paise']} paise\n")
        await expect_seats(api, USER, show_id, picked, "BOOKED")

        print(f"cancelling booking {booked.body['booking_id']}")
        check(await api.cancel(booked.body["booking_id"], USER), 204)
        await expect_seats(api, USER, show_id, picked, "AVAILABLE")

        print("replaying the same booking request with the same key")
        replay = await api.reserve(show_id, picked, key, USER)
        check(replay, 201)
        print(f"replay returned status {replay.body['status']} (expected CANCELLED)\n")

    print("smoke test passed")


if __name__ == "__main__":
    asyncio.run(main())
