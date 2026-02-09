# Evaluation Report

## Run Metadata

- Run time (UTC): 2026-02-09T13:35:48.534191+00:00
- Dataset: `eval/qa_dataset.json`
- Dataset size: 10
- K: 3
- Vector backend: faiss
- Embeddings provider: fake
- LLM provider: echo
- Results JSON: `eval/results/20260209T133548Z_results.json`

## Metrics

| Metric | Value |
| --- | --- |
| Recall@3 | 0.5000 |
| Precision@3 | 0.1667 |
| Latency p50 | 0.08 ms |
| Latency p95 | 0.00 ms |

## Notes

- Report generated via `python -m chatbot_parking.eval.evaluate --write-report`.
