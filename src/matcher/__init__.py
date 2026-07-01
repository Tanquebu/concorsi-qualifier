import json
import sqlite3
from pathlib import Path

from src.db import init_db
from src.extractor.models import Bando
from src.matcher.matcher import match as _match
from src.matcher.models import CandidatoProfilo, MatchResult

_DEFAULT_DB = Path("concorsi.db")


def match(
    bando: Bando,
    profilo: CandidatoProfilo,
    db_path: Path = _DEFAULT_DB,
    conn: sqlite3.Connection | None = None,
) -> MatchResult:
    """Esegue il match deterministico e persiste il MatchResult in SQLite."""
    result = _match(bando, profilo)
    _persist_match_result(result, db_path, conn=conn)
    return result


def _persist_match_result(
    mr: MatchResult,
    db_path: Path,
    conn: sqlite3.Connection | None = None,
) -> None:
    _own_conn = conn is None
    if _own_conn:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM match_results WHERE bando_id = ?", (mr.bando_id,))
        conn.execute(
            """INSERT INTO match_results
               (id, bando_id, profilo_nome, compatibilita, checklist,
                da_verificare, spiegazione, disclaimer, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                mr.id,
                mr.bando_id,
                mr.profilo_nome,
                mr.compatibilita,
                json.dumps([item.model_dump() for item in mr.checklist]),
                json.dumps(mr.da_verificare),
                mr.spiegazione,
                mr.disclaimer,
                mr.created_at.isoformat(),
            ),
        )
        conn.commit()
    finally:
        if _own_conn:
            conn.close()


__all__ = ["match", "MatchResult", "CandidatoProfilo"]
