# concorsi-qualifier — Public Concorsi Intelligence

Sistema AI modulare per il monitoraggio e la qualificazione automatica di bandi di concorso pubblico italiani.

---

## Stack

### Obbligatori

| Componente | Scelta |
|---|---|
| Linguaggio | Python 3.11+ |
| Scraping | Crawlee (Python SDK) |
| Orchestrazione LLM | LangChain |
| LLM estrazione bandi | OpenRouter (Mistral/Gemma 2) — dati pubblici |
| LLM matching/reporting | Ollama locale (Llama 3.1 / Mistral) — dati privati |
| Validazione output | Pydantic v2 |
| Storage | SQLite + file system |
| PDF text extraction | pdfplumber / pypdf |
| PDF OCR fallback | pytesseract + Tesseract (lingua: ita) |

### Opzionali (V2+)

| Componente | Uso |
|---|---|
| n8n / Make | Scheduling + digest email |
| ChromaDB / FAISS | RAG su documenti normativi |
| Streamlit | Dashboard |
| PostgreSQL | Scaling multi-tenant |

---

## Struttura moduli

| Modulo | Input | Output | Responsabilità |
|---|---|---|---|
| `collector` | Config fonti YAML | HTML/PDF su filesystem + log SQLite | Scarica bandi, calcola hash per deduplicazione, registra ogni run |
| `parser` | File HTML/PDF raw | Testo estratto + `parse_method` | Fallback chain: pdf_text → pdf_ocr → parse_failed |
| `extractor` | Testo bando | `Bando` Pydantic validato | LangChain + OpenRouter → JSON strutturato, retry su validation error |
| `matcher` | `Bando` + `CandidatoProfilo` | `MatchResult` | Checklist deterministica Python — nessun LLM per la decisione |
| `reporter` | `MatchResult` | Scheda Markdown | LLM locale (Ollama) genera solo la spiegazione testuale del risultato |
| `notifier` | Schede Markdown | Email digest | Trigger n8n/Make, bandi nuovi o in scadenza con compatibilità ≥ media |

---

## Vincoli non negoziabili

- **Nessun invio automatico di candidature** — human-in-the-loop sempre, senza eccezioni.
- **Il profilo candidato non esce mai dalla macchina locale** — non passa per nessun LLM cloud.
- **Nessuna consulenza legale automatica** — il sistema offre prima qualificazione assistita, non pareri sui requisiti di ammissione.
- **Disclaimer obbligatorio su ogni output**: *"Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato."*
- **Rispetto dei termini di servizio** delle fonti scraped.

---

## Principio architetturale chiave

```
LLM esterno (OpenRouter)  →  estrae i dati dal bando
Logica Python             →  decide il match (checklist deterministica)
LLM locale (Ollama)       →  genera solo la spiegazione testuale del risultato
```

Il LLM non prende mai decisioni di matching. L'output è auditabile e riproducibile indipendentemente dal modello usato.

---

## Valenza dual-use (piano B)

Oltre alla funzione portfolio (case study AI), questo progetto è un **seme di business** nel piano B di contingenza (`piano-b.md` §3, nel workspace di pianificazione). Guardrail da rispettare durante lo sviluppo:

- **Motore generico, non inchiodato sui bandi.** Tenere la pipeline (collector → parser → extractor → reporter) separata dalle parti specifiche del dominio "bandi" (`Bando`, checklist del `matcher`), così che ripuntare il motore su un altro verticale documentale (es. gare d'appalto, ciclo passivo) a switch attivato sia economico. Separabilità architetturale ora; un solo verticale (bandi) implementato. Non costruire il secondo verticale adesso.
- **Niente lavoro "solo business" in fase portfolio.** No multi-utente, no billing, no feature B2B (il `PostgreSQL` multi-tenant resta V2/post-switch come già segnato nello stack opzionale).
- **Kill criteria:** se a validazione fatta nessun buyer B2B conferma il dolore a un prezzo sostenibile, resta solo portfolio. Va benissimo così.

---

## Convenzioni di codice

- **Pydantic v2** per tutti i modelli dati (`Bando`, `CandidatoProfilo`, `MatchResult`, `CheckItem`).
- **Tipo di ritorno esplicito** su ogni funzione pubblica (nessuna firma senza `-> Type`).
- **Test con pytest** e fixture basate su bandi reali (file in `tests/fixtures/`).
- Nomi variabili e funzioni in **snake_case** inglese; testi e commenti in italiano.
- Ogni modulo espone la sua funzione principale tramite `__init__.py` — nessuna importazione interna cross-modulo diretta.

---

## Flusso dati (pipeline sequenziale MVP)

```
[Fonti: InPA, RIPAM, enti locali]
        ↓
[collector]  →  filesystem raw/ + SQLite (log run)
        ↓
[parser]     →  testo estratto + parse_method
        ↓
[extractor]  →  Bando (Pydantic) + extraction_confidence
        ↓
[matcher]    →  MatchResult (checklist deterministica)
        ↓
[reporter]   →  scheda Markdown (spiegazione via Ollama)
        ↓
[notifier]   →  digest email settimanale (n8n/Make)
```
