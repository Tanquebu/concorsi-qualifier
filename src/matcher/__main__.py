"""Legge tutti i Bando da SQLite e li matcha contro il profilo candidato."""
import argparse
import json
import logging
import sqlite3
from pathlib import Path

import yaml

from src.db import init_db
from src.extractor.models import Bando
from src.matcher import match
from src.matcher.models import CandidatoProfilo

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_ESITO_ICON = {"alta": "✅", "media": "🟡", "bassa": "❌", "da_verificare": "❓"}


def _load_bandi(
    db_path: Path,
    incremental: bool = False,
    bando_id: str | None = None,
) -> list[Bando]:
    if not db_path.exists():
        return []
    bandi = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if bando_id:
            sql = "SELECT * FROM bandi WHERE id = ?"
            params: tuple = (bando_id,)
        elif incremental:
            sql = """
                SELECT b.* FROM bandi b
                LEFT JOIN match_results mr ON b.id = mr.bando_id
                WHERE b.status = 'ok' AND mr.bando_id IS NULL
            """
            params = ()
        else:
            sql = "SELECT * FROM bandi WHERE status = 'ok'"
            params = ()
        rows = conn.execute(sql, params).fetchall()
    for row in rows:
        data = dict(row)
        for field in ("requisiti_formali", "materie_esame", "documenti_richiesti"):
            data[field] = json.loads(data[field]) if data.get(field) else []
        bandi.append(Bando(**data))
    return bandi


def main() -> None:
    parser = argparse.ArgumentParser(description="Matcha i bandi contro il profilo candidato")
    parser.add_argument(
        "profilo_config", nargs="?", default="config/profilo_candidato.yaml", type=Path
    )
    parser.add_argument("--db", default="concorsi.db", type=Path, metavar="PATH")
    parser.add_argument(
        "--incremental", action="store_true",
        help="Salta i bandi già matchati (più veloce nelle run quotidiane)",
    )
    parser.add_argument(
        "--bando-id", metavar="ID",
        help="Forza il (ri)match di un singolo bando per ID (ignora --incremental)",
    )
    args = parser.parse_args()

    with open(args.profilo_config, encoding="utf-8") as f:
        profilo = CandidatoProfilo(**yaml.safe_load(f))

    init_db(args.db)
    bandi = _load_bandi(args.db, incremental=args.incremental, bando_id=args.bando_id)
    if not bandi:
        if args.bando_id:
            print(f"Bando non trovato: {args.bando_id}")
        elif args.incremental:
            print("Nessun bando nuovo da matchare.")
        else:
            print("Nessun bando trovato in SQLite. Esegui prima il collector + extractor.")
        return

    totale = len(bandi)
    if args.bando_id:
        mode = f"singolo ({args.bando_id[:12]}…)"
    elif args.incremental:
        mode = "incrementale"
    else:
        mode = "completo"
    print(f"Profilo: {profilo.nome} | Bandi da analizzare: {totale} (modo {mode})\n")
    alta = media = bassa = da_ver = 0

    with sqlite3.connect(args.db) as conn:
        for i, bando in enumerate(bandi, 1):
            result = match(bando, profilo, db_path=args.db, conn=conn)
            icon = _ESITO_ICON[result.compatibilita]
            print(f"  [{i}/{totale}] {icon} [{result.compatibilita.upper():13}] {bando.titolo[:55]}")
            if result.compatibilita == "alta":
                alta += 1
            elif result.compatibilita == "media":
                media += 1
            elif result.compatibilita == "bassa":
                bassa += 1
            else:
                da_ver += 1

    print(f"\nRiepilogo: ✅ {alta} alta  🟡 {media} media  ❌ {bassa} bassa  ❓ {da_ver} da_ver")


if __name__ == "__main__":
    main()
