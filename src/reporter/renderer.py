from pathlib import Path

from src.extractor.models import Bando
from src.matcher.models import DISCLAIMER, MatchResult

_ESITO_EMOJI = {"ok": "✅", "warning": "⚠️", "fail": "❌", "unknown": "❓"}

_DEFAULT_OUTPUT = Path("data/processed")


def render_scheda(
    match_result: MatchResult,
    bando: Bando,
    spiegazione: dict[str, object],
    output_dir: Path = _DEFAULT_OUTPUT,
) -> tuple[str, Path]:
    """Assembla la scheda Markdown e la salva in output_dir/{bando.id}.md."""
    lines: list[str] = []

    lines += [f"# {bando.titolo}", ""]

    lines += ["## Riepilogo"]
    lines += [
        f"- **Ente:** {bando.ente}",
        f"- **Posti:** {bando.posti or 'non specificato'}",
        f"- **Scadenza:** {bando.scadenza or 'non specificata'}",
        f"- **Area geografica:** {bando.area_geografica or 'non specificata'}",
        f"- **Fonte:** [{bando.fonte}]({bando.url})",
        "",
    ]

    lines += ["## Compatibilità", f"**Esito:** {match_result.compatibilita.upper()}", ""]

    lines += ["### Checklist requisiti"]
    for item in match_result.checklist:
        emoji = _ESITO_EMOJI.get(item.esito, "?")
        nota = f" — {item.nota}" if item.nota else ""
        lines.append(f"- {emoji} **{item.requisito}**: {item.esito}{nota}")
    lines.append("")

    testo_spiegazione = str(spiegazione.get("spiegazione", ""))
    if testo_spiegazione:
        lines += ["## Analisi", testo_spiegazione, ""]

    azioni = spiegazione.get("azioni_consigliate", [])
    if isinstance(azioni, list) and azioni:
        lines += ["## Azioni consigliate"]
        lines += [f"- {a}" for a in azioni]
        lines.append("")

    if match_result.da_verificare:
        lines += ["## Punti da verificare manualmente"]
        lines += [f"- {p}" for p in match_result.da_verificare]
        lines.append("")

    if bando.requisiti_formali:
        lines += ["## Requisiti formali"]
        lines += [f"- {r}" for r in bando.requisiti_formali]
        lines.append("")

    if bando.materie_esame:
        lines += ["## Materie d'esame"]
        lines += [f"- {m}" for m in bando.materie_esame]
        lines.append("")

    lines += ["---", f"*{DISCLAIMER}*"]

    content = "\n".join(lines)
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{bando.id}.md"
    dest.write_text(content, encoding="utf-8")
    return content, dest
