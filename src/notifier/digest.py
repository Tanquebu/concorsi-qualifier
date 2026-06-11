from datetime import date, timedelta

from src.extractor.models import Bando
from src.matcher.models import MatchResult

_COMPATIBILITA_MINIMA = {"alta", "media"}


def filter_bandi(
    results: list[tuple[Bando, MatchResult]],
    days_ahead: int = 30,
) -> list[tuple[Bando, MatchResult]]:
    """Restituisce solo i bandi con compatibilità ≥ media e scadenza entro days_ahead giorni."""
    cutoff = date.today() + timedelta(days=days_ahead)
    out = []
    for bando, match in results:
        if match.compatibilita not in _COMPATIBILITA_MINIMA:
            continue
        if bando.scadenza is None or bando.scadenza > cutoff:
            continue
        if bando.scadenza < date.today():
            continue
        out.append((bando, match))
    return out


def build_digest_payload(
    filtered: list[tuple[Bando, MatchResult]],
) -> dict[str, object]:
    """Costruisce il payload per il webhook con lista bandi, HTML e plain text."""
    if not filtered:
        return {"bandi": [], "html": "", "plain_text": ""}

    plain_lines: list[str] = ["Digest bandi di concorso\n"]
    html_parts: list[str] = ["<h1>Digest bandi di concorso</h1><ul>"]

    items: list[dict[str, object]] = []
    for bando, match in filtered:
        item: dict[str, object] = {
            "id": bando.id,
            "titolo": bando.titolo,
            "ente": bando.ente,
            "scadenza": str(bando.scadenza) if bando.scadenza else "n.d.",
            "compatibilita": match.compatibilita,
            "url": bando.url,
        }
        items.append(item)

        plain_lines.append(
            f"- [{match.compatibilita.upper()}] {bando.titolo} — {bando.ente}"
            f" | scadenza: {item['scadenza']} | {bando.url}"
        )
        html_parts.append(
            f"<li><strong>[{match.compatibilita.upper()}]</strong> "
            f"<a href='{bando.url}'>{bando.titolo}</a> — {bando.ente}"
            f" | scadenza: {item['scadenza']}</li>"
        )

    html_parts.append("</ul>")
    return {
        "bandi": items,
        "html": "\n".join(html_parts),
        "plain_text": "\n".join(plain_lines),
    }
