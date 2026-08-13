"""Ledger dei bandi che non superano l'estrazione.

Senza questo, ogni run ritenta all'infinito i documenti rotti in modo deterministico:
13 bandi al giorno bruciavano chiamate OpenRouter per tornare sempre lo stesso errore.
Il contatore `attempts` cresce solo sugli errori NON transitori, cosi' un provider
sovraccarico (429) non consuma i tentativi di un documento che sarebbe estraibile.
"""
import os
import sqlite3
from datetime import datetime

from src.extractor.chain import is_transient_error

# Tentativi non transitori dopo i quali si smette di ritentare. Override con
# EXTRACTION_MAX_ATTEMPTS; 0 disattiva del tutto il blocco.
MAX_ATTEMPTS = int(os.environ.get("EXTRACTION_MAX_ATTEMPTS", "3"))


def blocked_ids(conn: sqlite3.Connection) -> set[str]:
    """Bandi che hanno esaurito i tentativi e vanno saltati."""
    if MAX_ATTEMPTS <= 0:
        return set()
    rows = conn.execute(
        "SELECT bando_id FROM extraction_failures WHERE attempts >= ?", (MAX_ATTEMPTS,)
    )
    return {row[0] for row in rows}


def record_failure(conn: sqlite3.Connection, bando_id: str, exc: BaseException) -> bool:
    """Registra un fallimento. Restituisce True se e' stato classificato come transitorio."""
    transient = is_transient_error(exc)
    cause = exc.__cause__ or exc.__context__ or exc
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO extraction_failures
               (bando_id, attempts, transient_count, last_error, last_transient,
                first_seen_at, last_attempt_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(bando_id) DO UPDATE SET
               attempts        = attempts + excluded.attempts,
               transient_count = transient_count + excluded.transient_count,
               last_error      = excluded.last_error,
               last_transient  = excluded.last_transient,
               last_attempt_at = excluded.last_attempt_at""",
        (
            bando_id,
            0 if transient else 1,
            1 if transient else 0,
            f"{type(cause).__name__}: {cause}"[:2000],
            1 if transient else 0,
            now,
            now,
        ),
    )
    conn.commit()
    return transient


def clear_failure(conn: sqlite3.Connection, bando_id: str) -> None:
    """Un'estrazione riuscita azzera la storia del bando."""
    conn.execute("DELETE FROM extraction_failures WHERE bando_id = ?", (bando_id,))
    conn.commit()
