#!/usr/bin/env python3
"""Estrae tutti i bandi raw non ancora presenti nel DB."""
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent / ".env")

from src.extractor import extract  # noqa: E402
from src.parser.fallback_chain import run_fallback_chain  # noqa: E402


def extract_one(html_path: Path) -> tuple[str, bool, str]:
    bando_id = html_path.stem
    meta_path = html_path.with_suffix(".meta.json")
    try:
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        parsed = run_fallback_chain(html_path)
        if not parsed.testo:
            return bando_id, False, "testo vuoto"
        extract(
            parsed.testo,
            parsed.parse_method,
            url=meta.get("url", ""),
            fonte=meta.get("fonte", ""),
            bando_id=bando_id,
        )
        has_pdf = "--- ALLEGATO PDF ---" in parsed.testo
        return bando_id, True, f"ok pdf={has_pdf}"
    except Exception as e:
        return bando_id, False, str(e)[:80]


def main() -> None:
    conn = sqlite3.connect("concorsi.db")
    in_db = {r[0] for r in conn.execute("SELECT id FROM bandi").fetchall()}
    conn.close()

    da_estrarre = [
        f for f in sorted(Path("data/raw").glob("*.html"))
        if f.stem not in in_db
    ]
    totale = len(da_estrarre)
    print(f"Da estrarre: {totale}", flush=True)

    ok = ko = 0
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(extract_one, p): p for p in da_estrarre}
        for i, fut in enumerate(as_completed(futures), 1):
            _, success, msg = fut.result()
            if success:
                ok += 1
            else:
                ko += 1
                if ko <= 20:
                    print(f"  KO [{i}/{totale}] {msg}", flush=True)
            if i % 50 == 0 or i == totale:
                print(f"  [{i}/{totale}] ok={ok} ko={ko}", flush=True)

    print(f"\nCompletato: {ok} OK, {ko} KO su {totale}", flush=True)


if __name__ == "__main__":
    main()
