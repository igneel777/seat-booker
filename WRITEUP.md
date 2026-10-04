# Write-up

## 1. Atomic decision

One Postgres transaction per hold/book: `SELECT ... FROM seats WHERE label IN (...) ORDER BY label FOR UPDATE` → check reservations → write → `COMMIT`.

- **Race-free:** the row lock serialises writers of a seat. The loser waits, then its check (a new statement under READ COMMITTED) sees the winner's commit → `409`.
- **Backstop:** a partial unique index allows one active (HELD/BOOKED) reservation per seat, so a bug can't produce a double booking.
- **No deadlock:** seats are locked in sorted label order. A deadlock needs someone holding A2 while waiting for A1, which is impossible when everyone locks A1 first.
- **All-or-nothing:** any seat taken → the whole transaction rolls back.

## 2. Idempotency

- **Stored in** `bookings.idempotency_key`, `UNIQUE (booked_by, idempotency_key)`.
- **Exactly-once:** an advisory lock on (user, key) queues parallel retries; each one finds the existing booking and replays it. Booking and seat rows commit in one transaction; the unique constraint is the backstop.
- **Same key, different seats/show** → `409`. Same key after cancel → returns the booking as `CANCELLED`, no re-book.

## 3. Holds & expiry

- A hold is a row with `hold_expires_at = db now() + BOOKING_HOLD_TTL` (10 min), not an open transaction.
- Expired holds count as AVAILABLE everywhere; only the Postgres clock is used. Rows are cleaned up lazily on the next hold/book/release.
- The per-user limit (4) is checked under an advisory lock, so parallel holds can't bypass it.

## 4. Consistency vs. availability

**Consistency over availability (CP).** A single Postgres primary is the only source of truth and the only lock manager.

- On a partition between app and DB, requests **fail** (`/health` goes red) instead of accepting bookings we can't verify. There is no second writer, so no split brain.
- Under contention, losers get a fast `409`. Under heavy load, requests queue on locks and on the connection pool and can time out.
- The right trade-off for ticketing: rejecting or delaying a few requests is cheap; a double booking (two people, one seat, both charged) is not.

## 5. Observability

**Built (kept simple):** Prometheus `/metrics`, `/health` (with a DB ping), structured logs with a correlation id per request.

| Metric | Exposed today |
|---|---|
| `seatbooker_reservations_confirmed`, `..._reservation_seats_confirmed` | New bookings / seats committed |
| `seatbooker_reservations_declined{operation, reason}` | `seat_taken`, `per_user_limit`, `idempotent_replay`, `idempotency_conflict`, `seat_not_found` |
| `seatbooker_bookings_cancelled` | Cancellations |
| `seatbooker_seats{show_id, status}` | Seats per status, read from the DB at scrape time |

**Page me at 2am for:**

| Signal | Why |
|---|---|
| **Double-booking invariant broken:** `BOOKED` seats ≠ seats confirmed − seats cancelled, or booked amount ≠ Σ seat prices | The one thing the system must never do. Should be 0; any drift is an incident |
| **5xx rate / `/health` failing** | DB unreachable or app crashing; nobody can book |
| **p99 latency on hold/reserve, pool checkout timeouts, lock waits** (`pg_locks` / `pg_stat_activity` waiting on `Lock`) | App or DB is choking. Scale up, or throttle with a **user queue** (admit N users at a time to a hot show) |
| **Deadlocks** (`pg_stat_database.deadlocks` > 0) | Should be impossible given lock ordering; a non-zero value means a code path broke the ordering |

**Watch, don't page:**
- `declined{reason="seat_taken"}` spike → a hot show with real contention (expected at on-sale). If it's high outside on-sale, the seat map shown to users is stale.
- `idempotent_replay` spike → clients or the payment webhook are retrying hard (timeouts upstream).
- `idempotency_conflict` > 0 → a client bug reusing keys.
- Hold → book conversion (holds created vs. confirmed) → low means TTL too short or payment failing.

## 6. AI usage

- **AI wrote:** most of the code and the docs, including the diagrams. I directed it step by step and reviewed every change.
- **I decided:** Postgres row locks over Redis, all-or-nothing holds/bookings, holds as a separate capability (the requirement's wording was ambiguous), consistency over availability. I reviewed the HLD and LLD and kept AI on a tight leash against them.
- **AI taught me:** Prometheus. I've monitored pipelines and apps with other tools; I used AI to learn the Prometheus client and metric types.

## 7. What I'd do next

1. **Async hold expiry:** move cleanup out of the request path into a cron job, or emit an event at each hold's expiry and clean up asynchronously.
2. **Payment-driven flow:** clarify the flow with the payment gateway. Book by `hold_id` (move exactly the held seats together) from the payment webhook, and handle late payments on expired holds (refund).
3. **Lock timeouts:** set `lock_timeout` / `statement_timeout` so a choking DB fails fast with a clear error instead of queueing, and alert on it.
4. **Gate per-user concurrency outside the DB:** move the advisory locks to Redis and/or add a rate limiter, to cut DB load and throttle aggressive clients.
5. **Auth:** today admin and user are strictly separate (an admin can't book). Relax this if admins need to book on someone's behalf.
6. **Split holds from bookings:** separate tables for holds and booked seats, instead of one `seat_reservations` lifecycle table.
