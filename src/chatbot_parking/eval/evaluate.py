"""Run simple retrieval evaluation for the parking chatbot."""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from chatbot_parking.config import get_settings
from chatbot_parking.rag import build_vector_store, retrieve

DATASET_PATH = Path("eval/qa_dataset.json")
REPORT_PATH = Path("docs/evaluation_report.md")


def load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError("Dataset not found at data/qa_dataset.json")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def evaluate(k: int = 3) -> dict:
    store = build_vector_store(insert_documents=False)
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


def _write_report(metrics: dict, k: int, dataset_size: int, results_path: Path) -> None:
    settings = get_settings()
    run_time = datetime.now(timezone.utc).isoformat()
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Evaluation Report",
                "",
                "## Run Metadata",
                "",
                f"- Run time (UTC): {run_time}",
                f"- Dataset: `{DATASET_PATH.as_posix()}`",
                f"- Dataset size: {dataset_size}",
                f"- K: {k}",
                f"- Vector backend: {settings.vector_backend}",
                f"- Embeddings provider: {settings.embeddings_provider}",
                f"- LLM provider: {settings.llm_provider}",
                f"- Results JSON: `{results_path.as_posix()}`",
                "",
                "## Metrics",
                "",
                "| Metric | Value |",
                "| --- | --- |",
                f"| Recall@{k} | {metrics['recall_at_k']:.4f} |",
                f"| Precision@{k} | {metrics['precision_at_k']:.4f} |",
                f"| Latency p50 | {metrics['latency_p50_ms']:.2f} ms |",
                f"| Latency p95 | {metrics['latency_p95_ms']:.2f} ms |",
                "",
                "## Notes",
                "",
                "- Report generated via `python -m chatbot_parking.eval.evaluate --write-report`.",
            ]
        ),
        encoding="utf-8",
    )


def _write_results(metrics: dict, k: int, dataset_size: int) -> Path:
    settings = get_settings()
    output_dir = Path(settings.eval_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_path = output_dir / f"{timestamp}_results.json"
    payload = {
        "run_time_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(DATASET_PATH),
        "dataset_size": dataset_size,
        "k": k,
        "vector_backend": settings.vector_backend,
        "embeddings_provider": settings.embeddings_provider,
        "llm_provider": settings.llm_provider,
        "metrics": metrics,
    }
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return results_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate retrieval performance.")
    parser.add_argument("--k", type=int, default=3, help="Top-k documents to retrieve.")
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write results JSON and update docs/evaluation_report.md.",
    )
    args = parser.parse_args()

    dataset = load_dataset()
    metrics = evaluate(k=args.k)
    for key, value in metrics.items():
        print(f"{key}: {value:.4f}")

    if args.write_report:
        results_path = _write_results(metrics, args.k, len(dataset))
        _write_report(metrics, args.k, len(dataset), results_path)


if __name__ == "__main__":
    main()
