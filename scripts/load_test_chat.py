#!/usr/bin/env python3
"""Simple concurrent load test for /chat/message and /admin endpoints."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import time
from urllib import error, request
import json


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> tuple[int, float]:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    started = time.perf_counter()
    with request.urlopen(req, timeout=20) as response:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return response.status, latency_ms


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, float]:
    req = request.Request(url, headers=headers or {}, method="GET")
    started = time.perf_counter()
    with request.urlopen(req, timeout=20) as response:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return response.status, latency_ms


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int((len(ordered) - 1) * q)
    return ordered[idx]


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test parking chatbot UI API")
    parser.add_argument("--base-url", required=True, help="Base URL, e.g. https://...azurecontainerapps.io")
    parser.add_argument("--requests", type=int, default=50, help="Number of requests")
    parser.add_argument("--concurrency", type=int, default=10, help="Parallel workers")
    parser.add_argument("--admin-token", default="", help="Optional x-api-token for /admin/requests checks")
    args = parser.parse_args()

    chat_url = f"{args.base_url.rstrip('/')}/chat/message"
    admin_url = f"{args.base_url.rstrip('/')}/admin/requests"
    headers = {"x-api-token": args.admin_token} if args.admin_token else None

    latencies: list[float] = []
    successes = 0
    failures = 0

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = []
        for i in range(args.requests):
            payload = {"message": "What are your working hours?", "thread_id": f"load-{i}"}
            futures.append(pool.submit(_post_json, chat_url, payload))
            if i % 10 == 0:
                futures.append(pool.submit(_get, admin_url, headers))

        for future in as_completed(futures):
            try:
                status, latency_ms = future.result()
                latencies.append(latency_ms)
                if 200 <= status < 300:
                    successes += 1
                else:
                    failures += 1
            except error.HTTPError:
                failures += 1
            except Exception:
                failures += 1

    print(f"total={len(latencies)} success={successes} failed={failures}")
    if latencies:
        print(f"p50_ms={_percentile(latencies, 0.50):.1f}")
        print(f"p95_ms={_percentile(latencies, 0.95):.1f}")
        print(f"avg_ms={statistics.fmean(latencies):.1f}")


if __name__ == "__main__":
    main()
