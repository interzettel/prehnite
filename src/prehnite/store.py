"""SQLite journal: completed stages are reused, submitted remote calls are recoverable."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class Journal:
    def __init__(self, workspace: Path, batch_id: str):
        self.root = workspace.resolve() / "batches" / batch_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "state.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
          task_key TEXT PRIMARY KEY, stage TEXT NOT NULL, status TEXT NOT NULL,
          request_id TEXT, path TEXT, provider TEXT, model TEXT,
          reserved_usd REAL NOT NULL DEFAULT 0, tokens_in INTEGER NOT NULL DEFAULT 0,
          tokens_out INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS task_attempts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          task_key TEXT NOT NULL,
          stage TEXT NOT NULL,
          provider TEXT NOT NULL,
          started_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')),
          outcome TEXT NOT NULL DEFAULT 'incomplete',
          elapsed_ms REAL,
          FOREIGN KEY(task_key) REFERENCES tasks(task_key)
        );
        CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.db.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM tasks WHERE task_key=?", (key,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["data"] = json.loads(data["data"])
        return data

    def put(self, key: str, stage: str, status: str, *, request_id: str | None = None,
            path: str | None = None, provider: str = "", model: str = "",
            reserved_usd: float = 0.0, tokens_in: int = 0, tokens_out: int = 0,
            data: dict | None = None) -> None:
        self.db.execute("""
        INSERT INTO tasks(task_key,stage,status,request_id,path,provider,model,reserved_usd,
                          tokens_in,tokens_out,data)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(task_key) DO UPDATE SET
          stage=excluded.stage,status=excluded.status,request_id=excluded.request_id,
          path=excluded.path,provider=excluded.provider,model=excluded.model,
          reserved_usd=excluded.reserved_usd,tokens_in=excluded.tokens_in,
          tokens_out=excluded.tokens_out,data=excluded.data,
          updated_at=CURRENT_TIMESTAMP
        """, (key, stage, status, request_id, path, provider, model, reserved_usd,
              tokens_in, tokens_out, json.dumps(data or {}, sort_keys=True)))
        self.db.commit()

    def begin_attempt(self, task_key: str, stage: str, provider: str) -> int:
        """Record that a new local invocation began, independently of task state."""
        cursor = self.db.execute(
            "INSERT INTO task_attempts(task_key,stage,provider) VALUES (?,?,?)",
            (task_key, stage, provider),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def finish_attempt(self, attempt_id: int, outcome: str, elapsed_ms: float) -> None:
        """Complete one attempt with measured monotonic wall elapsed time."""
        import math
        if (outcome not in ("completed", "failed")
                or isinstance(elapsed_ms, bool)
                or not math.isfinite(elapsed_ms) or elapsed_ms < 0):
            raise ValueError("Invalid attempt outcome or elapsed duration")
        cursor = self.db.execute(
            """UPDATE task_attempts SET outcome=?,elapsed_ms=?
               WHERE id=? AND outcome='incomplete'""",
            (outcome, elapsed_ms, attempt_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Attempt not found or already finished")
        self.db.commit()

    def attempts(self) -> list[dict]:
        """Append-only invocation evidence, including unfinished crash entries."""
        rows = self.db.execute(
            "SELECT id,task_key,stage,provider,started_at,outcome,elapsed_ms "
            "FROM task_attempts ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def set_fact(self, key: str, value: Any) -> None:
        self.db.execute("INSERT OR REPLACE INTO facts VALUES (?,?)",
                        (key, json.dumps(value)))
        self.db.commit()

    def fact(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def tasks(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM tasks ORDER BY updated_at,task_key").fetchall()
        return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    def reserved(self) -> float:
        return float(self.db.execute("SELECT COALESCE(SUM(reserved_usd),0) FROM tasks")
                     .fetchone()[0])

    @contextmanager
    def exclusive(self):
        """One active worker per batch, across processes (Windows and Unix).

        Kernel locks are automatically released when the worker crashes.
        The lock file is intentionally persistent; its existence does NOT
        indicate the batch is running.
        """
        path = self.root / "run.lock"
        with path.open("a+b") as handle:
            try:
                if os.name == "nt":
                    import msvcrt
                    if path.stat().st_size == 0:
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(
                    "Batch already has a running worker; refusing concurrent execution"
                ) from exc
            try:
                yield
            finally:
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def close(self):
        self.db.close()
