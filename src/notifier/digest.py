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


def _bando_item(bando: Bando, match: MatchResult) -> dict[str, object]:
    return {
        "id": bando.id,
        "titolo": bando.titolo,
        "ente": bando.ente,
        "scadenza": str(bando.scadenza) if bando.scadenza else "n.d.",
        "compatibilita": match.compatibilita,
        "url": bando.url,
    }


def build_digest_payload(
    filtered: list[tuple[Bando, MatchResult]],
) -> dict[str, object]:
    """Costruisce il payload strutturato per il webhook.

    Separa alta da media per consentire al consumer (n8n) di formattare
    messaggi compatti — i bandi 'alta' in dettaglio, i 'media' come conteggio.
    Questo evita di superare il limite di 4096 caratteri di Telegram anche
    con centinaia di bandi.
    """
    if not filtered:
        return {"data": str(date.today()), "alta": [], "media": [], "totale": 0}

    alta: list[dict[str, object]] = []
    media: list[dict[str, object]] = []

    for bando, match in filtered:
        item = _bando_item(bando, match)
        if match.compatibilita == "alta":
            alta.append(item)
        else:
            media.append(item)

    return {
        "data": str(date.today()),
        "totale": len(filtered),
        "alta": alta,
        "media": media,
    }
