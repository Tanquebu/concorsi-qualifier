"""Genera le schede Markdown per tutti i MatchResult in SQLite."""
import argparse
import json
import logging
import sqlite3
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

import src.env  # noqa: F401
from src.extractor.models import Bando
from src.matcher.models import CheckItem, MatchResult
from src.reporter import generate_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_COMPAT_CONFIG: dict[str, tuple[str, str]] = {
    "alta":          ("✅ ALTA",   "bold green"),
    "media":         ("🟡 MEDIA",  "bold yellow"),
    "bassa":         ("❌ BASSA",  "bold red"),
    "da_verificare": ("❓ DA_VER", "dim"),
}


def _compat_cell(compat: str) -> Text:
    label, style = _COMPAT_CONFIG.get(compat, (compat, ""))
    return Text(label, style=style)


def _load_pairs(db_path: Path) -> list[tuple[MatchResult, Bando]]:
    if not db_path.exists():
        return []
    pairs = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT mr.*, b.titolo as _titolo, b.ente as _ente, b.fonte as _fonte,
                      b.url as _url, b.parse_method as _parse_method,
                      b.scadenza as _scadenza, b.area_geografica as _area_geografica,
                      b.posti as _posti, b.requisiti_formali as _req,
                      b.materie_esame as _materie, b.documenti_richiesti as _docs,
                      b.extraction_confidence as _conf, b.tassa_concorso as _tassa,
                      b.link_candidatura as _link, b.categoria as _cat,
                      b.titolo_studio_richiesto as _titolo_studio,
                      b.testo_raw as _testo_raw, b.status as _bstatus,
                      b.created_at as _bcreated_at
               FROM match_results mr
               JOIN bandi b ON mr.bando_id = b.id
               WHERE mr.compatibilita IN ('alta', 'media')"""
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
            extraction_confidence=d["_conf"] or 0.0,
            testo_raw=d["_testo_raw"] or "",
        )
        pairs.append((mr, bando))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera schede Markdown (richiede Ollama attivo)"
    )
    parser.add_argument("--db", default="concorsi.db", type=Path, metavar="PATH")
    parser.add_argument("--output", default="data/processed", type=Path, metavar="DIR")
    args = parser.parse_args()

    pairs = _load_pairs(args.db)
    if not pairs:
        print("Nessun match_result trovato. Esegui prima matcher.")
        return

    console = Console()
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Esito", width=12)
    table.add_column("Ente", width=22, no_wrap=True)
    table.add_column("Titolo", width=48, no_wrap=True)
    table.add_column("Scadenza", width=10)
    table.add_column("File", width=22, style="dim", no_wrap=True)

    totale = len(pairs)
    errori = 0
    for i, (mr, bando) in enumerate(pairs, 1):
        try:
            path = generate_report(mr, bando, output_dir=args.output)
            scadenza = str(bando.scadenza) if bando.scadenza else "—"
            table.add_row(
                str(i),
                _compat_cell(mr.compatibilita),
                (bando.ente or "—")[:22],
                (bando.titolo or "—")[:48],
                scadenza,
                path.name,
            )
        except Exception as exc:
            errori += 1
            table.add_row(
                str(i),
                Text("ERR", style="bold red"),
                "—",
                (bando.id or "")[:48],
                "—",
                str(exc)[:22],
            )

    console.print(f"\n[bold]Schede da generare:[/bold] {totale}")
    console.print(table)
    if errori:
        console.print(f"[bold red]{errori} errori[/bold red]")
    console.print(f"[dim]Output → {args.output}/[/dim]\n")


if __name__ == "__main__":
    main()
