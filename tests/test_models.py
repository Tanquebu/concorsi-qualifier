import warnings
from datetime import date

import pytest
from pydantic import ValidationError

from src.extractor.models import Bando
from src.matcher.models import DISCLAIMER, CandidatoProfilo, CheckItem, MatchResult


def _bando_minimo(**kwargs: object) -> Bando:
    defaults: dict[str, object] = {
        "id": "hash001",
        "fonte": "inpa.gov.it",
        "url": "https://example.com/bando/1",
        "titolo": "Concorso Test",
        "ente": "Comune di Test",
        "parse_method": "pdf_text",
    }
    defaults.update(kwargs)
    return Bando(**defaults)  # type: ignore[arg-type]


# --- Bando ---

def test_bando_valid() -> None:
    b = _bando_minimo()
    assert b.id == "hash001"
    assert b.status == "ok"
    assert b.extraction_confidence == 0.0


def test_bando_optional_fields() -> None:
    b = _bando_minimo()
    assert b.categoria is None
    assert b.posti is None
    assert b.scadenza is None
    assert b.requisiti_formali == []


def test_bando_confidence_range() -> None:
    with pytest.raises(ValidationError):
        _bando_minimo(extraction_confidence=1.1)
    with pytest.raises(ValidationError):
        _bando_minimo(extraction_confidence=-0.1)


def test_bando_confidence_bounds() -> None:
    b_min = _bando_minimo(extraction_confidence=0.0)
    b_max = _bando_minimo(extraction_confidence=1.0)
    assert b_min.extraction_confidence == 0.0
    assert b_max.extraction_confidence == 1.0


def test_bando_scadenza_passata() -> None:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        b = _bando_minimo(scadenza=date(2020, 1, 1))
    assert b.scadenza == date(2020, 1, 1)
    assert any("scadenza" in str(warning.message).lower() for warning in w)


def test_bando_parse_method_literal() -> None:
    with pytest.raises(ValidationError):
        _bando_minimo(parse_method="invalid_method")


# --- CheckItem ---

def test_check_item_valid() -> None:
    item = CheckItem(requisito="Titolo di studio", esito="ok")
    assert item.nota is None


def test_check_item_literals() -> None:
    with pytest.raises(ValidationError):
        CheckItem(requisito="Test", esito="invalid")


# --- MatchResult ---

def test_match_result_roundtrip() -> None:
    mr = MatchResult(
        bando_id="hash001",
        profilo_nome="Mario Rossi",
        compatibilita="alta",
        checklist=[CheckItem(requisito="Titolo", esito="ok")],
    )
    dumped = mr.model_dump()
    mr2 = MatchResult.model_validate(dumped)
    assert mr2.bando_id == mr.bando_id
    assert mr2.compatibilita == mr.compatibilita
    assert mr2.disclaimer == DISCLAIMER


def test_match_result_literals() -> None:
    with pytest.raises(ValidationError):
        MatchResult(
            bando_id="x",
            profilo_nome="Test",
            compatibilita="altissima",
            checklist=[],
        )


def test_match_result_disclaimer_hardcoded() -> None:
    mr = MatchResult(
        bando_id="x",
        profilo_nome="Test",
        compatibilita="media",
        checklist=[],
    )
    assert mr.disclaimer == DISCLAIMER
    assert "responsabilità del candidato" in mr.disclaimer


# --- CandidatoProfilo ---

def test_candidato_profilo_valid() -> None:
    p = CandidatoProfilo(nome="Mario", titolo_studio="LM-18")
    assert p.aree_preferite == []
    assert p.anni_esperienza is None
