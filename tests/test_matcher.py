import sqlite3
from datetime import date, timedelta
from pathlib import Path

from src.extractor.models import Bando
from src.matcher.checks import (
    check_area_geografica,
    check_categoria,
    check_esclusioni,
    check_scadenza,
    check_titolo_studio,
)
from src.matcher.matcher import aggregate_checks
from src.matcher.matcher import match as internal_match
from src.matcher.models import DISCLAIMER, CandidatoProfilo, CheckItem


def _bando(**kwargs: object) -> Bando:
    defaults: dict[str, object] = {
        "id": "b001",
        "fonte": "inpa",
        "url": "https://example.com",
        "titolo": "Concorso Test",
        "ente": "Comune Test",
        "parse_method": "pdf_text",
    }
    defaults.update(kwargs)
    return Bando(**defaults)  # type: ignore[arg-type]


def _profilo(**kwargs: object) -> CandidatoProfilo:
    defaults: dict[str, object] = {
        "nome": "Mario Rossi",
        "titolo_studio": "Laurea magistrale LM-18 Informatica",
        "aree_preferite": ["Milano", "Lombardia"],
        "settori": ["informatica"],
        "esclusioni": ["riservato ai dipendenti interni"],
    }
    defaults.update(kwargs)
    return CandidatoProfilo(**defaults)  # type: ignore[arg-type]


# --- check_titolo_studio ---

def test_check_titolo_studio_ok_substring() -> None:
    titolo = "Laurea magistrale LM-18 Informatica"
    item = check_titolo_studio(titolo, titolo)
    assert item.esito == "ok"


def test_check_titolo_studio_ok_livello() -> None:
    item = check_titolo_studio("Diploma di scuola superiore", "Laurea magistrale LM-18")
    assert item.esito == "ok"


def test_check_titolo_studio_fail() -> None:
    item = check_titolo_studio("Dottorato di ricerca", "Diploma di scuola superiore")
    assert item.esito == "fail"
    assert item.nota is not None


def test_check_titolo_studio_unknown() -> None:
    item = check_titolo_studio(None, "Laurea magistrale LM-18")
    assert item.esito == "unknown"


# --- check_area_geografica ---

def test_check_area_geografica_ok() -> None:
    item = check_area_geografica("Milano", ["Milano", "Roma"])
    assert item.esito == "ok"


def test_check_area_geografica_warning() -> None:
    item = check_area_geografica("Palermo", ["Milano", "Roma"])
    assert item.esito == "warning"


def test_check_area_geografica_unknown() -> None:
    item = check_area_geografica(None, ["Milano"])
    assert item.esito == "unknown"


# --- check_scadenza ---

def test_check_scadenza_ok() -> None:
    item = check_scadenza(date.today() + timedelta(days=30))
    assert item.esito == "ok"


def test_check_scadenza_expired() -> None:
    item = check_scadenza(date(2020, 1, 1))
    assert item.esito == "fail"
    assert item.nota is not None


def test_check_scadenza_none() -> None:
    item = check_scadenza(None)
    assert item.esito == "unknown"


# --- check_esclusioni ---

def test_check_esclusioni_ok() -> None:
    item = check_esclusioni(["Cittadinanza italiana"], ["riservato ai dipendenti interni"])
    assert item.esito == "ok"


def test_check_esclusioni_triggered() -> None:
    item = check_esclusioni(
        ["Riservato ai dipendenti interni all'ente"],
        ["riservato ai dipendenti interni"],
    )
    assert item.esito == "fail"
    assert item.nota is not None


# --- check_categoria ---

def test_check_categoria_ok() -> None:
    item = check_categoria("informatica e sistemi", ["informatica"])
    assert item.esito == "ok"


def test_check_categoria_warning() -> None:
    item = check_categoria("area amministrativa", ["informatica"])
    assert item.esito == "warning"


def test_check_categoria_unknown() -> None:
    item = check_categoria(None, ["informatica"])
    assert item.esito == "unknown"


# --- aggregate_checks ---

def test_aggregate_all_ok() -> None:
    checks = [CheckItem(requisito="X", esito="ok"), CheckItem(requisito="Y", esito="ok")]
    assert aggregate_checks(checks) == "alta"


def test_aggregate_one_fail() -> None:
    checks = [CheckItem(requisito="X", esito="ok"), CheckItem(requisito="Y", esito="fail")]
    assert aggregate_checks(checks) == "bassa"


def test_aggregate_all_unknown() -> None:
    checks = [CheckItem(requisito="X", esito="unknown")]
    assert aggregate_checks(checks) == "da_verificare"


def test_aggregate_mixed_ok_warning() -> None:
    checks = [CheckItem(requisito="X", esito="ok"), CheckItem(requisito="Y", esito="warning")]
    assert aggregate_checks(checks) == "media"


def test_aggregate_empty() -> None:
    assert aggregate_checks([]) == "da_verificare"


# --- match() ---

def test_match_returns_match_result() -> None:
    from src.matcher.models import MatchResult

    bando = _bando(
        scadenza=date.today() + timedelta(days=30),
        titolo_studio_richiesto="Laurea magistrale LM-18 Informatica",
        area_geografica="Milano",
        categoria="informatica",
    )
    result = internal_match(bando, _profilo())
    assert isinstance(result, MatchResult)
    assert result.disclaimer == DISCLAIMER


def test_match_compatible_alta() -> None:
    bando = _bando(
        scadenza=date.today() + timedelta(days=30),
        titolo_studio_richiesto="Laurea magistrale LM-18 Informatica",
        area_geografica="Milano",
        categoria="informatica",
        requisiti_formali=[],
    )
    result = internal_match(bando, _profilo())
    assert result.compatibilita == "alta"


def test_match_incompatible_bassa() -> None:
    bando = _bando(scadenza=date(2020, 1, 1))
    result = internal_match(bando, _profilo())
    assert result.compatibilita == "bassa"


# --- match() pubblica con persistenza ---

def test_match_persists_to_db(tmp_path: Path) -> None:
    from src.matcher import match as public_match

    bando = _bando(
        scadenza=date.today() + timedelta(days=30),
        titolo_studio_richiesto="Laurea magistrale LM-18 Informatica",
        area_geografica="Milano",
        categoria="informatica",
    )
    db = tmp_path / "test.db"
    result = public_match(bando, _profilo(), db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT bando_id, compatibilita FROM match_results WHERE bando_id = 'b001'"
        ).fetchone()
    assert row is not None
    assert row[1] == result.compatibilita
