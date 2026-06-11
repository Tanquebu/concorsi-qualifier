from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.extractor.models import Bando
from src.matcher.models import DISCLAIMER, CheckItem, MatchResult
from src.reporter.chain import _parse_response
from src.reporter.prompt import REPORTER_PROMPT
from src.reporter.renderer import render_scheda


def _bando(**kwargs: object) -> Bando:
    defaults: dict[str, object] = {
        "id": "b001",
        "fonte": "inpa",
        "url": "https://example.com/bando/1",
        "titolo": "Concorso Informatici",
        "ente": "Comune di Roma",
        "parse_method": "pdf_text",
        "scadenza": date.today() + timedelta(days=30),
        "area_geografica": "Roma",
        "posti": 5,
        "materie_esame": ["Informatica"],
        "requisiti_formali": ["Cittadinanza italiana"],
    }
    defaults.update(kwargs)
    return Bando(**defaults)  # type: ignore[arg-type]


def _match_result(**kwargs: object) -> MatchResult:
    defaults: dict[str, object] = {
        "bando_id": "b001",
        "profilo_nome": "Mario Rossi",
        "compatibilita": "alta",
        "checklist": [
            CheckItem(requisito="Titolo di studio", esito="ok"),
            CheckItem(requisito="Scadenza", esito="ok"),
        ],
    }
    defaults.update(kwargs)
    return MatchResult(**defaults)  # type: ignore[arg-type]


# --- prompt ---

def test_reporter_prompt_render() -> None:
    result = REPORTER_PROMPT.format_messages(
        titolo="Concorso Test",
        ente="Comune Test",
        scadenza="2026-12-31",
        compatibilita="alta",
        checklist_testo="- Titolo di studio: OK",
        da_verificare_testo="Nessuno",
    )
    assert len(result) > 0
    full_text = " ".join(m.content for m in result if hasattr(m, "content"))
    assert len(full_text) > 50


def test_reporter_prompt_disclaimer_present() -> None:
    result = REPORTER_PROMPT.format_messages(
        titolo="Test",
        ente="Ente",
        scadenza="2026-12-31",
        compatibilita="media",
        checklist_testo="- X: OK",
        da_verificare_testo="Nessuno",
    )
    full_text = " ".join(m.content for m in result if hasattr(m, "content"))
    assert "responsabilità del candidato" in full_text


# --- _parse_response ---

def test_parse_response_structured() -> None:
    text = (
        "SPIEGAZIONE:\nIl bando è compatibile con il profilo.\n\n"
        "AZIONI CONSIGLIATE:\n- Verificare i documenti\n- Preparare il CV\n"
    )
    result = _parse_response(text)
    assert "compatibile" in result["spiegazione"]
    assert len(result["azioni_consigliate"]) >= 2  # type: ignore[arg-type]


def test_parse_response_fallback_on_free_text() -> None:
    result = _parse_response("Risposta libera del modello senza formato.")
    assert isinstance(result["spiegazione"], str)
    assert isinstance(result["azioni_consigliate"], list)


def test_parse_response_empty() -> None:
    result = _parse_response("")
    assert result["spiegazione"] == ""
    assert result["azioni_consigliate"] == []


# --- renderer ---

def test_renderer_sections_present(tmp_path: Path) -> None:
    spiegazione = {
        "spiegazione": "Il bando è compatibile con il tuo profilo.",
        "azioni_consigliate": ["Verifica i documenti", "Prepara il CV"],
    }
    content, path = render_scheda(_match_result(), _bando(), spiegazione, tmp_path)
    assert "## Riepilogo" in content
    assert "## Compatibilità" in content
    assert "## Checklist requisiti" in content
    assert "## Analisi" in content
    assert "## Azioni consigliate" in content


def test_renderer_disclaimer_present(tmp_path: Path) -> None:
    content, _ = render_scheda(_match_result(), _bando(), {}, tmp_path)
    assert DISCLAIMER in content
    assert "responsabilità del candidato" in content


def test_renderer_file_saved(tmp_path: Path) -> None:
    _, path = render_scheda(_match_result(), _bando(), {}, tmp_path)
    assert path.exists()
    assert path.suffix == ".md"
    assert path.stat().st_size > 0


# --- generate_report ---

def _make_ollama_mock(response_text: str) -> RunnableLambda:
    def _fn(_: object) -> AIMessage:
        return AIMessage(content=response_text)

    return RunnableLambda(_fn)


_MOCK_RESPONSE = (
    "SPIEGAZIONE:\nBando compatibile con il profilo.\n\n"
    "AZIONI CONSIGLIATE:\n- Verifica scadenza\n- Prepara CV\n"
)


def test_generate_report_returns_path(tmp_path: Path) -> None:
    from src.reporter import generate_report

    with patch("src.reporter.chain._get_llm", return_value=_make_ollama_mock(_MOCK_RESPONSE)):
        path = generate_report(_match_result(), _bando(), output_dir=tmp_path)

    assert isinstance(path, Path)
    assert path.exists()
    assert DISCLAIMER in path.read_text(encoding="utf-8")
