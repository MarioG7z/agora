"""The event log of a run, one JSON line per event."""

import json
from datetime import UTC, datetime
from pathlib import Path

from agora.orchestrator import Event


class EventLog:
    """Appends every event as one JSON line: the history of a run, filterable by task."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, run_id: str, event: Event) -> None:
        """Append the event as one JSON line, with the time and the run id."""
        line = {"time": datetime.now(UTC).isoformat(), "run_id": run_id, **event.model_dump()}
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")
