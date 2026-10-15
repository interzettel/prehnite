"""SQLite journal: completed stages are reused, submitted remote calls are recoverable."""
from __future__ import annotations

import json
import sqlite3
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

    def close(self):
        self.db.close()
