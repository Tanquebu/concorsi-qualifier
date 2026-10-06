import json
import logging
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.extractor.prompt import EXTRACTION_PROMPT, EXTRACTION_PROMPT_SIMPLIFIED

logger = logging.getLogger(__name__)

# Tetto al testo mandato al modello. Gli allegati InPA con elenchi e graduatorie arrivano a
# 550k char (~330k token) contro i 128k di contesto del modello di default: senza taglio la
# chiamata torna 502 "maximum context length" e il bando viene perso a ogni run. Il contenuto
# utile (titolo, ente, scadenza, requisiti) sta in testa, le code sono tabelle di profili.
# 150k char sono ~91k token: con i 16k di output richiesti si resta sotto il limite lasciando
# margine al prompt. Override con EXTRACTION_MAX_INPUT_CHARS.
_MAX_INPUT_CHARS = int(os.environ.get("EXTRACTION_MAX_INPUT_CHARS", "150000"))
_TRUNCATION_MARK = "\n\n[...documento troncato per limite di contesto...]"

# Errori imputabili al provider e non al documento: ritentarli alla run successiva ha senso.
_TRANSIENT_MARKERS = (
    "429",
    "rate limit",
    "rate-limited",
    "engine_overloaded",
    "overloaded",
    "temporarily",
    "timeout",
    "timed out",
    "502",
    "503",
    "504",
    "connection error",
    "connection reset",
    "service unavailable",
)

# I tipi dell'SDK openai non ripetono sempre il motivo nel messaggio (un RateLimitError puo'
# arrivare con solo "Provider returned error"): il nome della classe e' gia' la diagnosi.
_TRANSIENT_TYPES = (
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "InternalServerError",
    "ServiceUnavailableError",
    "TimeoutError",
    "ConnectionError",
)


def is_transient_error(exc: BaseException | None) -> bool:
    """True se l'errore, o una delle sue cause, dipende dal provider e non dal documento."""
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if type(exc).__name__ in _TRANSIENT_TYPES:
            return True
        if any(marker in str(exc).lower() for marker in _TRANSIENT_MARKERS):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def truncate_for_context(testo: str) -> str:
    """Taglia il testo alla lunghezza massima che il modello riesce ad accettare."""
    if len(testo) <= _MAX_INPUT_CHARS:
        return testo
    logger.warning("Testo troncato per il contesto: %d char -> %d", len(testo), _MAX_INPUT_CHARS)
    return testo[:_MAX_INPUT_CHARS] + _TRUNCATION_MARK


def _get_llm() -> ChatOpenAI:
    api_key = SecretStr(os.environ.get("OPENROUTER_API_KEY", "placeholder"))
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        model=os.environ.get("OPENROUTER_MODEL", "mistralai/mistral-small-3.2-24b-instruct"),
        temperature=0,
        default_headers={"X-Title": "concorsi-qualifier"},
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


# Riga "Sede:" dell'header che il collector InPA mette in testa al testo. Il LLM la copia quasi
# sempre alla lettera in area_geografica, ma a volte restituisce null pur avendola davanti.
_SEDE_HEADER_RE = re.compile(r"^Sede:[ \t]*\n?[ \t]*(\S[^\n]*)$", re.MULTILINE)
_SEDE_HEADER_WINDOW = 2000
# Record raccolti con una versione precedente del collector: le sedi sono repr di dict Python.
_SEDE_DENOMINAZIONE_RE = re.compile(r"'(?:provincia|regione)Denominazione': '([^']+)'")


def _area_from_header(testo: str) -> str | None:
    """Ricava la sede dalla riga "Sede:" dell'header InPA, se presente."""
    match = _SEDE_HEADER_RE.search(testo[:_SEDE_HEADER_WINDOW])
    if not match:
        return None
    value = match.group(1).strip()
    if value.endswith(":"):
        # Sede vuota: la regex ha agganciato l'etichetta della riga successiva
        return None
    if "Denominazione'" in value:
        nomi = list(dict.fromkeys(_SEDE_DENOMINAZIONE_RE.findall(value)))
        return ", ".join(nomi) or None
    return value


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


def run_extraction(testo: str, data_pubblicazione: str = "") -> tuple[dict[str, Any], float]:
    """Estrae dati strutturati dal testo con retry su prompt semplificato.

    Restituisce (dati_estratti, extraction_confidence).
    Solleva RuntimeError se entrambi i tentativi falliscono.
    """
    llm = _get_llm()
    last_exc: Exception = RuntimeError("Estrazione fallita")
    data_pub = data_pubblicazione or "non disponibile"
    invoke_input = {"testo_bando": truncate_for_context(testo), "data_pubblicazione": data_pub}

    for prompt in (EXTRACTION_PROMPT, EXTRACTION_PROMPT_SIMPLIFIED):
        try:
            response = (prompt | llm).invoke(invoke_input)
            raw = response.content
            content = raw if isinstance(raw, str) else str(raw)
            data: dict[str, Any] = _extract_json_from_text(content)
            if not data.get("area_geografica"):
                data["area_geografica"] = _area_from_header(testo)
            confidence = _compute_confidence(data)
            return data, confidence
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError("Estrazione fallita dopo tutti i tentativi") from last_exc
