import sqlite3
from pathlib import Path

import pytest

from src.db import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_concorsi.db"


def test_init_db_creates_tables(db_path: Path) -> None:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"bandi", "collector_runs", "match_results"} <= tables


def test_init_db_idempotent(db_path: Path) -> None:
    init_db(db_path)
    init_db(db_path)  # non deve sollevare eccezioni


def test_bandi_insert_select_roundtrip(db_path: Path) -> None:
    init_db(db_path)
    record = {
        "id": "abc123",
        "fonte": "inpa.gov.it",
        "url": "https://example.com/bando/1",
        "titolo": "Concorso Informatico",
        "ente": "Comune di Test",
        "parse_method": "pdf_text",
        "extraction_confidence": 0.85,
        "status": "ok",
        "created_at": "2026-06-11T10:00:00",
        "testo_raw": "testo del bando",
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO bandi (id, fonte, url, titolo, ente, parse_method,
               extraction_confidence, status, created_at, testo_raw)
               VALUES (:id, :fonte, :url, :titolo, :ente, :parse_method,
               :extraction_confidence, :status, :created_at, :testo_raw)""",
            record,
        )
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM bandi WHERE id = 'abc123'").fetchone()
    assert row is not None
    assert row[0] == "abc123"
    assert row[2] == "https://example.com/bando/1"
