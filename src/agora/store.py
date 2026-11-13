"""Persistence of the board in SQLite: task states and every artifact version."""

import json
import sqlite3
from pathlib import Path

from agora.board import Board, Status, Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    artifact TEXT,
    PRIMARY KEY (run_id, name)
);
CREATE TABLE IF NOT EXISTS artifact_versions (
    run_id TEXT NOT NULL,
    task TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    PRIMARY KEY (run_id, task, version)
);
"""


class BoardStore:
    """Saves and loads a board in SQLite, so a run can resume after a crash."""

    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def save(self, run_id: str, board: Board) -> None:
        # One transaction for everything: a task is never stored as approved without its
        # artifact. If anything fails inside the block, nothing is written.
        """Save every task of the board, and new artifact versions, in one transaction."""
        with self.conn:
            for task in board.tasks.values():
                self.conn.execute(
                    "INSERT OR REPLACE INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        task.name,
                        task.status,
                        json.dumps(task.depends_on),
                        task.attempts,
                        task.artifact,
                    ),
                )
                if task.artifact is not None:
                    self._save_version(run_id, task)

    def _save_version(self, run_id: str, task: Task) -> None:
        # Old versions are kept: a new row is added only when the artifact changed.
        """Add the artifact as a new version if it changed."""
        latest = self.conn.execute(
            "SELECT version, content FROM artifact_versions"
            " WHERE run_id = ? AND task = ? ORDER BY version DESC LIMIT 1",
            (run_id, task.name),
        ).fetchone()
        if latest is not None and latest[1] == task.artifact:
            return
        version = 1 if latest is None else latest[0] + 1
        self.conn.execute(
            "INSERT INTO artifact_versions VALUES (?, ?, ?, ?)",
            (run_id, task.name, version, task.artifact),
        )

    def versions(self, run_id: str, task_name: str) -> list[str]:
        """Every stored version of the artifact of a task, oldest first."""
        rows = self.conn.execute(
            "SELECT content FROM artifact_versions WHERE run_id = ? AND task = ? ORDER BY version",
            (run_id, task_name),
        ).fetchall()
        return [row[0] for row in rows]

    def load(self, run_id: str) -> Board:
        """Rebuild the board of a stored run; raises KeyError if it does not exist."""
        rows = self.conn.execute(
            "SELECT name, status, depends_on, attempts, artifact FROM tasks WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        if not rows:
            raise KeyError(f"No run stored with id {run_id}")
        tasks = []
        for name, status, depends_on, attempts, artifact in rows:
            task = Task(name, json.loads(depends_on))
            # Restoring a saved state, not making a transition, so move_to is not used.
            task.status = Status(status)
            task.attempts = attempts
            task.artifact = artifact
            tasks.append(task)
        return Board(tasks)

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
