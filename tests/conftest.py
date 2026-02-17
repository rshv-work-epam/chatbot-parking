import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def disable_ml_guardrails_for_tests(monkeypatch):
    monkeypatch.setenv("GUARDRAILS_USE_ML", "false")
