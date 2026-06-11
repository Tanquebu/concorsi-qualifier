import os
import re

from langchain_community.chat_models import ChatOllama

from src.extractor.models import Bando
from src.matcher.models import MatchResult
from src.reporter.prompt import REPORTER_PROMPT


def _get_llm() -> ChatOllama:
    return ChatOllama(
        model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )


def _format_checklist(match_result: MatchResult) -> str:
    lines = []
    for item in match_result.checklist:
        nota = f" ({item.nota})" if item.nota else ""
        lines.append(f"- {item.requisito}: {item.esito.upper()}{nota}")
    return "\n".join(lines) if lines else "Nessuna voce"


def _parse_response(text: str) -> dict[str, object]:
    """Parsing robusto: estrae SPIEGAZIONE e AZIONI CONSIGLIATE. Fallback graceful."""
    spiegazione = ""
    azioni: list[str] = []

    match = re.search(r"SPIEGAZIONE:\s*(.+?)(?:AZIONI CONSIGLIATE:|$)", text, re.DOTALL)
    if match:
        spiegazione = match.group(1).strip()
    else:
        spiegazione = text.strip()

    match = re.search(r"AZIONI CONSIGLIATE:\s*(.+?)$", text, re.DOTALL)
    if match:
        azioni = [
            line.lstrip("-•* \t").strip()
            for line in match.group(1).splitlines()
            if line.strip() and line.strip() not in ("-",)
        ]

    return {"spiegazione": spiegazione, "azioni_consigliate": azioni}


def generate_explanation(match_result: MatchResult, bando: Bando) -> dict[str, object]:
    """Chiama Ollama per generare spiegazione e azioni. Fallback graceful su errore."""
    try:
        llm = _get_llm()
        da_verificare_testo = (
            "\n".join(f"- {v}" for v in match_result.da_verificare) or "Nessuno"
        )
        response = (REPORTER_PROMPT | llm).invoke(
            {
                "titolo": bando.titolo,
                "ente": bando.ente,
                "scadenza": str(bando.scadenza) if bando.scadenza else "non specificata",
                "compatibilita": match_result.compatibilita,
                "checklist_testo": _format_checklist(match_result),
                "da_verificare_testo": da_verificare_testo,
            }
        )
        raw = response.content
        content = raw if isinstance(raw, str) else str(raw)
        return _parse_response(content)
    except Exception:
        return {"spiegazione": "", "azioni_consigliate": []}
