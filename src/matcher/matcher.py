from typing import Literal

from src.extractor.models import Bando
from src.matcher.checks import (
    check_area_geografica,
    check_categoria,
    check_esclusioni,
    check_esperienza_dominio,
    check_scadenza,
    check_tipo_atto,
    check_titolo_studio,
)
from src.matcher.models import DISCLAIMER, CandidatoProfilo, CheckItem, MatchResult


def aggregate_checks(
    checks: list[CheckItem],
) -> Literal["alta", "media", "bassa", "da_verificare"]:
    if not checks:
        return "da_verificare"
    esiti = [c.esito for c in checks]
    if all(e == "unknown" for e in esiti):
        return "da_verificare"
    if any(e == "fail" for e in esiti):
        return "bassa"
    n_known = sum(1 for e in esiti if e != "unknown")
    if n_known < 2:
        # Informazioni insufficienti: solo un check con esito noto (tipicamente nessuna esclusione)
        return "da_verificare"
    if any(e == "warning" for e in esiti):
        return "media"
    return "alta"


def match(bando: Bando, profilo: CandidatoProfilo) -> MatchResult:
    checks = [
        check_tipo_atto(bando.titolo, bando.testo_raw),
        check_titolo_studio(bando.titolo_studio_richiesto, profilo.titolo_studio),
        check_area_geografica(bando.area_geografica, profilo.aree_preferite),
        check_scadenza(bando.scadenza),
        check_esclusioni(
            bando.requisiti_formali, profilo.esclusioni, bando.titolo, bando.testo_raw
        ),
        check_categoria(bando.categoria, profilo.settori),
        check_esperienza_dominio(bando.requisiti_formali, profilo.settori, profilo.parole_chiave),
    ]
    compatibilita = aggregate_checks(checks)
    da_verificare = [c.nota for c in checks if c.esito == "unknown" and c.nota]
    return MatchResult(
        bando_id=bando.id,
        profilo_nome=profilo.nome,
        compatibilita=compatibilita,
        checklist=checks,
        da_verificare=[s for s in da_verificare if s],
        disclaimer=DISCLAIMER,
    )
