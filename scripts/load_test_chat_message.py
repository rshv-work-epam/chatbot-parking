#!/usr/bin/env python3
"""Minimal load test for the chat API.

Why this exists:
- Stage 4 review asked for system/load testing.
- Keep dependencies at zero (stdlib only) so it can run anywhere.

Example:
  python scripts/load_test_chat_message.py --base-url http://localhost:8000 --requests 200 --concurrency 20
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import math
import time
import urllib.error
import urllib.request
from uuid import uuid4


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * p
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _post_chat_message(*, base_url: str, message: str, thread_id: str, timeout: float) -> tuple[bool, int | None, float]:
    url = f"{base_url.rstrip('/')}/chat/message"
    payload = {"message": message, "thread_id": thread_id}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()  # ensure the body is consumed
            elapsed = time.perf_counter() - start
            return (200 <= resp.status < 300, int(resp.status), elapsed)
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        elapsed = time.perf_counter() - start
        return (False, int(getattr(exc, "code", 0) or 0), elapsed)
    except Exception:
        elapsed = time.perf_counter() - start
        return (False, None, elapsed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load test /chat/message endpoint (stdlib only).")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL (default: http://localhost:8000)")
    parser.add_argument("--requests", type=int, default=100, help="Total requests (default: 100)")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers (default: 10)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds (default: 10)")
    parser.add_argument("--message", default="What are your working hours?", help="Message to send")
    parser.add_argument("--thread-prefix", default="load", help="Thread id prefix")
    args = parser.parse_args()

    total = max(1, int(args.requests))
    concurrency = max(1, int(args.concurrency))

    latencies: list[float] = []
    ok_count = 0
    status_counts: dict[str, int] = {}

    def one(i: int) -> tuple[bool, int | None, float]:
        return _post_chat_message(
            base_url=args.base_url,
            message=args.message,
            thread_id=f"{args.thread_prefix}:{uuid4()}:{i}",
            timeout=float(args.timeout),
        )

    started_at = time.perf_counter()
    with futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        for ok, status, elapsed in executor.map(one, range(total)):
            latencies.append(elapsed)
            if ok:
                ok_count += 1
            key = str(status) if status is not None else "error"
            status_counts[key] = status_counts.get(key, 0) + 1

    duration = time.perf_counter() - started_at
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    rps = total / duration if duration > 0 else float("inf")

    print("Load test results")
    print(f"- Base URL: {args.base_url}")
    print(f"- Requests: {total}")
    print(f"- Concurrency: {concurrency}")
    print(f"- Duration: {duration:.2f}s")
    print(f"- Throughput: {rps:.2f} req/s")
    if p50 is not None:
        print(f"- Latency p50: {p50*1000:.1f} ms")
    if p95 is not None:
        print(f"- Latency p95: {p95*1000:.1f} ms")
    print(f"- Success: {ok_count}/{total}")
    print(f"- Status counts: {status_counts}")

    return 0 if ok_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

