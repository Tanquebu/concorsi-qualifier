import json
import sqlite3
from pathlib import Path

from src.extractor.models import Bando
from src.matcher.models import CheckItem, MatchResult
from src.reporter.chain import generate_explanation
from src.reporter.renderer import render_scheda

_DEFAULT_DB = Path("concorsi.db")
_DEFAULT_OUTPUT = Path("data/processed")


def generate_report(
    match_result: MatchResult,
    bando: Bando,
    output_dir: Path = _DEFAULT_OUTPUT,
    db_path: Path = _DEFAULT_DB,
) -> Path:
    """Genera la scheda Markdown e aggiorna match_results.spiegazione in SQLite."""
    spiegazione = generate_explanation(match_result, bando)
    _, dest = render_scheda(match_result, bando, spiegazione, output_dir)
    _persist_spiegazione(match_result.bando_id, str(spiegazione.get("spiegazione", "")), db_path)
    return dest


def _persist_spiegazione(bando_id: str, spiegazione: str, db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE match_results SET spiegazione = ? WHERE bando_id = ?",
            (spiegazione, bando_id),
        )


def reprocess_bando(
    bando_id: str,
    output_dir: Path = _DEFAULT_OUTPUT,
    db_path: Path = _DEFAULT_DB,
) -> dict[str, object]:
    """Carica match_result + bando dal DB, chiama Ollama, persiste e ritorna la spiegazione."""
    if not db_path.exists():
        raise ValueError(f"DB non trovato: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT mr.*, b.titolo as _titolo, b.ente as _ente, b.fonte as _fonte,
                      b.url as _url, b.parse_method as _parse_method,
                      b.scadenza as _scadenza, b.area_geografica as _area_geografica,
                      b.posti as _posti, b.requisiti_formali as _req,
                      b.materie_esame as _materie, b.documenti_richiesti as _docs,
                      b.extraction_confidence as _conf, b.tassa_concorso as _tassa,
                      b.link_candidatura as _link, b.categoria as _cat,
                      b.titolo_studio_richiesto as _titolo_studio,
                      b.testo_raw as _testo_raw
               FROM match_results mr
               JOIN bandi b ON mr.bando_id = b.id
               WHERE mr.bando_id = ?""",
            (bando_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"Nessun match_result per bando_id={bando_id}")

    d = dict(row)
    mr = MatchResult(
        id=d["id"],
        bando_id=d["bando_id"],
        profilo_nome=d["profilo_nome"],
        compatibilita=d["compatibilita"],
        checklist=[CheckItem(**c) for c in json.loads(d["checklist"])],
        da_verificare=json.loads(d["da_verificare"]),
        spiegazione=d["spiegazione"] or "",
        disclaimer=d["disclaimer"],
    )
    bando = Bando(
        id=d["bando_id"],
        fonte=d["_fonte"],
        url=d["_url"],
        titolo=d["_titolo"] or "",
        ente=d["_ente"] or "",
        parse_method=d["_parse_method"],
        scadenza=d["_scadenza"],
        area_geografica=d["_area_geografica"],
        posti=d["_posti"],
        categoria=d["_cat"],
        titolo_studio_richiesto=d["_titolo_studio"],
        requisiti_formali=json.loads(d["_req"]) if d["_req"] else [],
        materie_esame=json.loads(d["_materie"]) if d["_materie"] else [],
        documenti_richiesti=json.loads(d["_docs"]) if d["_docs"] else [],
        tassa_concorso=d["_tassa"],
        link_candidatura=d["_link"],
        extraction_confidence=d["_conf"] or 0.0,
        testo_raw=d["_testo_raw"] or "",
    )

    explanation = generate_explanation(mr, bando)
    _persist_spiegazione(bando_id, str(explanation.get("spiegazione", "")), db_path)
    render_scheda(mr, bando, explanation, output_dir)
    return explanation


__all__ = ["generate_report", "reprocess_bando"]
