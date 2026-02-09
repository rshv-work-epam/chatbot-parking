# RAG Evaluation Report (Template)

## Performance Tests

- Measure average latency for retrieval + response generation.
- Load test `/record` endpoint for sustained writes.
- Use `chatbot_parking.evaluation.evaluate_retrieval()` to capture average retrieval latency.

## Retrieval Accuracy

- Compute Recall@K and Precision@K based on a labeled QA set.
- Track the percentage of responses filtered by guard rails.
- A sample dataset is available via `chatbot_parking.evaluation.sample_dataset()`.

## Sample Report

Create a report in `docs/evaluation_report.md` using the metrics produced by the evaluation helpers.

## Example Metrics

| Metric | Value | Notes |
| --- | --- | --- |
| Avg Latency | 1.2s | Measured over 100 queries |
| Recall@3 | 0.78 | Static corpus QA |
| Precision@3 | 0.66 | Static corpus QA |

## Next Steps

- Replace `FakeEmbeddings` with a production embedding model.
- Introduce automated regression evaluation in CI.
