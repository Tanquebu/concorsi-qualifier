"""Filtra i bandi rilevanti e invia il digest al webhook."""
import argparse
import json
import logging
import sqlite3
from pathlib import Path

from src.extractor.models import Bando
from src.matcher.models import CheckItem, MatchResult
from src.notifier import filter_bandi, send_digest
from src.notifier.digest import build_digest_payload

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _load_pairs(db_path: Path) -> list[tuple[Bando, MatchResult]]:
    if not db_path.exists():
        return []
    pairs = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT mr.*, b.titolo as _titolo, b.ente as _ente, b.fonte as _fonte,
                      b.url as _url, b.parse_method as _pm, b.scadenza as _scadenza,
                      b.area_geografica as _area, b.posti as _posti,
                      b.requisiti_formali as _req, b.materie_esame as _mat,
                      b.documenti_richiesti as _docs, b.extraction_confidence as _conf,
                      b.testo_raw as _testo, b.status as _bstatus,
                      b.created_at as _bca, b.categoria as _cat,
                      b.titolo_studio_richiesto as _ts
               FROM match_results mr JOIN bandi b ON mr.bando_id = b.id"""
        ).fetchall()
    for row in rows:
        d = dict(row)
        mr = MatchResult(
            id=d["id"],
            bando_id=d["bando_id"],
            profilo_nome=d["profilo_nome"],
            compatibilita=d["compatibilita"],
            checklist=[CheckItem(**c) for c in json.loads(d["checklist"])],
            da_verificare=json.loads(d["da_verificare"]),
        )
        bando = Bando(
            id=d["bando_id"],
            fonte=d["_fonte"],
            url=d["_url"],
            titolo=d["_titolo"] or "",
            ente=d["_ente"] or "",
            parse_method=d["_pm"],
            scadenza=d["_scadenza"],
            area_geografica=d["_area"],
            posti=d["_posti"],
            categoria=d["_cat"],
            titolo_studio_richiesto=d["_ts"],
            requisiti_formali=json.loads(d["_req"]) if d["_req"] else [],
            materie_esame=json.loads(d["_mat"]) if d["_mat"] else [],
            documenti_richiesti=json.loads(d["_docs"]) if d["_docs"] else [],
            extraction_confidence=d["_conf"] or 0.0,
            testo_raw=d["_testo"] or "",
        )
        pairs.append((bando, mr))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Invia digest bandi rilevanti via webhook")
    parser.add_argument("--db", default="concorsi.db", type=Path, metavar="PATH")
    parser.add_argument(
        "--days", default=30, type=int, help="Giorni alla scadenza (default 30)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostra il payload senza inviarlo"
    )
    args = parser.parse_args()

    pairs = _load_pairs(args.db)
    filtered = filter_bandi(pairs, days_ahead=args.days)

    if not filtered:
        print("Nessun bando da notificare (compatibilità < media o scadenza fuori finestra).")
        return

    print(f"Bandi da notificare: {len(filtered)}")
    for bando, mr in filtered:
        print(f"  [{mr.compatibilita.upper()}] {bando.titolo[:60]} — scadenza {bando.scadenza}")

    if args.dry_run:
        payload = build_digest_payload(filtered)
        print(f"\n--- Payload (dry-run) ---\n{payload['plain_text']}")
    else:
        send_digest(pairs, days_ahead=args.days)


if __name__ == "__main__":
    main()
