# Architettura tecnica — Public Concorsi Intelligence

> Generato da SPEC.md Sezione 1. Documento di riferimento per lo sviluppo.

---

## 1. Descrizione testuale

Il sistema si articola in sei moduli indipendenti che operano in pipeline sequenziale. Il `collector` interroga periodicamente i portali pubblici configurati (attualmente InPA via WordPress REST API) tramite httpx, salva snapshot HTML/PDF sul filesystem con sidecar `.meta.json` (url, fonte, data scraping), usa hash `url + data_pubblicazione` per deduplicazione, e registra ogni run in SQLite. I siti che rendono il contenuto via JavaScript (SPA Angular/React come RIPAM) richiedono Playwright e non sono ancora supportati. Il `parser` applica una fallback chain a tre livelli: estrazione testuale diretta con pdfplumber/pypdf, OCR con pytesseract + Tesseract (lingua italiana) per i PDF scansionati, marcatura `parse_failed` per i documenti irrecuperabili — che vengono conservati per revisione manuale, non scartati silenziosamente. L'`extractor` passa il testo a una chain LangChain che chiama OpenRouter (dati pubblici, nessun vincolo privacy), ottiene JSON strutturato e lo valida con il modello Pydantic v2 `Bando`; in caso di validation error, ritenta con prompt semplificato. Il `matcher` riceve un `Bando` e un `CandidatoProfilo` (letto da YAML locale) e produce un `MatchResult` tramite checklist deterministica Python puro: nessun LLM interviene nella decisione di compatibilità. L'esito è uno tra `alta | media | bassa | da_verificare`. Il `reporter` chiama Ollama locale per generare la spiegazione testuale del risultato e produce una scheda Markdown; il LLM locale riceve solo l'aggregato (checklist + esito), mai il profilo grezzo. Il `notifier` filtra i bandi con compatibilità ≥ media e li invia come digest email tramite n8n/Make.

La separazione cloud/locale è architetturale: `extractor` usa sempre OpenRouter, `reporter` usa sempre Ollama. Non è una scelta di configurazione ma di struttura del codice — il profilo candidato non può fisicamente raggiungere un LLM cloud.

---

## 2. Diagramma ASCII

```
[fonti_web: InPA (WordPress API) | RIPAM, enti_locali (TODO: Playwright)]
          │
          ▼
    [collector]  ─────────────────────────────┐
  Crawlee • hash-dedup                        │
          │                                   │
          ▼                                   │
  [data/raw/]  filesystem snapshot            │ SQLite
          │                                   │ (run_log,
          ▼                                   │  bandi,
      [parser]                                │  match_results)
  pdf_text → pdf_ocr → parse_failed          │
          │                                   │
          ▼                                   │
    [extractor]                               │
  LangChain + OpenRouter (cloud)              │
  → Bando (Pydantic v2)  ───────────────────►│
          │                                   │
          ▼                                   │
      [matcher]  ◄── CandidatoProfilo (YAML) │
  checklist Python deterministica             │
  → MatchResult  ──────────────────────────►│
          │                                   │
          ▼                                   │
     [reporter]                               │
  Ollama locale (Llama 3.1 / Mistral)        │
  → scheda Markdown in data/processed/        │
          │                                   │
          ▼                                   │
    [notifier]                                │
  n8n / Make cron                             │
  → digest email settimanale                  │
                                              │
  [SQLite: concorsi.db] ◄────────────────────┘
```

---

## 3. Responsabilità moduli

| Modulo | Input | Output | Dipendenze |
|---|---|---|---|
| `collector` | `config/sources.yaml` | File raw in `data/raw/` + sidecar `.meta.json`, log run in SQLite (`collector_runs`) | httpx, BeautifulSoup4, pyyaml |
| `parser` | File raw HTML/PDF da `data/raw/` | Testo estratto + campo `parse_method` | pdfplumber, pypdf, pytesseract, Pillow |
| `extractor` | Testo bando + `parse_method` | `Bando` (Pydantic v2) persistito in SQLite | LangChain, langchain-openai, Pydantic v2, tenacity |
| `matcher` | `Bando` da SQLite + `CandidatoProfilo` da YAML locale | `MatchResult` (Pydantic v2) persistito in SQLite | Pydantic v2, python-dateutil |
| `reporter` | `MatchResult` + `Bando` da SQLite | Scheda Markdown in `data/processed/` | LangChain, langchain-ollama, Ollama (locale o remoto) |
| `notifier` | Schede Markdown filtrate per compatibilità | Payload email digest (HTML/plain) | n8n / Make (esterno via webhook), httpx |

---

## 4. Decisioni architetturali chiave

- **Separazione LLM cloud / LLM locale è strutturale, non configurabile**: `extractor` chiama sempre OpenRouter, `reporter` chiama sempre Ollama. Non esiste un flag per invertire i ruoli — il profilo candidato non può raggiungere un LLM cloud per costruzione.
- **Matching deterministico, mai LLM**: il `matcher` usa solo logica Python (checklist di funzioni `check_*`). L'output `MatchResult` è auditabile, riproducibile e identico indipendentemente dal modello LLM disponibile.
- **PDF fallback chain a tre livelli**: pdfplumber → pytesseract OCR → `parse_failed`. I bandi irrecuperabili vengono marcati e conservati, non scartati silenziosamente — il dato sporco è narrativa tecnica del progetto.
- **Deduplicazione hash-based senza DB complesso**: ogni bando è identificato da `hash(url + data_pubblicazione)`; il collector non reingerisce bandi già visti senza necessità di query relazionali articolate.
- **SQLite come bus tra moduli**: i moduli non si chiamano direttamente — ogni modulo scrive sul DB e il successivo legge da lì. Questo rende ogni componente sostituibile in isolamento senza toccare le interfacce degli altri.
- **Human-in-the-loop by design, non per policy**: nessun modulo ha la capacità tecnica di inviare candidature o prendere decisioni vincolanti sui requisiti di ammissione. Il disclaimer è hardcoded nel template del reporter, non opzionale.

---

## 5. Struttura cartelle dettagliata

```
concorsi-qualifier/
├── CLAUDE.md
├── pyproject.toml
│
├── config/
│   ├── sources.yaml              # lista fonti: url, tipo, frequenza, parser
│   └── profilo_candidato.yaml    # CandidatoProfilo — mai inviato a LLM cloud
│
├── data/
│   ├── raw/                      # snapshot HTML/PDF + sidecar .meta.json
│   └── processed/                # schede Markdown generate dal reporter
│
├── docs/
│   └── architecture.md           # questo documento
│
├── src/
│   ├── __init__.py
│   ├── collector/
│   │   ├── __init__.py           # espone: run_collector()
│   │   ├── crawler.py            # httpx download: tipo html/pdf/wordpress
│   │   ├── dedup.py              # hash(url + data_pubblicazione)
│   │   └── db.py                 # SQLite: tabella collector_runs
│   ├── parser/
│   │   ├── __init__.py           # espone: parse(file_path) -> ParseResult
│   │   ├── pdf_text.py           # pdfplumber / pypdf — livello 1
│   │   ├── pdf_ocr.py            # pytesseract — livello 2
│   │   └── fallback_chain.py     # orchestrazione tre livelli
│   ├── extractor/
│   │   ├── __init__.py           # espone: extract(testo, parse_method) -> Bando
│   │   ├── chain.py              # LangChain chain + retry logic
│   │   ├── prompt.py             # PromptTemplate estrazione strutturata
│   │   └── models.py             # Bando (Pydantic v2)
│   ├── matcher/
│   │   ├── __init__.py           # espone: match(bando, profilo) -> MatchResult
│   │   ├── checks.py             # check_titolo_studio, check_area, check_scadenza, ...
│   │   ├── matcher.py            # aggregate_checks() + match()
│   │   └── models.py             # CandidatoProfilo, CheckItem, MatchResult
│   ├── reporter/
│   │   ├── __init__.py           # espone: generate_report(match_result, bando) -> Path
│   │   ├── chain.py              # LangChain + Ollama: genera spiegazione
│   │   ├── prompt.py             # ChatPromptTemplate per Ollama
│   │   └── renderer.py           # assembla scheda Markdown finale
│   └── notifier/
│       ├── __init__.py           # espone: send_digest(bandi_filtrati)
│       └── digest.py             # filtro compatibilità + payload email
│
└── tests/
    ├── __init__.py
    ├── fixtures/                 # bandi reali (PDF/HTML + JSON atteso)
    ├── test_collector.py
    ├── test_parser.py
    ├── test_extractor.py
    ├── test_matcher.py
    └── test_reporter.py
```

---

## 6. Interfacce tra moduli (contratti)

Ogni modulo espone una sola funzione pubblica. Queste sono le firme target:

```python
# collector
def run_collector(sources_config: Path) -> CollectorRun: ...

# parser
def parse(file_path: Path) -> ParseResult: ...
# ParseResult = testo: str, parse_method: Literal["pdf_text","pdf_ocr","html","parse_failed"]

# extractor
def extract(testo: str, parse_method: str) -> Bando: ...

# matcher
def match(bando: Bando, profilo: CandidatoProfilo) -> MatchResult: ...

# reporter
def generate_report(match_result: MatchResult, bando: Bando) -> Path: ...

# notifier
def send_digest(bandi_filtrati: list[tuple[Bando, MatchResult]]) -> None: ...
```

L'interfaccia è minimale e stabile: cambiare l'implementazione interna di un modulo non richiede modifiche agli altri.
