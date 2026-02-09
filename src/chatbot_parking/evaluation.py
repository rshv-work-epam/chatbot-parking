"""Evaluation helpers for retrieval accuracy and latency."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from chatbot_parking.rag import build_vector_store, retrieve


@dataclass
class QAPair:
    question: str
    expected_doc_ids: set[str]


@dataclass
class RetrievalMetrics:
    recall_at_k: float
    precision_at_k: float
    average_latency_s: float


def evaluate_retrieval(dataset: Iterable[QAPair], k: int = 3) -> RetrievalMetrics:
    store = build_vector_store()
    total_recall = 0.0
    total_precision = 0.0
    total_latency = 0.0
    count = 0
    for item in dataset:
        start = time.perf_counter()
        result = retrieve(item.question, store, k=k)
        total_latency += time.perf_counter() - start
        retrieved_ids = {doc.metadata.get("id", "") for doc in result.documents}
        hits = len(retrieved_ids & item.expected_doc_ids)
        total_recall += hits / max(len(item.expected_doc_ids), 1)
        total_precision += hits / max(k, 1)
        count += 1
    if count == 0:
        return RetrievalMetrics(0.0, 0.0, 0.0)
    return RetrievalMetrics(
        recall_at_k=total_recall / count,
        precision_at_k=total_precision / count,
        average_latency_s=total_latency / count,
    )


def sample_dataset() -> list[QAPair]:
    return [
        QAPair("Where is the parking facility located?", {"parking_overview"}),
        QAPair("How do I reserve a space?", {"booking_process"}),
        QAPair("What payment methods are accepted?", {"payments"}),
    ]
