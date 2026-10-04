# Seat Booker

Seat hold/booking API (FastAPI + Postgres). Design: [HLD.md](HLD.md), decisions: [DECISIONS.md](DECISIONS.md).

## Run locally

```bash
docker compose up --build
```

API on `http://localhost:8000` (docs at `/docs`), Postgres on `:5432`. No `.env` needed; DB credentials and the JWT secret have dev defaults.

> **The DB is not persisted.** Postgres has no volume, so restarting the stack (`docker compose down && docker compose up`) starts from an empty DB. Tables are created on app startup.

## Tester scripts

Scripts in `scripts/tester/` hit a running API over HTTP and print each step. They mint their own JWTs, so no manual auth is needed.

```bash
uv sync
uv run python -m scripts.tester.smoke
uv run python -m scripts.tester.errors
uv run python -m scripts.tester.storm
```

| Script | What it tests |
| --- | --- |
| `smoke` | Happy path: create show → hold → release → hold → book → cancel → replay the booking with the same idempotency key (returns `CANCELLED`). Checks seat status after every step. |
| `errors` | Each failure returns the right status: 401 (no/bad token), 403 (non-admin creates show), 404 (unknown show/seat), 422 (duplicate seats, >4 seats), 409 (seat held by someone else, idempotency key reused for different seats). |
| `storm` | ~20k concurrent requests on one 100-seat show, then checks: each contested seat booked by exactly one user, zero 5xx, seat counts always reconcile (during and after), same-key retries create one booking, per-user hold limit (4) holds under concurrency, user identity comes from the token, not the request body. |

**Base URL is configurable.** Scripts default to `http://localhost:8000`; to target another deployment, change `BASE_URL` in `scripts/tester/helpers.py`. For a deployed server with a non-default secret, also `export AUTH_JWT_SECRET=<server's secret>` so the minted tokens are accepted.

Storm size is `TOTAL_REQUESTS` in `scripts/tester/storm.py`.

## Auth: no user accounts

There is no users table or login. The API trusts a signed JWT: `sub` is the user id, `role` is `user` or `admin`. Any `sub` works, so a "user" exists as soon as a token is minted for it. The tester scripts mint tokens on the fly for each user they act as; to mint one by hand:

```bash
uv run python -m scripts.mint_token --role admin --sub admin-1
uv run python -m scripts.mint_token --sub user-1   # role defaults to user
```

Send it as `Authorization: Bearer <token>`.
