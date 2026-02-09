# Evaluation Report (Sample)

## Dataset

- Source: `eval/qa_dataset.json`
- Size: 10 QA pairs
- Coverage: location, booking rules, amenities, payments, support

## Metrics (Example Run)

| Metric | Value |
| --- | --- |
| Recall@3 | 0.70 |
| Precision@3 | 0.60 |
| Latency p50 | 1.5 ms |
| Latency p95 | 0.0 ms |

## Notes

- Metrics use demo `FakeEmbeddings` + FAISS.
- Replace embeddings + vector DB for production reliability.
