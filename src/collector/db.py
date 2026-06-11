import json
import sqlite3
from pathlib import Path

from src.db import init_db


class CollectorRun:
    def __init__(
        self,
        id: str,
        fonte: str,
        started_at: str,
        completed_at: str | None = None,
        n_trovati: int = 0,
        n_nuovi: int = 0,
        n_duplicati: int = 0,
        status: str = "running",
        errori: list[str] | None = None,
    ) -> None:
        self.id = id
        self.fonte = fonte
        self.started_at = started_at
        self.completed_at = completed_at
        self.n_trovati = n_trovati
        self.n_nuovi = n_nuovi
        self.n_duplicati = n_duplicati
        self.status = status
        self.errori: list[str] = errori or []


def insert_run(db_path: Path, run: CollectorRun) -> None:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO collector_runs
               (id, fonte, started_at, completed_at, n_trovati, n_nuovi,
                n_duplicati, status, errori)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id,
                run.fonte,
                run.started_at,
                run.completed_at,
                run.n_trovati,
                run.n_nuovi,
                run.n_duplicati,
                run.status,
                json.dumps(run.errori),
            ),
        )


def update_run_status(
    db_path: Path,
    run_id: str,
    status: str,
    errori: list[str] | None = None,
    completed_at: str | None = None,
    n_trovati: int | None = None,
    n_nuovi: int | None = None,
    n_duplicati: int | None = None,
) -> None:
    fields = ["status = ?"]
    values: list[object] = [status]
    if errori is not None:
        fields.append("errori = ?")
        values.append(json.dumps(errori))
    if completed_at is not None:
        fields.append("completed_at = ?")
        values.append(completed_at)
    if n_trovati is not None:
        fields.append("n_trovati = ?")
        values.append(n_trovati)
    if n_nuovi is not None:
        fields.append("n_nuovi = ?")
        values.append(n_nuovi)
    if n_duplicati is not None:
        fields.append("n_duplicati = ?")
        values.append(n_duplicati)
    values.append(run_id)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"UPDATE collector_runs SET {', '.join(fields)} WHERE id = ?", values
        )


def get_known_hashes(db_path: Path, fonte: str) -> set[str]:
    """Restituisce gli hash dei bandi già noti per una fonte."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM bandi WHERE fonte = ?", (fonte,)
        ).fetchall()
    return {row[0] for row in rows}
