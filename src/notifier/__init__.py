import logging
import os

import httpx

from src.extractor.models import Bando
from src.matcher.models import MatchResult
from src.notifier.digest import build_digest_payload, filter_bandi

_logger = logging.getLogger(__name__)

_DEFAULT_DAYS_AHEAD = 30


def send_digest(
    results: list[tuple[Bando, MatchResult]],
    days_ahead: int = _DEFAULT_DAYS_AHEAD,
) -> None:
    """Filtra i bandi rilevanti e invia il digest al webhook configurato."""
    webhook_url = os.environ.get("NOTIFIER_WEBHOOK_URL", "")
    if not webhook_url:
        _logger.warning("NOTIFIER_WEBHOOK_URL non configurato — digest non inviato")
        return

    filtered = filter_bandi(results, days_ahead=days_ahead)
    if not filtered:
        _logger.info("Nessun bando da notificare")
        return

    payload = build_digest_payload(filtered)
    try:
        response = httpx.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        _logger.info("Digest inviato: %d bandi", len(filtered))
    except Exception as exc:
        _logger.error("Errore invio digest: %s", exc)


__all__ = ["send_digest", "filter_bandi", "build_digest_payload"]
