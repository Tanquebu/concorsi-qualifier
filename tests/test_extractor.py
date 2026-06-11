import json
import re
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.extractor.chain import _compute_confidence, _extract_json_from_text, run_extraction
from src.extractor.prompt import EXTRACTION_PROMPT, EXTRACTION_PROMPT_SIMPLIFIED

_VALID_JSON = json.dumps(
    {
        "titolo": "Concorso Informatici",
        "ente": "Comune di Roma",
        "scadenza": "2026-12-31",
        "posti": 10,
        "titolo_studio_richiesto": "Laurea in Informatica",
        "area_geografica": "Roma",
        "categoria": None,
        "tassa_concorso": None,
        "link_candidatura": None,
        "requisiti_formali": ["Cittadinanza italiana"],
        "materie_esame": ["Informatica generale"],
        "documenti_richiesti": ["CV aggiornato"],
    }
)


def _make_llm(*responses: str) -> RunnableLambda:
    """LLM mock che restituisce le risposte in sequenza."""
    it = iter(responses)

    def _fn(_: object) -> AIMessage:
        return AIMessage(content=next(it))

    return RunnableLambda(_fn)


# --- prompt ---

def test_prompt_render() -> None:
    result = EXTRACTION_PROMPT.format(testo_bando="Testo bando di prova lungo quanto basta")
    assert isinstance(result, str)
    assert len(result) > 50
    assert "Testo bando di prova" in result


def test_prompt_no_unresolved_vars() -> None:
    result = EXTRACTION_PROMPT.format(testo_bando="test input")
    assert not re.search(r"\{[a-z_]+\}", result)


def test_prompt_simplified_render() -> None:
    result = EXTRACTION_PROMPT_SIMPLIFIED.format(testo_bando="test")
    assert "test" in result
    assert len(result) > 20


# --- _extract_json_from_text ---

def test_extract_json_plain() -> None:
    data = _extract_json_from_text('{"titolo": "Concorso", "posti": 5}')
    assert data["titolo"] == "Concorso"
    assert data["posti"] == 5


def test_extract_json_markdown_block() -> None:
    data = _extract_json_from_text('```json\n{"titolo": "Test"}\n```')
    assert data["titolo"] == "Test"


def test_extract_json_with_preamble() -> None:
    data = _extract_json_from_text(
        'Ecco il JSON estratto:\n{"titolo": "Bando", "ente": "Comune"}'
    )
    assert data["titolo"] == "Bando"


def test_extract_json_invalid_raises() -> None:
    with pytest.raises(Exception):
        _extract_json_from_text("testo senza json")


# --- _compute_confidence ---

def test_compute_confidence_all_filled() -> None:
    data = {
        "categoria": "informatica",
        "area_geografica": "Roma",
        "posti": 5,
        "scadenza": "2026-12-31",
        "titolo_studio_richiesto": "Laurea",
        "tassa_concorso": 10.0,
        "link_candidatura": "https://example.com",
    }
    assert _compute_confidence(data) == 1.0


def test_compute_confidence_all_none() -> None:
    assert _compute_confidence({}) == 0.0


# --- run_extraction ---

def test_run_extraction_valid_response() -> None:
    with patch("src.extractor.chain._get_llm", return_value=_make_llm(_VALID_JSON, _VALID_JSON)):
        data, confidence = run_extraction("Testo bando di prova")
    assert data["titolo"] == "Concorso Informatici"
    assert 0.0 <= confidence <= 1.0


def test_run_extraction_retry_on_invalid() -> None:
    with patch(
        "src.extractor.chain._get_llm",
        return_value=_make_llm("JSON INVALIDO {{{", _VALID_JSON),
    ):
        data, confidence = run_extraction("Testo bando")
    assert data["titolo"] == "Concorso Informatici"


def test_run_extraction_raises_after_all_fail() -> None:
    with patch(
        "src.extractor.chain._get_llm",
        return_value=_make_llm("RISPOSTA NON JSON", "ANCORA NON JSON"),
    ):
        with pytest.raises(RuntimeError):
            run_extraction("testo")


# --- extract() ---

def test_extract_returns_bando(tmp_path: Path) -> None:
    from src.extractor import extract
    from src.extractor.models import Bando

    with patch("src.extractor.run_extraction", return_value=(json.loads(_VALID_JSON), 0.8)):
        bando = extract(
            "Testo del bando",
            "pdf_text",
            url="https://example.com/bando/1",
            fonte="inpa",
            bando_id="hash001",
            db_path=tmp_path / "test.db",
        )
    assert isinstance(bando, Bando)
    assert bando.titolo == "Concorso Informatici"
    assert bando.extraction_confidence == 0.8


def test_extract_persists_to_db(tmp_path: Path) -> None:
    from src.extractor import extract

    db = tmp_path / "test.db"
    with patch("src.extractor.run_extraction", return_value=(json.loads(_VALID_JSON), 0.7)):
        extract(
            "testo bando",
            "html",
            url="https://x.com",
            fonte="test",
            bando_id="id-001",
            db_path=db,
        )

    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT titolo, fonte FROM bandi WHERE id = 'id-001'").fetchone()
    assert row is not None
    assert row[0] == "Concorso Informatici"
    assert row[1] == "test"


# --- fixture reale bando_01 ---

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "extractor"
_BANDO_01_TXT = _FIXTURE_DIR / "bando_01.txt"
_BANDO_01_EXPECTED = _FIXTURE_DIR / "bando_01_expected.json"


def test_extract_real_fixture_bando_01(tmp_path: Path) -> None:
    """Verifica che il testo reale del bando venga processato correttamente."""
    from src.extractor import extract
    from src.extractor.models import Bando

    testo = _BANDO_01_TXT.read_text(encoding="utf-8")
    expected = json.loads(_BANDO_01_EXPECTED.read_text(encoding="utf-8"))

    llm_response = json.dumps(
        {
            **expected,
            "documenti_richiesti": [],
        }
    )

    with patch(
        "src.extractor.chain._get_llm",
        return_value=_make_llm(llm_response, llm_response),
    ):
        bando = extract(
            testo,
            "pdf_text",
            url="https://www.inpa.gov.it/bando-oss-sinalunga-2026/",
            fonte="inpa",
            bando_id="inpa-oss-sinalunga-2026",
            db_path=tmp_path / "test.db",
        )

    assert isinstance(bando, Bando)
    assert bando.posti == expected["posti"]
    assert bando.ente == expected["ente"]
    assert str(bando.scadenza) == expected["scadenza"]
    assert bando.tassa_concorso == expected["tassa_concorso"]
    assert len(bando.materie_esame) >= 5
    assert len(bando.requisiti_formali) >= 3


def test_extract_real_fixture_prompt_renders() -> None:
    """Verifica che il prompt si renderizzi senza errori con testo reale lungo."""
    testo = _BANDO_01_TXT.read_text(encoding="utf-8")
    result = EXTRACTION_PROMPT.format(testo_bando=testo)
    assert len(result) > 500
    assert not re.search(r"\{[a-z_]+\}", result)
