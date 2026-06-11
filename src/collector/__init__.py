import uuid
from datetime import datetime
from pathlib import Path

import yaml

from src.collector.crawler import download_source
from src.collector.db import CollectorRun, get_known_hashes, insert_run, update_run_status
from src.db import init_db

_DEFAULT_DB = Path("concorsi.db")
_DEFAULT_RAW = Path("data/raw")


def run_collector(
    sources_config: Path,
    db_path: Path = _DEFAULT_DB,
    raw_dir: Path = _DEFAULT_RAW,
) -> CollectorRun:
    """Scarica bandi da tutte le fonti configurate. Restituisce il CollectorRun della sessione."""
    init_db(db_path)

    with open(sources_config) as f:
        config = yaml.safe_load(f)
    sources: list[dict[str, str]] = config.get("sources", [])

    run = CollectorRun(
        id=str(uuid.uuid4()),
        fonte="all",
        started_at=datetime.utcnow().isoformat(),
    )
    insert_run(db_path, run)

    errori: list[str] = []
    n_trovati = 0
    n_nuovi = 0

    for source in sources:
        fonte_nome: str = source.get("nome", source["url"])
        known = get_known_hashes(db_path, fonte_nome)
        try:
            nuovi = download_source(source, raw_dir, known)
            n_trovati += 1
            n_nuovi += len(nuovi)
        except Exception as exc:
            errori.append(f"{fonte_nome}: {exc}")

    n_duplicati = n_trovati - n_nuovi
    completed_at = datetime.utcnow().isoformat()
    status = "completed" if not errori else "completed_with_errors"

    update_run_status(
        db_path,
        run.id,
        status=status,
        errori=errori,
        completed_at=completed_at,
        n_trovati=n_trovati,
        n_nuovi=n_nuovi,
        n_duplicati=max(n_duplicati, 0),
    )

    run.status = status
    run.completed_at = completed_at
    run.n_trovati = n_trovati
    run.n_nuovi = n_nuovi
    run.n_duplicati = max(n_duplicati, 0)
    run.errori = errori
    return run


__all__ = ["run_collector", "CollectorRun"]
