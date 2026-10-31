"""Process-wide job store.

Imported by name so `python -m rastro.api` (which runs this package's api
module as __main__) and `import rastro.api` share the same jobs.
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_results: dict[str, dict[str, Any]] = {}
