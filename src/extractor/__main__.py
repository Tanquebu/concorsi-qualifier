"""Legge i file in data/raw/, li parsa e li estrae in Bando (SQLite)."""
import argparse
import json
import logging
from pathlib import Path

from src.extractor import extract
from src.parser import parse

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parsa e struttura i file raw in Bando (richiede OPENROUTER_API_KEY)"
    )
    parser.add_argument("--raw", default="data/raw", type=Path, metavar="DIR")
    parser.add_argument("--db", default="concorsi.db", type=Path, metavar="PATH")
    args = parser.parse_args()

    meta_files = sorted(args.raw.glob("*.meta.json"))
    if not meta_files:
        print(f"Nessun file .meta.json trovato in {args.raw}")
        return

    print(f"File da processare: {len(meta_files)}")
    ok = err = skip = 0

    for meta_path in meta_files:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        file_hash = meta_path.stem.removesuffix(".meta")
        raw_file = args.raw / f"{file_hash}.{meta['ext']}"

        if not raw_file.exists():
            print(f"  SKIP {file_hash} — file raw mancante")
            skip += 1
            continue

        try:
            parse_result = parse(raw_file)
            if not parse_result.testo.strip():
                print(f"  SKIP {file_hash} — testo vuoto ({parse_result.parse_method})")
                skip += 1
                continue

            bando = extract(
                parse_result.testo,
                parse_result.parse_method,
                url=meta["url"],
                fonte=meta["fonte"],
                bando_id=file_hash,
                data_pubblicazione=meta.get("published", ""),
                db_path=args.db,
            )
            print(f"  OK   {file_hash} — {bando.titolo[:60]!r}")
            ok += 1
        except Exception as exc:
            print(f"  ERR  {file_hash} — {exc}")
            err += 1

    print(f"\nEstrazione: {ok} ok, {skip} saltati, {err} errori")


if __name__ == "__main__":
    main()
