import json
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.extractor.prompt import EXTRACTION_PROMPT, EXTRACTION_PROMPT_SIMPLIFIED


def _get_llm() -> ChatOpenAI:
    api_key = SecretStr(os.environ.get("OPENROUTER_API_KEY", "placeholder"))
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        model=os.environ.get("OPENROUTER_MODEL", "mistralai/mistral-small-3.2-24b-instruct"),
        temperature=0,
    )


def _extract_json_from_text(text: str) -> dict[str, Any]:
    """Estrae il primo oggetto JSON dalla risposta LLM, gestendo code block markdown."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))  # type: ignore[no-any-return]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))  # type: ignore[no-any-return]
    return json.loads(text)  # type: ignore[no-any-return]


def _compute_confidence(data: dict[str, Any]) -> float:
    """Proporzione di campi opzionali non-None su totale campi opzionali."""
    optional_fields = [
        "categoria",
        "area_geografica",
        "posti",
        "scadenza",
        "titolo_studio_richiesto",
        "tassa_concorso",
        "link_candidatura",
    ]
    filled = sum(1 for f in optional_fields if data.get(f) is not None)
    return round(filled / len(optional_fields), 2)


def run_extraction(testo: str) -> tuple[dict[str, Any], float]:
    """Estrae dati strutturati dal testo con retry su prompt semplificato.

    Restituisce (dati_estratti, extraction_confidence).
    Solleva RuntimeError se entrambi i tentativi falliscono.
    """
    llm = _get_llm()
    last_exc: Exception = RuntimeError("Estrazione fallita")

    for prompt in (EXTRACTION_PROMPT, EXTRACTION_PROMPT_SIMPLIFIED):
        try:
            response = (prompt | llm).invoke({"testo_bando": testo})
            raw = response.content
            content = raw if isinstance(raw, str) else str(raw)
            data: dict[str, Any] = _extract_json_from_text(content)
            confidence = _compute_confidence(data)
            return data, confidence
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError("Estrazione fallita dopo tutti i tentativi") from last_exc
