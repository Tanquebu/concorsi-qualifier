import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.collector.db import CollectorRun, get_known_hashes, insert_run, update_run_status
from src.collector.dedup import compute_hash
from src.db import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    init_db(p)
    return p


# --- dedup ---

def test_compute_hash_deterministic() -> None:
    h1 = compute_hash("https://example.com/bando/1", "2026-01-01")
    h2 = compute_hash("https://example.com/bando/1", "2026-01-01")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_different_url() -> None:
    h1 = compute_hash("https://example.com/bando/1", "2026-01-01")
    h2 = compute_hash("https://example.com/bando/2", "2026-01-01")
    assert h1 != h2


def test_compute_hash_different_date() -> None:
    h1 = compute_hash("https://example.com/bando/1", "2026-01-01")
    h2 = compute_hash("https://example.com/bando/1", "2026-01-02")
    assert h1 != h2


# --- collector db ---

def test_insert_and_get_run(db_path: Path) -> None:
    run = CollectorRun(id="run-001", fonte="inpa", started_at="2026-06-11T10:00:00")
    insert_run(db_path, run)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, fonte, status FROM collector_runs WHERE id = 'run-001'"
        ).fetchone()
    assert row is not None
    assert row[0] == "run-001"
    assert row[1] == "inpa"
    assert row[2] == "running"


def test_update_run_status(db_path: Path) -> None:
    run = CollectorRun(id="run-002", fonte="ripam", started_at="2026-06-11T10:00:00")
    insert_run(db_path, run)
    update_run_status(
        db_path,
        "run-002",
        status="completed",
        completed_at="2026-06-11T10:05:00",
        n_trovati=10,
        n_nuovi=5,
        n_duplicati=5,
    )
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, n_nuovi, completed_at FROM collector_runs WHERE id = 'run-002'"
        ).fetchone()
    assert row[0] == "completed"
    assert row[1] == 5
    assert row[2] == "2026-06-11T10:05:00"


def test_get_known_hashes_empty(db_path: Path) -> None:
    hashes = get_known_hashes(db_path, "inpa")
    assert hashes == set()


def _insert_bando(db_path: Path, id: str, fonte: str, url: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO bandi (id, fonte, url, parse_method, status, created_at, testo_raw)"
            " VALUES (?, ?, ?, 'pdf_text', 'ok', '2026-06-11', '')",
            (id, fonte, url),
        )


def test_get_known_hashes_returns_inserted(db_path: Path) -> None:
    _insert_bando(db_path, "hash-abc", "inpa", "https://example.com")
    hashes = get_known_hashes(db_path, "inpa")
    assert "hash-abc" in hashes


def test_get_known_hashes_filters_by_fonte(db_path: Path) -> None:
    _insert_bando(db_path, "hash-xyz", "ripam", "https://ripam.cloud/1")
    hashes = get_known_hashes(db_path, "inpa")
    assert "hash-xyz" not in hashes


# --- run_collector ---

def test_run_collector_mock(tmp_path: Path) -> None:
    from src.collector import run_collector

    sources_yaml = tmp_path / "sources.yaml"
    sources_yaml.write_text(
        "sources:\n"
        "  - nome: TestFonte\n"
        "    url: https://example.com\n"
        "    tipo: html\n"
        "    frequenza: daily\n"
    )
    db = tmp_path / "test.db"
    raw = tmp_path / "raw"

    with patch("src.collector.download_source", return_value=["hash-new"]):
        result = run_collector(sources_yaml, db_path=db, raw_dir=raw)

    assert result.n_nuovi >= 1
    assert result.status in ("completed", "completed_with_errors")


def test_run_collector_returns_collector_run(tmp_path: Path) -> None:
    from src.collector import CollectorRun, run_collector

    sources_yaml = tmp_path / "sources.yaml"
    sources_yaml.write_text("sources: []\n")
    db = tmp_path / "test.db"

    with patch("src.collector.download_source", return_value=[]):
        result = run_collector(sources_yaml, db_path=db)

    assert isinstance(result, CollectorRun)


# --- fixture reale InPA ---

_FIXTURE_HTML = Path(__file__).parent / "fixtures" / "collector" / "inpa_listing.html"


def test_run_collector_real_fixture(tmp_path: Path) -> None:
    """Verifica il flusso completo con contenuto HTML reale (senza rete)."""
    from unittest.mock import MagicMock

    from src.collector import run_collector

    fixture_bytes = _FIXTURE_HTML.read_bytes()

    mock_response = MagicMock()
    mock_response.content = fixture_bytes
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.raise_for_status.return_value = None

    sources_yaml = tmp_path / "sources.yaml"
    sources_yaml.write_text(
        "sources:\n"
        "  - nome: InPA\n"
        "    url: https://www.inpa.gov.it/bandi-di-concorso/\n"
        "    tipo: html\n"
        "    frequenza: daily\n"
    )
    db = tmp_path / "test.db"
    raw = tmp_path / "raw"

    with patch("src.collector.crawler.httpx.get", return_value=mock_response):
        result = run_collector(sources_yaml, db_path=db, raw_dir=raw)

    assert result.n_nuovi == 1
    assert result.status in ("completed", "completed_with_errors")

    saved = list(raw.glob("*.html"))
    assert len(saved) == 1
    assert saved[0].stat().st_size == len(fixture_bytes)
