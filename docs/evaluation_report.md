# Evaluation Report

## Run Metadata

- Run time (UTC): 2026-02-10T11:19:53.043206+00:00
- Dataset: `eval/qa_dataset.json`
- Dataset size: 32
- K: 3
- Vector backend: faiss
- Embeddings provider: openai
- LLM provider: openai
- Results JSON: `eval/results/20260210T111953Z_results.json`

## Metrics

| Metric | Value |
| --- | --- |
| Recall@3 | 0.9688 |
| Precision@3 | 0.3229 |
| Latency p50 | 248.77 ms |
| Latency p95 | 686.95 ms |

## Notes

- Report generated via `python -m chatbot_parking.eval.evaluate --write-report`.