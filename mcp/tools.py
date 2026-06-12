import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db import init_db  # noqa: E402 — solo stdlib (sqlite3 + pathlib)

DB_PATH = PROJECT_ROOT / "concorsi.db"

# Python usato per lanciare i sottoprocessi della pipeline (deve avere le dipendenze del progetto)
PIPELINE_PYTHON = os.environ.get("PIPELINE_PYTHON", "/usr/bin/python3")

# Ordine di compatibilità decrescente (usato per il filtro "minima")
_COMPAT_ORDER = ["alta", "media", "bassa", "da_verificare"]


def _ensure_db() -> Path:
    """Garantisce che il DB esista con schema corretto. Idempotente."""
    init_db(DB_PATH)
    return DB_PATH


def get_bandi(
    compatibilita: str | None = None,
    scadenza_entro_giorni: int | None = None,
    limit: int = 20,
) -> dict:
    """Lista bandi, esclude testo_raw per non appesantire la risposta."""
    db = _ensure_db()

    if compatibilita:
        join = "JOIN match_results mr ON b.id = mr.bando_id"
        compat_cond = "AND mr.compatibilita = ?"
        compat_params: list = [compatibilita]
        extra_cols = ", mr.compatibilita, mr.id as match_id"
    else:
        join = "LEFT JOIN match_results mr ON b.id = mr.bando_id"
        compat_cond = ""
        compat_params = []
        extra_cols = ", mr.compatibilita, mr.id as match_id"

    date_cond = ""
    date_params: list = []
    if scadenza_entro_giorni is not None:
        deadline = (date.today() + timedelta(days=scadenza_entro_giorni)).isoformat()
        date_cond = "AND b.scadenza IS NOT NULL AND b.scadenza <= ?"
        date_params = [deadline]

    sql = f"""
        SELECT b.id, b.fonte, b.url, b.titolo, b.ente, b.categoria,
               b.area_geografica, b.posti, b.scadenza, b.titolo_studio_richiesto,
               b.tassa_concorso, b.extraction_confidence, b.parse_method,
               b.created_at{extra_cols}
        FROM bandi b
        {join}
        WHERE b.status = 'ok'
        {compat_cond}
        {date_cond}
        ORDER BY b.scadenza ASC NULLS LAST
        LIMIT ?
    """
    params = compat_params + date_params + [limit]

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()

    result = [dict(r) for r in rows]
    nota = (
        None
        if result
        else "Nessun bando trovato. Esegui collector + extractor per popolare il database."
    )
    return {"bandi": result, "count": len(result), "_nota": nota}


def get_match_results(
    compatibilita_minima: str | None = None,
    bando_id: str | None = None,
    limit: int = 20,
) -> dict:
    """Risultati di matching con checklist e da_verificare già parsati da JSON."""
    db = _ensure_db()

    conditions: list[str] = []
    params: list = []

    if compatibilita_minima and compatibilita_minima in _COMPAT_ORDER:
        idx = _COMPAT_ORDER.index(compatibilita_minima)
        levels = _COMPAT_ORDER[: idx + 1]
        placeholders = ",".join("?" * len(levels))
        conditions.append(f"mr.compatibilita IN ({placeholders})")
        params.extend(levels)

    if bando_id:
        conditions.append("mr.bando_id = ?")
        params.append(bando_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT mr.id, mr.bando_id, mr.profilo_nome, mr.compatibilita,
               mr.checklist, mr.da_verificare, mr.spiegazione, mr.disclaimer,
               mr.created_at,
               b.titolo AS bando_titolo, b.ente AS bando_ente,
               b.scadenza AS bando_scadenza
        FROM match_results mr
        JOIN bandi b ON mr.bando_id = b.id
        {where}
        ORDER BY mr.created_at DESC
        LIMIT ?
    """
    params.append(limit)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        for field in ("checklist", "da_verificare"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        result.append(d)

    nota = (
        None
        if result
        else "Nessun match result trovato. Esegui il matcher per generare i risultati."
    )
    return {"match_results": result, "count": len(result), "_nota": nota}


def get_collector_runs(limit: int = 10) -> dict:
    """Storico run del collector con errori già parsati da JSON."""
    db = _ensure_db()

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM collector_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        if d.get("errori"):
            try:
                d["errori"] = json.loads(d["errori"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)

    nota = (
        None
        if result
        else "Nessun run del collector trovato. Esegui il collector per registrare le run."
    )
    return {"collector_runs": result, "count": len(result), "_nota": nota}


async def trigger_pipeline(
    module: str,
    extra_args: list[str] | None = None,
) -> dict:
    """
    Lancia un modulo della pipeline come subprocess.
    Aspetta fino a 10 secondi: se finisce restituisce l'output completo,
    altrimenti (modulo lento) restituisce PID + path del log in background.
    """
    valid = {"collector", "extractor", "matcher", "reporter", "notifier"}
    if module not in valid:
        return {
            "error": f"Modulo non valido: {module!r}. Accettati: {', '.join(sorted(valid))}"
        }

    timestamp = int(time.time())
    log_path = Path(tempfile.gettempdir()) / f"concorsi_{module}_{timestamp}.log"
    cmd = [PIPELINE_PYTHON, "-m", f"src.{module}"] + (extra_args or [])

    log_fh = open(log_path, "w")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=log_fh,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
        )
    except Exception as exc:
        log_fh.close()
        return {"error": f"Impossibile avviare {module!r}: {exc}"}

    # Chiude in parent — il subprocess mantiene il suo fd
    log_fh.close()

    try:
        await asyncio.wait_for(proc.wait(), timeout=10.0)
        output = log_path.read_text(encoding="utf-8", errors="replace")
        return {
            "status": "completed",
            "returncode": proc.returncode,
            "module": module,
            "output": output,
            "log": str(log_path),
        }
    except TimeoutError:
        partial = (
            log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        )
        return {
            "status": "running",
            "pid": proc.pid,
            "module": module,
            "log": str(log_path),
            "output_partial": partial,
            "message": (
                f"Modulo lento in esecuzione in background (PID {proc.pid}). "
                f"Monitora con: tail -f {log_path}"
            ),
        }
