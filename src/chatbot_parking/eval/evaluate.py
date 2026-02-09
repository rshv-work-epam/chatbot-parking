"""Run simple retrieval evaluation for the parking chatbot."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from chatbot_parking.rag import build_vector_store, retrieve

DATASET_PATH = Path("eval/qa_dataset.json")


def load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError("Dataset not found at data/qa_dataset.json")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def evaluate(k: int = 3) -> dict:
    store = build_vector_store()
    dataset = load_dataset()

    recalls: list[float] = []
    precisions: list[float] = []
    latencies: list[float] = []

    for sample in dataset:
        start = time.perf_counter()
        result = retrieve(sample["question"], store, k=k)
        latencies.append(time.perf_counter() - start)

        retrieved_ids = {doc.metadata.get("id") for doc in result.documents}
        expected_ids = set(sample["expected_ids"])
        if not expected_ids:
            continue

        hit_count = len(retrieved_ids & expected_ids)
        recalls.append(hit_count / len(expected_ids))
        precisions.append(hit_count / max(len(retrieved_ids), 1))

    return {
        "recall_at_k": statistics.mean(recalls) if recalls else 0.0,
        "precision_at_k": statistics.mean(precisions) if precisions else 0.0,
        "latency_p50_ms": statistics.median(latencies) * 1000 if latencies else 0.0,
        "latency_p95_ms": statistics.quantiles(latencies, n=20)[18] * 1000 if len(latencies) >= 20 else 0.0,
    }


def main() -> None:
    metrics = evaluate()
    for key, value in metrics.items():
        print(f"{key}: {value:.4f}")


if __name__ == "__main__":
    main()
