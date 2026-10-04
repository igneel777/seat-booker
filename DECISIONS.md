# Decisions

## Running the PoC

1. **Postgres not persisted.** No volume; `docker compose down && up` starts with an empty DB, so test runs are repeatable.
2. **Env defaults are dev-only.** DB password and JWT secret have defaults (commented in `settings/`) so no `.env` is needed. Override via `DB_*`, `AUTH_JWT_SECRET`.
3. **Booking config:** `BOOKING_HOLD_TTL` (default 10 min), `BOOKING_PER_HOLD_LIMIT` (default 4).
4. **Single uvicorn worker.** Correctness doesn't depend on it (locks live in Postgres), so `--workers N` is safe. Caveats: Prometheus metrics become per worker (needs multiprocess mode), and DB connections multiply per worker.

## Product flow

5. **All-or-nothing holds and bookings.** A request for A1 + A2 gets both or a `409`, even if one is free. Like the real world: booking for a family, you don't want a partial set.
6. **Book directly, or hold then book.** The requirement was ambiguous, so holds are a separate capability. Flows:
   - **Book directly:** one `reserve` call.
   - **Hold → pay → book (recommended):** the payment webhook calls `reserve` with the same idempotency key, so retries are safe. Ideally `reserve` would take the `hold_id` and book exactly the held seats together. Not built here; `reserve` takes seat labels.
   - **Pay → book → refund on conflict (not recommended):** refunds pile up under contention.

## Design

7. **Postgres row locks, not Redis.** `FOR UPDATE` in label order: one store, no dual writes, no deadlocks.
8. **Holds are rows with an expiry, not open transactions.** Checked against Postgres `now()`; cleanup is optional.
9. **Seats static; state in `seat_reservations`.** No row = AVAILABLE. Partial unique index allows one active row per seat.
10. **Idempotency per (user, key).** Same request replays; different seats → `409`. An advisory lock makes parallel retries replay.
11. **Cancel is a soft delete.** Seats are freed; replaying the key returns `CANCELLED`.
12. **Core owns transactions, the adapter owns SQL.** Core uses `DBPort` primitives, never SQLAlchemy.
