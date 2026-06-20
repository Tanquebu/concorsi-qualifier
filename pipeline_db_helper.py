#!/usr/bin/env python3
"""Aggiorna pipeline_runs in SQLite durante l'esecuzione di run_pipeline.sh.

Uso:
  python pipeline_db_helper.py init    <run_id>
  python pipeline_db_helper.py start   <run_id> <step>
  python pipeline_db_helper.py end     <run_id> <step>
  python pipeline_db_helper.py done    <run_id> completed|error [error_step] [error_msg]
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).parent / "concorsi.db"

_STEPS = ["collector", "extractor", "ocr_worker", "matcher", "reporter", "notifier"]

_DDL_PIPELINE_RUNS = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    current_step TEXT,
    status       TEXT NOT NULL DEFAULT 'running',
    steps_json   TEXT NOT NULL DEFAULT '[]',
    error_step   TEXT,
    error_msg    TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.executescript(_DDL_PIPELINE_RUNS)
    return conn


def cmd_init(run_id: str) -> None:
    steps = [{"name": s, "status": "pending", "started_at": None, "completed_at": None}
             for s in _STEPS]
    conn = _connect()
    # Sana run orfani lasciati in stato "running" da crash precedenti (es. SIGKILL)
    conn.execute(
        "UPDATE pipeline_runs SET status='error', completed_at=?, error_msg=?"
        " WHERE status='running'",
        (_now(), "processo terminato inaspettatamente"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO pipeline_runs (id, started_at, status, steps_json) VALUES (?,?,?,?)",
        (run_id, _now(), "running", json.dumps(steps)),
    )
    conn.commit()
    conn.close()


def cmd_start(run_id: str, step: str) -> None:
    conn = _connect()
    row = conn.execute("SELECT steps_json FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        return
    steps = json.loads(row[0])
    for s in steps:
        if s["name"] == step:
            s["status"] = "running"
            s["started_at"] = _now()
            break
    conn.execute(
        "UPDATE pipeline_runs SET current_step=?, steps_json=? WHERE id=?",
        (step, json.dumps(steps), run_id),
    )
    conn.commit()
    conn.close()


def cmd_end(run_id: str, step: str) -> None:
    conn = _connect()
    row = conn.execute("SELECT steps_json FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        return
    steps = json.loads(row[0])
    for s in steps:
        if s["name"] == step:
            s["status"] = "completed"
            s["completed_at"] = _now()
            break
    conn.execute(
        "UPDATE pipeline_runs SET steps_json=? WHERE id=?",
        (json.dumps(steps), run_id),
    )
    conn.commit()
    conn.close()


def cmd_done(run_id: str, status: str, error_step: str = "", error_msg: str = "") -> None:
    conn = _connect()
    row = conn.execute("SELECT steps_json FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
    if row:
        now = _now()
        steps = json.loads(row[0])
        for s in steps:
            if s["status"] == "running":
                if status == "error" and error_step and s["name"] == error_step:
                    s["status"] = "error"
                else:
                    s["status"] = "completed"
                s["completed_at"] = now
        conn.execute(
            "UPDATE pipeline_runs SET status=?, completed_at=?, current_step=NULL,"
            " error_step=?, error_msg=?, steps_json=? WHERE id=?",
            (status, now, error_step or None, error_msg or None, json.dumps(steps), run_id),
        )
    else:
        conn.execute(
            "UPDATE pipeline_runs SET status=?, completed_at=?, current_step=NULL,"
            " error_step=?, error_msg=? WHERE id=?",
            (status, _now(), error_step or None, error_msg or None, run_id),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    try:
        match sys.argv[1]:
            case "init":
                cmd_init(sys.argv[2])
            case "start":
                cmd_start(sys.argv[2], sys.argv[3])
            case "end":
                cmd_end(sys.argv[2], sys.argv[3])
            case "done":
                cmd_done(sys.argv[2], sys.argv[3],
                         sys.argv[4] if len(sys.argv) > 4 else "",
                         sys.argv[5] if len(sys.argv) > 5 else "")
    except Exception as exc:
        # Non bloccare mai la pipeline per un errore di tracking
        print(f"[pipeline_db_helper] warning: {exc}", file=sys.stderr)
        sys.exit(0)
