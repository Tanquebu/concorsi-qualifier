import hashlib
import json
import sqlite3
from pathlib import Path

from src.db import init_db
from src.extractor.chain import run_extraction
from src.extractor.models import Bando

_DEFAULT_DB = Path("concorsi.db")


def extract(
    testo: str,
    parse_method: str,
    *,
    url: str = "",
    fonte: str = "",
    bando_id: str = "",
    data_pubblicazione: str = "",
    db_path: Path = _DEFAULT_DB,
    conn: sqlite3.Connection | None = None,
) -> Bando:
    """Estrae un Bando dal testo e lo persiste in SQLite."""
    data, confidence = run_extraction(testo, data_pubblicazione=data_pubblicazione)

    data["titolo"] = data.get("titolo") or ""
    data["ente"] = data.get("ente") or ""
    data["requisiti_formali"] = data.get("requisiti_formali") or []
    data["materie_esame"] = data.get("materie_esame") or []
    data["documenti_richiesti"] = data.get("documenti_richiesti") or []

    data["id"] = bando_id or hashlib.sha256(url.encode()).hexdigest()
    data["fonte"] = fonte
    data["url"] = url
    data["testo_raw"] = testo
    data["parse_method"] = parse_method
    data["extraction_confidence"] = confidence

    bando = Bando(**data)
    _persist_bando(bando, db_path, conn=conn)
    return bando


def _persist_bando(
    bando: Bando,
    db_path: Path,
    conn: sqlite3.Connection | None = None,
) -> None:
    _own_conn = conn is None
    if _own_conn:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO bandi
               (id, fonte, url, titolo, ente, categoria, area_geografica, posti, scadenza,
                titolo_studio_richiesto, requisiti_formali, materie_esame, tassa_concorso,
                link_candidatura, documenti_richiesti, testo_raw, parse_method,
                extraction_confidence, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                bando.id,
                bando.fonte,
                bando.url,
                bando.titolo,
                bando.ente,
                bando.categoria,
                bando.area_geografica,
                bando.posti,
                str(bando.scadenza) if bando.scadenza else None,
                bando.titolo_studio_richiesto,
                json.dumps(bando.requisiti_formali),
                json.dumps(bando.materie_esame),
                bando.tassa_concorso,
                bando.link_candidatura,
                json.dumps(bando.documenti_richiesti),
                bando.testo_raw,
                bando.parse_method,
                bando.extraction_confidence,
                bando.status,
                bando.created_at.isoformat(),
            ),
        )
        conn.commit()
    finally:
        if _own_conn:
            conn.close()


__all__ = ["extract", "run_extraction", "Bando"]
