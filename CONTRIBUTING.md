# Contributing

Thanks for taking a look.

This repository is kept intentionally small and reviewer-friendly. If you propose changes:

1. Keep diffs focused (one concern per PR).
2. Add/adjust tests for behavior changes.
3. Do not add secrets, keys, or credentials.
4. Prefer simple, readable implementations over clever ones.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m pytest -q
```

