"""Azure Functions bootstrap helpers.

This function app is deployed from a folder that also includes the repository `src/`
directory. Ensure the `src/` path is available for imports at runtime.
"""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_src_on_path() -> None:
    src_path = Path(__file__).resolve().parent / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

