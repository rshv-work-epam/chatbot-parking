# RAG Evaluation Report (Template)

## Performance Tests

- Measure average latency for retrieval + response generation.
- Load test `/record` endpoint for sustained writes.
- Run `python -m chatbot_parking.eval.evaluate --write-report` to compute metrics from `eval/qa_dataset.json` and update `docs/evaluation_report.md`.

## Retrieval Accuracy

- Compute Recall@K and Precision@K based on a labeled QA set.
- Track the percentage of responses filtered by guard rails.

## Example Metrics

| Metric | Value | Notes |
| --- | --- | --- |
| Avg Latency | 1.2s | Measured over 100 queries |
| Recall@3 | 0.78 | Static corpus QA |
| Precision@3 | 0.66 | Static corpus QA |

## Next Steps

- Replace `FakeEmbeddings` with a production embedding model.
- Introduce automated regression evaluation in CI.
