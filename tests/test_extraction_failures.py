"""Troncamento per contesto e ledger dei fallimenti di estrazione."""
import sqlite3
from pathlib import Path

import pytest
from openai import RateLimitError

from src.db import init_db
from src.extractor.chain import _MAX_INPUT_CHARS, is_transient_error, truncate_for_context
from src.extractor.failures import blocked_ids, clear_failure, record_failure

# Errori reali osservati nella run del 13/08/2026.
_ERR_CONTESTO = (
    "Upstream error from Venice: This model's maximum context length is 128000 tokens. "
    "However, you requested 16384 output tokens and your prompt contains 135013 input tokens"
)
_ERR_429 = (
    "Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, "
    "'metadata': {'raw': 'mistralai/mistral-small-3.2-24b-instruct is temporarily "
    "rate-limited upstream', 'provider_error_code': 'engine_overloaded'}}}"
)


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "test.db"
    init_db(db)
    connection = sqlite3.connect(db)
    yield connection
    connection.close()


def _fallimento(messaggio: str) -> RuntimeError:
    """Riproduce la forma con cui la chain propaga l'errore: causa incatenata."""
    try:
        try:
            raise ValueError(messaggio)
        except ValueError as causa:
            raise RuntimeError("Estrazione fallita dopo tutti i tentativi") from causa
    except RuntimeError as exc:
        return exc


# --- troncamento ---

def test_testo_corto_non_viene_toccato() -> None:
    testo = "Bando di concorso " * 100
    assert truncate_for_context(testo) == testo


def test_testo_oltre_il_contesto_viene_troncato() -> None:
    testo = "x" * (_MAX_INPUT_CHARS + 50_000)
    result = truncate_for_context(testo)
    assert len(result) < len(testo)
    assert result.startswith("x" * 1000)
    assert "troncato" in result


# --- classificazione degli errori ---

def test_errore_di_contesto_non_e_transitorio() -> None:
    assert is_transient_error(_fallimento(_ERR_CONTESTO)) is False


def test_429_del_provider_e_transitorio() -> None:
    assert is_transient_error(_fallimento(_ERR_429)) is True


def test_riconosce_il_tipo_di_eccezione_oltre_al_messaggio() -> None:
    exc = RateLimitError.__new__(RateLimitError)
    Exception.__init__(exc, "Provider returned error")
    assert is_transient_error(exc) is True


def test_causa_nulla_non_e_transitoria() -> None:
    assert is_transient_error(None) is False


# --- ledger ---

def test_errore_di_documento_consuma_un_tentativo(conn: sqlite3.Connection) -> None:
    transient = record_failure(conn, "bando-1", _fallimento(_ERR_CONTESTO))
    assert transient is False
    row = conn.execute(
        "SELECT attempts, transient_count, last_error FROM extraction_failures"
    ).fetchone()
    assert row[0] == 1
    assert row[1] == 0
    assert "maximum context length" in row[2]


def test_429_non_consuma_tentativi(conn: sqlite3.Connection) -> None:
    for _ in range(5):
        assert record_failure(conn, "bando-1", _fallimento(_ERR_429)) is True
    row = conn.execute("SELECT attempts, transient_count FROM extraction_failures").fetchone()
    assert row[0] == 0
    assert row[1] == 5
    assert blocked_ids(conn) == set()


def test_blocco_dopo_i_tentativi_esauriti(conn: sqlite3.Connection) -> None:
    for _ in range(3):
        record_failure(conn, "bando-rotto", _fallimento(_ERR_CONTESTO))
    record_failure(conn, "bando-sfortunato", _fallimento(_ERR_429))
    assert blocked_ids(conn) == {"bando-rotto"}


def test_estrazione_riuscita_azzera_la_storia(conn: sqlite3.Connection) -> None:
    for _ in range(3):
        record_failure(conn, "bando-1", _fallimento(_ERR_CONTESTO))
    assert blocked_ids(conn) == {"bando-1"}
    clear_failure(conn, "bando-1")
    assert blocked_ids(conn) == set()
    assert conn.execute("SELECT count(*) FROM extraction_failures").fetchone()[0] == 0
