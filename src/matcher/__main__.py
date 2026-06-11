"""Legge tutti i Bando da SQLite e li matcha contro il profilo candidato."""
import argparse
import json
import logging
import sqlite3
from pathlib import Path

import yaml

from src.extractor.models import Bando
from src.matcher import match
from src.matcher.models import CandidatoProfilo

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_ESITO_ICON = {"alta": "✅", "media": "🟡", "bassa": "❌", "da_verificare": "❓"}


def _load_bandi(db_path: Path) -> list[Bando]:
    if not db_path.exists():
        return []
    bandi = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM bandi WHERE status = 'ok'").fetchall()
    for row in rows:
        data = dict(row)
        for field in ("requisiti_formali", "materie_esame", "documenti_richiesti"):
            if data.get(field):
                data[field] = json.loads(data[field])
        bandi.append(Bando(**data))
    return bandi


def main() -> None:
    parser = argparse.ArgumentParser(description="Matcha i bandi contro il profilo candidato")
    parser.add_argument(
        "profilo_config", nargs="?", default="config/profilo_candidato.yaml", type=Path
    )
    parser.add_argument("--db", default="concorsi.db", type=Path, metavar="PATH")
    args = parser.parse_args()

    with open(args.profilo_config, encoding="utf-8") as f:
        profilo = CandidatoProfilo(**yaml.safe_load(f))

    bandi = _load_bandi(args.db)
    if not bandi:
        print("Nessun bando trovato in SQLite. Esegui prima il collector + extractor.")
        return

    print(f"Profilo: {profilo.nome} | Bandi da analizzare: {len(bandi)}\n")
    alta = media = bassa = da_ver = 0

    for bando in bandi:
        result = match(bando, profilo, db_path=args.db)
        icon = _ESITO_ICON[result.compatibilita]
        print(f"  {icon} [{result.compatibilita.upper():13}] {bando.titolo[:55]}")
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
