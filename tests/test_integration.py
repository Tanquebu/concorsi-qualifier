"""Integration test end-to-end: parse → extract (mock) → match → generate_report."""
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.extractor.models import Bando
from src.matcher import match
from src.matcher.models import DISCLAIMER, CandidatoProfilo
from src.parser import parse
from src.reporter import generate_report

_FIXTURE_HTML = Path(__file__).parent / "fixtures" / "parser" / "bando_sample.html"

_MOCK_BANDO = Bando(
    id="integration-01",
    fonte="inpa",
    url="https://www.comune.milano.it/concorso-informatici",
    titolo="Concorso pubblico – n. 5 posti Informatico categoria D",
    ente="Comune di Milano",
    parse_method="html",
    scadenza=date.today() + timedelta(days=60),
    area_geografica="Milano",
    categoria="informatica",
    titolo_studio_richiesto="Laurea magistrale LM-18 Informatica",
    posti=5,
    materie_esame=["Informatica", "Algoritmi e strutture dati", "Basi di dati"],
    requisiti_formali=["Cittadinanza italiana o UE"],
    extraction_confidence=0.9,
)

_PROFILO = CandidatoProfilo(
    nome="Mario Rossi",
    titolo_studio="Laurea magistrale LM-18 Informatica",
    aree_preferite=["Milano", "Lombardia"],
    settori=["informatica"],
    esclusioni=["riservato ai dipendenti interni"],
)

_MOCK_LLM_RESPONSE = (
    "SPIEGAZIONE:\nIl bando è compatibile con il profilo del candidato.\n\n"
    "AZIONI CONSIGLIATE:\n- Verificare i requisiti formali\n- Preparare il CV\n"
)


def _make_mock_llm() -> RunnableLambda:
    def _fn(_: object) -> AIMessage:
        return AIMessage(content=_MOCK_LLM_RESPONSE)

    return RunnableLambda(_fn)


def test_pipeline_end_to_end(tmp_path: Path) -> None:
    # Step 1: parse HTML fixture
    parse_result = parse(_FIXTURE_HTML)
    assert parse_result.parse_method == "html"
    assert len(parse_result.testo) > 50

    # Step 2: extract (mock — non chiama OpenRouter)
    bando = _MOCK_BANDO

    # Step 3: match (deterministica, nessun mock necessario)
    db = tmp_path / "integration.db"
    match_result = match(bando, _PROFILO, db_path=db)
    assert match_result.bando_id == bando.id
    assert match_result.compatibilita in ("alta", "media", "bassa", "da_verificare")
    assert match_result.disclaimer == DISCLAIMER

    # Step 4: generate_report (mock Ollama)
    with patch("src.reporter.chain._get_llm", return_value=_make_mock_llm()):
        report_path = generate_report(match_result, bando, output_dir=tmp_path)

    assert report_path.exists()
    assert report_path.suffix == ".md"
    content = report_path.read_text(encoding="utf-8")
    assert DISCLAIMER in content
    assert bando.titolo in content
    assert match_result.compatibilita.upper() in content


def test_pipeline_compatible_alta(tmp_path: Path) -> None:
    """Con bando e profilo perfettamente allineati, la compatibilità deve essere alta."""
    db = tmp_path / "integration.db"
    match_result = match(_MOCK_BANDO, _PROFILO, db_path=db)
    assert match_result.compatibilita == "alta"
