"""Storm test: one burst of ~N concurrent requests (reserves, plus one user's
parallel holds) against a fresh show, then the six rules are checked and printed
as PASS/FAIL.

    uv run python -m scripts.tester.storm
"""

import asyncio
import statistics
import time
import uuid
from collections import Counter
from collections.abc import Awaitable

from scripts.tester.helpers import BASE_URL, Api, Result, burst, check

TOTAL_REQUESTS = 2_000  # raise to 20_000 for the full storm
PRICE = 10_000

HOT = [f"A{i}" for i in range(1, 6)]
RETRY_SEAT = "B1"
CONFLICT_SEATS = ["B2", "B3"]
LIMIT_SEATS = [f"C{i}" for i in range(1, 11)]
SPOOF_SEATS = ["D1", "D2"]
NAMED = HOT + [RETRY_SEAT] + CONFLICT_SEATS + LIMIT_SEATS + SPOOF_SEATS
SEATS = NAMED + [f"F{i}" for i in range(1, 101 - len(NAMED))]  # 100 seats total

RETRY_COPIES = 300
CONFLICT_COPIES = 100
HOT_PER_SEAT = (TOTAL_REQUESTS - RETRY_COPIES - CONFLICT_COPIES - len(LIMIT_SEATS)) // 5

failed: list[str] = []


def verdict(rule: str, ok: bool, detail: str) -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {rule}: {detail}")
    if not ok:
        failed.append(rule)


def tally(results: list[Result]) -> str:
    counts = Counter(r.status for r in results)
    return ", ".join(f"{status} x {n}" for status, n in sorted(counts.items()))


def seat_counts(show: Result) -> Counter[str]:
    return Counter(s["status"] for s in show.body["seats"])


async def poll_reconciliation(
    show_id: str, stop: asyncio.Event, snapshots: list[Counter[str]]
) -> None:
    """Snapshot seat counts while the burst runs (rule 3, 'during'). Uses its own
    client so its GETs don't queue behind the burst's connections."""
    async with Api() as api:
        while not stop.is_set():
            show = await api.get_show(show_id, "poller")
            if show.status == 200:
                snapshots.append(seat_counts(show))
            await asyncio.sleep(0.25)


async def tracked(call: Awaitable[Result], done: Counter[int]) -> Result:
    """Count each finished request by status, for the live progress line."""
    try:
        result = await call
    except Exception:
        done[0] += 1
        raise
    done[result.status] += 1
    return result


async def print_progress(
    total: int, done: Counter[int], snapshots: list[Counter[str]], stop: asyncio.Event
) -> None:
    start = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(1)
        statuses = ", ".join(f"{k} x {v}" for k, v in sorted(done.items()))
        seats = dict(snapshots[-1]) if snapshots else {}
        elapsed = time.perf_counter() - start
        print(
            f"  [{elapsed:4.0f}s] {done.total()}/{total} done ({statuses})"
            f"  seats {seats}",
            flush=True,
        )


def build_burst(api: Api, show_id: str) -> dict[str, list[Awaitable[Result]]]:
    run = uuid.uuid4().hex[:8]  # keeps keys/users unique across reruns
    groups: dict[str, list[Awaitable[Result]]] = {}
    for seat in HOT:
        groups[f"hot {seat}"] = [
            api.reserve(show_id, [seat], f"hot-{run}-{seat}-{i}", f"u-{seat}-{i}")
            for i in range(HOT_PER_SEAT)
        ]
    groups["retry"] = [
        api.reserve(show_id, [RETRY_SEAT], f"retry-{run}", "retrier")
        for _ in range(RETRY_COPIES)
    ]
    groups["conflict"] = [
        api.reserve(show_id, [CONFLICT_SEATS[i % 2]], f"conflict-{run}", "conflicter")
        for i in range(CONFLICT_COPIES)
    ]
    # The per-user limit applies to holds only; bookings are uncapped.
    groups["limit"] = [api.hold(show_id, [seat], "greedy") for seat in LIMIT_SEATS]
    return groups


def check_burst(
    groups: dict[str, list[Result]], final: Counter[str], seats: dict
) -> None:
    every = [r for results in groups.values() for r in results]

    print("\nrule 1: each hot seat confirmed to exactly one user")
    for seat in HOT:
        results = groups[f"hot {seat}"]
        wins = sum(r.status == 201 for r in results)
        losses = sum(r.status == 409 for r in results)
        ok = wins == 1 and losses == len(results) - 1 and seats[seat] == "BOOKED"
        verdict(f"1 {seat}", ok, f"{wins} x 201, {losses} x 409, seat {seats[seat]}")

    print("\nrule 2: zero 5xx (and zero client errors) across the burst")
    server_errors = sum(r.status >= 500 for r in every)
    client_errors = [r for r in every if r.status == 0]
    verdict("2 no 5xx", server_errors == 0, f"{server_errors} x 5xx")
    sample = f" e.g. {client_errors[0].body}" if client_errors else ""
    verdict("2 no client errors", not client_errors, f"{len(client_errors)}{sample}")

    print("\nrule 3: reconciliation after the burst")
    booked_by_201 = {
        seat
        for name, results in groups.items()
        if name not in ("conflict", "limit")
        for seat, r in zip(seats_for(name), results, strict=True)
        if r.status == 201
    } | {s for s in CONFLICT_SEATS if seats[s] == "BOOKED"}
    verdict(
        "3 sum == total",
        sum(final.values()) == len(SEATS),
        f"{dict(final)} = {sum(final.values())} / {len(SEATS)}",
    )
    held_wins = sum(r.status == 201 for r in groups["limit"])
    verdict(
        "3 HELD == holds that got a 201",
        final["HELD"] == held_wins,
        f"{final['HELD']} held vs {held_wins} holds with a 201",
    )
    verdict(
        "3 BOOKED == seats that got a 201",
        final["BOOKED"] == len(booked_by_201),
        f"{final['BOOKED']} booked vs {len(booked_by_201)} seats with a 201",
    )

    print("\nrule 4: idempotent retries move nothing extra")
    retry = groups["retry"]
    ids = {r.body["booking_id"] for r in retry if r.status == 201}
    verdict(
        "4 same key -> one booking",
        all(r.status == 201 for r in retry) and len(ids) == 1,
        f"{tally(retry)}, {len(ids)} distinct booking id(s)",
    )
    conflict = groups["conflict"]
    by_seat = {
        s: Counter(r.status for i, r in enumerate(conflict) if i % 2 == n)
        for n, s in enumerate(CONFLICT_SEATS)
    }
    booked = [s for s in CONFLICT_SEATS if seats[s] == "BOOKED"]
    ok = len(booked) == 1 and set(by_seat[booked[0]]) == {201}
    loser = [s for s in CONFLICT_SEATS if s not in booked]
    ok = ok and all(set(by_seat[s]) == {409} and seats[s] == "AVAILABLE" for s in loser)
    detail = ", ".join(f"{s}: {dict(by_seat[s])} -> {seats[s]}" for s in CONFLICT_SEATS)
    verdict("4 same key, different seats -> 409", ok, detail)

    print("\nrule 5: per-user hold limit under concurrency")
    limit = groups["limit"]
    wins = sum(r.status == 201 for r in limit)
    rejected = sum(r.status == 403 for r in limit)
    held = sum(seats[s] == "HELD" for s in LIMIT_SEATS)
    verdict(
        "5 greedy user holds <= 4",
        wins <= 4 and rejected == len(limit) - wins and held == wins,
        f"{tally(limit)}, {held} of {len(LIMIT_SEATS)} seats HELD",
    )


def seats_for(group: str) -> list[str]:
    """Seat each request in a booking group targeted, in request order."""
    if group == "retry":
        return [RETRY_SEAT] * RETRY_COPIES
    return [group.removeprefix("hot ")] * HOT_PER_SEAT


async def check_spoofing(api: Api, show_id: str) -> None:
    """Rule 6: a spoofed user field in the body is ignored; the token decides."""
    print("\nrule 6: identity comes from the token, not the body")
    booked = await api.request(
        "POST",
        f"/shows/{show_id}/reserve",
        "spoofer",
        {
            "seats": ["D1"],
            "idempotency_key": f"spoof-{uuid.uuid4()}",
            "booked_by": "victim",
        },
    )
    held = await api.request(
        "POST",
        f"/shows/{show_id}/hold",
        "spoofer",
        {"seats": ["D2"], "held_by": "victim", "user_id": "victim"},
    )
    if booked.status != 201 or held.status != 201:
        verdict(
            "6 spoofed requests", False, f"reserve {booked.status}, hold {held.status}"
        )
        return

    await api.cancel(booked.body["booking_id"], "victim")
    await api.release(held.body["hold_id"], "victim")
    seats = await seat_map(api, show_id)
    verdict(
        "6 'victim' can't cancel/release",
        seats["D1"] == "BOOKED" and seats["D2"] == "HELD",
        f"after victim's cancel+release: D1 {seats['D1']}, D2 {seats['D2']}",
    )

    await api.cancel(booked.body["booking_id"], "spoofer")
    await api.release(held.body["hold_id"], "spoofer")
    seats = await seat_map(api, show_id)
    verdict(
        "6 token user owns them",
        seats["D1"] == "AVAILABLE" and seats["D2"] == "AVAILABLE",
        f"after spoofer's cancel+release: D1 {seats['D1']}, D2 {seats['D2']}",
    )


async def seat_map(api: Api, show_id: str) -> dict[str, str]:
    show = await api.get_show(show_id, "poller")
    return {s["label"]: s["status"] for s in show.body["seats"]}


def print_latency(results: list[Result], elapsed: float) -> None:
    ms = sorted(r.latency_ms for r in results if r.status)
    if len(ms) < 2:
        return
    p50, p95 = statistics.quantiles(ms, n=100)[49], statistics.quantiles(ms, n=100)[94]
    print(
        f"latency p50 {p50:.0f}ms, p95 {p95:.0f}ms, max {ms[-1]:.0f}ms "
        f"(includes client-side queueing); {len(results) / elapsed:.0f} req/s"
    )


async def main() -> None:
    print(f"initialising storm test against {BASE_URL}\n")
    async with Api() as api:
        print(f"using admin to create a show with {len(SEATS)} seats")
        created = await api.create_show(SEATS, PRICE)
        check(created, 201)
        show_id = created.body["id"]

        named = build_burst(api, show_id)
        total = sum(len(calls) for calls in named.values())
        print(
            f"firing {total} concurrent requests: {HOT_PER_SEAT} reserves per hot seat "
            f"{HOT}, {RETRY_COPIES} same-key retries, {CONFLICT_COPIES} same-key "
            f"conflicts, {len(LIMIT_SEATS)} holds from one greedy user",
            flush=True,
        )

        stop, snapshots, done = asyncio.Event(), [], Counter()
        poller = asyncio.create_task(poll_reconciliation(show_id, stop, snapshots))
        progress = asyncio.create_task(print_progress(total, done, snapshots, stop))
        start = time.perf_counter()
        flat = await burst(
            [tracked(c, done) for calls in named.values() for c in calls]
        )
        elapsed = time.perf_counter() - start
        stop.set()
        await asyncio.gather(poller, progress)

        groups, i = {}, 0
        for name, calls in named.items():
            groups[name], i = flat[i : i + len(calls)], i + len(calls)

        print(f"burst done in {elapsed:.1f}s")
        for name, results in groups.items():
            print(f"  {name:<10} {tally(results)}")
        print_latency(flat, elapsed)

        print("\nrule 3 (during): reconciliation in every snapshot")
        bad = [s for s in snapshots if sum(s.values()) != len(SEATS)]
        verdict(
            "3 during",
            not bad and bool(snapshots),
            f"{len(snapshots)} snapshots, {len(bad)} off",
        )

        show = await api.get_show(show_id, "poller")
        check(show, 200)
        seats = {s["label"]: s["status"] for s in show.body["seats"]}
        check_burst(groups, seat_counts(show), seats)

        await check_spoofing(api, show_id)

    print(f"\nstorm test {'FAILED: ' + ', '.join(failed) if failed else 'passed'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
