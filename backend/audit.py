"""Append-only audit trail at output/audit_trail.json.

The file is a JSON array of AuditEvent objects. Every record() call reads the
array, appends one event to the end, and atomically replaces the file, so
earlier runs are never erased and a crash mid-run keeps every step so far.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_core import to_jsonable_python

from models import AgentDeps, AuditEvent, AuditEventType

# CAMPUS_CUSTOMS_AUDIT overrides the path for sandbox testing only.
AUDIT_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_AUDIT") or Path(__file__).resolve().parent.parent / "output" / "audit_trail.json")
MAX_TEXT_CHARS = 4000  # long strings are clipped so one huge tool result cannot bloat the log


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
        return value[:MAX_TEXT_CHARS] + f"... [clipped {len(value) - MAX_TEXT_CHARS} chars]"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value]
    return value


class AuditTrail:
    def __init__(self, path: Path = AUDIT_PATH):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> list:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        try:
            events = json.loads(self.path.read_text())
        except json.JSONDecodeError as exc:
            # Never overwrite a log we cannot read: that would erase history.
            raise RuntimeError(f"{self.path} is not valid JSON; fix or move it before running the agents") from exc
        if not isinstance(events, list):
            raise RuntimeError(f"{self.path} must contain a JSON array")
        return events

    def record(
        self,
        run_id: str,
        event: AuditEventType,
        deps: AgentDeps | None = None,
        step: int | None = None,
        **data: Any,
    ) -> None:
        entry = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            event=event,
            agent=deps.agent if deps else None,
            agent_run_id=deps.agent_run_id if deps else None,
            chain=list(deps.chain) if deps else [],
            step=step,
            data=_clip(to_jsonable_python(data, fallback=str)),
        )
        with self._lock:
            events = self._load()
            events.append(entry.model_dump(mode="json"))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(events, indent=2))
            os.replace(tmp, self.path)
