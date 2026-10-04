"""Errors test: bad requests get the right status code, printed step by step.

uv run python -m scripts.tester.errors
"""

import asyncio
import uuid

import jwt

from scripts.tester.helpers import BASE_URL, Api, check, expect_seats

SEATS = ["A1", "A2", "A3", "A4", "A5", "A6"]
USER_1, USER_2 = "user-1", "user-2"


def wrong_secret_token() -> str:
    payload = {"sub": USER_1, "role": "user"}
    return jwt.encode(payload, "not-the-server-secret-0000000000", algorithm="HS256")


async def main() -> None:
    print(f"initialising errors test against {BASE_URL}\n")
    async with Api() as api:
        print(f"using admin to create a show with seats {SEATS}")
        created = await api.create_show(SEATS)
        check(created, 201)
        show_id = created.body["id"]

        print("--- auth ---\n")
        print("getting the show with no token")
        check(await api.request("GET", f"/shows/{show_id}"), 401)

        print("getting the show with a token signed by the wrong secret")
        bad = wrong_secret_token()
        check(await api.request("GET", f"/shows/{show_id}", token=bad), 401)

        print(f"creating a show as {USER_1} (not an admin)")
        body = {"name": "nope", "seats": ["A1"], "price_paise": 100}
        check(await api.request("POST", "/shows", USER_1, body), 403)

        print("--- not found ---\n")
        print("holding a seat on a show that doesn't exist")
        check(await api.hold(str(uuid.uuid4()), ["A1"], USER_1), 404)

        print("holding seat Z9, which doesn't exist on this show")
        check(await api.hold(show_id, ["Z9"], USER_1), 404)

        print("--- validation ---\n")
        print("holding duplicate seats ['A1', 'A1']")
        check(await api.hold(show_id, ["A1", "A1"], USER_1), 422)

        print("holding 5 seats in one request (limit is 4)")
        check(await api.hold(show_id, SEATS[:5], USER_1), 422)

        print("--- conflicts ---\n")
        print(f"holding A1 as {USER_1}")
        held = await api.hold(show_id, ["A1"], USER_1)
        check(held, 201)

        print(f"holding A1 as {USER_2} while {USER_1} holds it")
        check(await api.hold(show_id, ["A1"], USER_2), 409)

        print(f"booking A1 as {USER_2} while {USER_1} holds it")
        check(await api.reserve(show_id, ["A1"], "errors-u2", USER_2), 409)

        print(f"{USER_2} releasing {USER_1}'s hold (should be a silent no-op)")
        check(await api.release(held.body["hold_id"], USER_2), 204)
        await expect_seats(api, USER_1, show_id, ["A1"], "HELD")

        print("--- idempotency ---\n")
        key = f"errors-{uuid.uuid4()}"
        print(f"booking A1 as {USER_1} with key {key}")
        check(await api.reserve(show_id, ["A1"], key, USER_1), 201)

        print("reusing the same key for a different seat (A2)")
        check(await api.reserve(show_id, ["A2"], key, USER_1), 409)
        await expect_seats(api, USER_1, show_id, ["A2"], "AVAILABLE")

    print("errors test passed")


if __name__ == "__main__":
    asyncio.run(main())
