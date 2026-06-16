#!/usr/bin/env python3
"""Ri-estrae i bandi che hanno un allegato PDF ma testo_raw senza contenuto PDF."""
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent / ".env")

from src.extractor import extract  # noqa: E402
from src.parser.fallback_chain import run_fallback_chain  # noqa: E402


def reextract_one(bando_id: str, url: str, fonte: str) -> tuple[str, bool, str]:
    html_path = Path(f"data/raw/{bando_id}.html")
    if not html_path.exists():
        return bando_id, False, "file HTML non trovato"
    try:
        parsed = run_fallback_chain(html_path)
        if not parsed or not parsed.testo:
            return bando_id, False, "parsing fallito"
        extract(
            parsed.testo,
            parsed.parse_method,
            url=url,
            fonte=fonte,
            bando_id=bando_id,
        )
        has_pdf = "--- ALLEGATO PDF ---" in parsed.testo
        return bando_id, True, f"pdf_incluso={has_pdf}"
    except Exception as e:
        return bando_id, False, str(e)[:80]


def main() -> None:
    conn = sqlite3.connect("concorsi.db")
    rows = conn.execute("SELECT id, url, fonte, testo_raw FROM bandi").fetchall()
    conn.close()

    da_estrarre = []
    for bando_id, url, fonte, testo_raw in rows:
        allegato = Path(f"data/raw/{bando_id}.allegato.pdf")
        if allegato.exists() and "--- ALLEGATO PDF ---" not in (testo_raw or ""):
            da_estrarre.append((bando_id, url or "", fonte or ""))

    totale = len(da_estrarre)
    print(f"Bandi da ri-estrarre: {totale}", flush=True)

    ok = 0
    ko = 0
    ko_pdf = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(reextract_one, bid, url, fonte): bid
            for bid, url, fonte in da_estrarre
        }
        for i, fut in enumerate(as_completed(futures), 1):
            bando_id, success, msg = fut.result()
            if success:
                ok += 1
                if "pdf_incluso=False" in msg:
                    ko_pdf += 1
            else:
                ko += 1
                print(f"  KO [{i}/{totale}] {bando_id[:16]} — {msg}", flush=True)
            if i % 10 == 0 or i == totale:
                print(f"  [{i}/{totale}] ok={ok} ko={ko} (no_pdf={ko_pdf})", flush=True)

    print(f"\nCompletato: {ok} OK (di cui {ko_pdf} senza PDF), {ko} KO su {totale}", flush=True)


if __name__ == "__main__":
    main()
