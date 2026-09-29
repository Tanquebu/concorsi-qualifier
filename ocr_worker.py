#!/usr/bin/env python3
"""Processa la coda OCR (data/ocr_queue.txt) sequenzialmente, uno alla volta."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import sqlite3  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent / ".env")

from src.extractor import extract  # noqa: E402
from src.parser.pdf_ocr import extract_text_ocr  # noqa: E402

_QUEUE = Path("data/ocr_queue.txt")
_DB = Path("concorsi.db")
_DEFERRED_QUEUE = Path("data/ocr_waiting_for_db.txt")


def _get_bando_meta(bando_id: str) -> tuple[str, str] | None:
    conn = sqlite3.connect(f"{_DB.resolve().as_uri()}?mode=ro", uri=True)
    row = conn.execute("SELECT url, fonte FROM bandi WHERE id=?", (bando_id,)).fetchone()
    conn.close()
    return (row[0] or "", row[1] or "") if row else None


def process_one(bando_id: str) -> tuple[bool, str]:
    meta = _get_bando_meta(bando_id)
    if not meta:
        return False, "bando non in DB"
    url, fonte = meta

    allegato = Path(f"data/raw/{bando_id}.allegato.pdf")
    if not allegato.exists():
        return False, "allegato non trovato"

    pdf_text = extract_text_ocr(allegato)
    if not pdf_text:
        return False, "OCR: testo vuoto"

    html_path = Path(f"data/raw/{bando_id}.html")
    if not html_path.exists():
        return False, "HTML non trovato"

    try:
        from bs4 import BeautifulSoup
        html = html_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        base_text = soup.get_text(separator="\n").strip()
    except Exception as e:
        return False, f"parse HTML: {e}"

    testo = base_text + "\n\n--- ALLEGATO PDF (OCR) ---\n\n" + pdf_text

    try:
        extract(testo, "html", url=url, fonte=fonte, bando_id=bando_id)
        return True, f"OCR ok, testo={len(pdf_text)} chars"
    except Exception as e:
        return False, f"extractor: {e}"


def remove_from_queue(bando_id: str) -> None:
    if not _QUEUE.exists():
        return
    lines = [line for line in _QUEUE.read_text().splitlines() if line != bando_id]
    _QUEUE.write_text("\n".join(lines) + ("\n" if lines else ""))


def reconcile_queue() -> tuple[int, int]:
    """Sospende gli ID assenti dal DB e riattiva quelli nel frattempo inseriti.

    Eseguire senza altri worker/scrittori della coda attivi (pipeline sequenziale).
    Scrive prima la coda di attesa: se interrotto, gli ID restano recuperabili.
    """
    def read_ids(path: Path) -> list[str]:
        if not path.exists():
            return []
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]

    ids = list(dict.fromkeys(read_ids(_QUEUE) + read_ids(_DEFERRED_QUEUE)))
    active, deferred = [], []
    with sqlite3.connect(f"{_DB.resolve().as_uri()}?mode=ro", uri=True) as conn:
        for bando_id in ids:
            target = active if conn.execute(
                "SELECT 1 FROM bandi WHERE id=?", (bando_id,)
            ).fetchone() else deferred
            target.append(bando_id)
    for path, entries in (
        (_DEFERRED_QUEUE, ids), (_QUEUE, active), (_DEFERRED_QUEUE, deferred)
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(entry + "\n" for entry in entries))
        temporary.replace(path)
    return len(active), len(deferred)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconcile-only", action="store_true",
                        help="Riordina le code senza eseguire OCR o chiamate LLM")
    args = parser.parse_args()
    active, deferred = reconcile_queue()
    print(f"Code OCR: {active} attivi, {deferred} in attesa del record DB", flush=True)
    if args.reconcile_only:
        return
    if not _QUEUE.exists() or not _QUEUE.read_text().strip():
        print("Coda OCR vuota.", flush=True)
        return

    bandi = [line.strip() for line in _QUEUE.read_text().splitlines() if line.strip()]
    print(f"Coda OCR: {len(bandi)} bandi da processare (sequenziale)", flush=True)

    ok = ko = 0
    for i, bando_id in enumerate(bandi, 1):
        print(f"[{i}/{len(bandi)}] {bando_id[:16]}...", end=" ", flush=True)
        success, msg = process_one(bando_id)
        if success:
            ok += 1
            remove_from_queue(bando_id)
            print(f"OK — {msg}", flush=True)
        else:
            ko += 1
            print(f"KO — {msg}", flush=True)

    print(f"\nCompletato: {ok} OK, {ko} KO", flush=True)


if __name__ == "__main__":
    main()
