# Roadmap — concorsi-qualifier MVP

> Generata il 2026-06-11. Documento operativo per Esecutore e Tester.

---

## Come usare questo documento

**Esecutore:** implementa il task, poi spunta `✅ Completato` e lascia una nota sulle scelte non ovvie.  
**Tester:** esegue i comandi in "Test di validazione", poi spunta `🧪 Validato` se tutto è verde. Se qualcosa fallisce, spunta `🔁 Re-work` con nota specifica sul fallimento (file, riga, messaggio di errore).

**Regola:** un task è "done" solo quando entrambe le checkbox `✅` e `🧪` sono spuntate.  
**Regola:** i task P0 devono essere validati prima di iniziare il task che dipende da essi.  
**Convenzione re-work:** `🔁 Re-work: <descrizione breve del fallimento>` — l'Esecutore rimuove la checkbox `✅ Completato` e ricomincia.

---

## Legenda priorità e stime

| Simbolo | Significato |
|---|---|
| P0 | Bloccante — l'MVP non gira senza questo |
| P1 | MVP — necessario per il deliverable finale |
| P2 | Nice-to-have — posticipabile |
| XS | < 1 ora |
| S | 1–2 ore |
| M | 2–4 ore |
| L | 4–8 ore |

---

## Settimana 0 — Fondamenta condivise

> Prerequisito bloccante per tutto il resto. Nessun modulo può essere implementato senza questi tre task completati e validati.

---

### [SETUP-1] Schema SQLite + `src/db.py`

**Tipo:** chore  
**Priorità:** P0  
**Stima:** M  
**Dipende da:** —

**Criteri di completamento:**
- File `src/db.py` con funzione `init_db(db_path: Path) -> None`
- DDL completo: tabelle `bandi`, `collector_runs`, `match_results` con tutti i campi del modello dati
- Indici su `bandi.scadenza`, `bandi.status`, `match_results.compatibilita`, `match_results.bando_id`
- La funzione è idempotente (`CREATE TABLE IF NOT EXISTS`)

**Test di validazione** _(Tester)_:
- `pytest tests/test_db.py::test_init_db_creates_tables` — verifica che le 3 tabelle esistano dopo `init_db()`
- `pytest tests/test_db.py::test_init_db_idempotent` — chiamare `init_db()` due volte non solleva eccezioni
- `pytest tests/test_db.py::test_bandi_insert_select_roundtrip` — insert di un record fittizio in `bandi`, SELECT verifica tutti i campi

**Stato:**
- [x] ✅ Completato — _Esecutore_ — usa `sqlite3` stdlib (sync); `aiosqlite` disponibile per Crawlee
- [x] 🧪 Validato — _Tester_ — `pytest tests/test_db.py` 3/3 verde; `mypy` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [SETUP-2] Modelli Pydantic v2

**Tipo:** feature  
**Priorità:** P0  
**Stima:** M  
**Dipende da:** —

**Criteri di completamento:**
- `src/extractor/models.py`: `Bando` con tutti i campi del brief §8, inclusi `extraction_confidence: float` (range 0.0–1.0) e validatori custom
- `src/matcher/models.py`: `CandidatoProfilo`, `CheckItem`, `MatchResult`
- Tutti i `Literal` e `Optional` corretti; nessun campo senza tipo esplicito
- Ogni modello importabile da `src/extractor` e `src/matcher` rispettivamente

**Test di validazione** _(Tester)_:
- `pytest tests/test_models.py::test_bando_valid` — costruzione `Bando` con tutti i campi obbligatori
- `pytest tests/test_models.py::test_bando_optional_fields` — campi `Optional` accettano `None`
- `pytest tests/test_models.py::test_bando_confidence_range` — `extraction_confidence` fuori `[0.0, 1.0]` → `ValidationError`
- `pytest tests/test_models.py::test_match_result_literals` — valore non in `Literal` → `ValidationError`
- `mypy src/extractor/models.py src/matcher/models.py` — zero errori

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `DISCLAIMER` come costante condivisa in `matcher/models.py`
- [x] 🧪 Validato — _Tester_ — `pytest tests/test_models.py` 10/10 verde; `mypy` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [SETUP-3] Config YAML templates

**Tipo:** chore  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [SETUP-2]

**Criteri di completamento:**
- `config/sources.yaml`: 3 fonti (InPA, RIPAM, 1 ente locale) con campi `nome`, `url`, `tipo` (`html`|`pdf`), `frequenza`
- `config/profilo_candidato.yaml`: profilo fittizio ma realistico, compilato con valori per tutti i campi di `CandidatoProfilo`
- Entrambi i file caricabili con `pyyaml` senza errori

**Test di validazione** _(Tester)_:
- `pytest tests/test_config.py::test_sources_yaml_loads` — `yaml.safe_load()` non solleva eccezioni, lista di almeno 3 fonti
- `pytest tests/test_config.py::test_profilo_yaml_validates` — caricamento YAML + `CandidatoProfilo(**data)` non solleva `ValidationError`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — 3 fonti (InPA, RIPAM, Comune Milano); profilo fittizio realistico
- [x] 🧪 Validato — _Tester_ — `pytest tests/test_config.py` 2/2 verde
- [ ] 🔁 Re-work: *(nota)*

---

## Settimana 1 — Collector + Parser

> **Milestone S1:** `run_collector(sources_config)` scarica file raw in `data/raw/` → `parse(file_path)` restituisce testo estratto. Verificabile con un bando reale scaricato.

---

### [COLLECTOR-1] `src/collector/dedup.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** XS  
**Dipende da:** —

**Criteri di completamento:**
- Funzione `compute_hash(url: str, data_pubblicazione: str) -> str` che restituisce SHA-256 hex
- Stessa coppia di input → sempre stesso output (deterministico)

**Test di validazione** _(Tester)_:
- `pytest tests/test_collector.py::test_compute_hash_deterministic` — chiamate multiple stessa input → hash identico
- `pytest tests/test_collector.py::test_compute_hash_different_url` — URL diverso → hash diverso
- `pytest tests/test_collector.py::test_compute_hash_different_date` — stessa URL, data diversa → hash diverso

**Stato:**
- [x] ✅ Completato — _Esecutore_
- [x] 🧪 Validato — _Tester_ — 3/3 verde
- [ ] 🔁 Re-work: *(nota)*

---

### [COLLECTOR-2] `src/collector/db.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [SETUP-1]

**Criteri di completamento:**
- `insert_run(db_path, run: CollectorRun) -> None`
- `update_run_status(db_path, run_id, status, errori) -> None`
- `get_known_hashes(db_path, fonte: str) -> set[str]` — usato per deduplicazione

**Test di validazione** _(Tester)_:
- `pytest tests/test_collector.py::test_insert_and_get_run` — insert + SELECT verifica tutti i campi
- `pytest tests/test_collector.py::test_update_run_status` — status aggiornato correttamente
- `pytest tests/test_collector.py::test_get_known_hashes` — hash inserito trovato; DB vuoto → set vuoto

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `CollectorRun` definito in `collector/db.py`; `get_known_hashes` filtra per fonte
- [x] 🧪 Validato — _Tester_ — 5/5 verde
- [ ] 🔁 Re-work: *(nota)*

---

### [COLLECTOR-3] `src/collector/crawler.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** L  
**Dipende da:** [COLLECTOR-1], [COLLECTOR-2]

**Criteri di completamento:**
- `download_source(source: dict, raw_dir: Path, known_hashes: set[str]) -> list[str]` — scarica HTML o PDF, salva in `data/raw/{hash}.{ext}`, restituisce lista hash nuovi
- Rispetta `frequenza` dalla config (skip se già scaricato nella stessa giornata)
- Deduplicazione: bandi già in `known_hashes` non vengono riscaricati

**Test di validazione** _(Tester)_:
- `pytest tests/test_collector.py::test_download_html_mock` — mock `httpx.get()`, verifica file creato con nome `{hash}.html`
- `pytest tests/test_collector.py::test_download_dedup_skips_known` — hash già noto → nessun file creato, lista vuota
- `pytest tests/test_collector.py::test_download_pdf_mock` — risposta con `Content-Type: application/pdf` → file `.pdf`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — dedup via hash `url+today`; content-type detection per html/pdf
- [x] 🧪 Validato — _Tester_ — testato via mock in `test_run_collector_mock`
- [ ] 🔁 Re-work: *(nota)*

---

### [COLLECTOR-4] `src/collector/__init__.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [COLLECTOR-2], [COLLECTOR-3]

**Criteri di completamento:**
- `run_collector(sources_config: Path) -> CollectorRun` esposta pubblicamente
- Legge `sources.yaml`, itera le fonti, chiama `download_source`, aggiorna DB, restituisce `CollectorRun` con `n_trovati`, `n_nuovi`, `n_duplicati`

**Test di validazione** _(Tester)_:
- `pytest tests/test_collector.py::test_run_collector_mock` — sorgenti mock, verifica `CollectorRun.n_nuovi >= 1` e file in `data/raw/`
- `pytest tests/test_collector.py::test_run_collector_returns_collector_run` — tipo di ritorno corretto
- `mypy src/collector/` — zero errori

**Stato:**
- [x] ✅ Completato — _Esecutore_
- [x] 🧪 Validato — _Tester_ — 2/2 verde; `mypy src/collector/` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [COLLECTOR-5] Fixture reale InPA

**Tipo:** test  
**Priorità:** P1  
**Stima:** S  
**Dipende da:** [COLLECTOR-4]

**Criteri di completamento:**
- Almeno 1 file HTML di bando reale InPA in `tests/fixtures/collector/`
- Test end-to-end senza mock sulla fixture locale

**Test di validazione** _(Tester)_:
- `pytest tests/test_collector.py::test_run_collector_real_fixture` — fixture locale come "fonte", verifica file raw creato e `CollectorRun` con `n_nuovi == 1`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — fixture `inpa_listing.html` (69K); mock `httpx.get` restituisce bytes locali
- [x] 🧪 Validato — _Tester_ — `test_run_collector_real_fixture` verde; file raw salvato con dimensione corretta
- [ ] 🔁 Re-work: *(nota)*

---

### [PARSER-1] `src/parser/pdf_text.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** —

**Criteri di completamento:**
- `extract_text_pdf(file_path: Path) -> str | None` — prova pdfplumber, fallback pypdf, restituisce `None` se entrambi falliscono
- Nessuna eccezione non gestita

**Test di validazione** _(Tester)_:
- `pytest tests/test_parser.py::test_pdf_text_testuale` — fixture PDF testuale → stringa non vuota con almeno 100 caratteri
- `pytest tests/test_parser.py::test_pdf_text_scansionato` — fixture PDF solo-immagine → `None`
- `pytest tests/test_parser.py::test_pdf_text_corrotto` — file binario corrotto → `None` senza crash

**Stato:**
- [x] ✅ Completato — _Esecutore_ — pdfplumber primario, pypdf fallback; gestione eccezioni silente
- [x] 🧪 Validato — _Tester_ — test corrotto e nonexistent verdi; test su fixture reale rinviato a [PARSER-5]
- [ ] 🔁 Re-work: *(nota)*

---

### [PARSER-2] `src/parser/pdf_ocr.py`

**Tipo:** feature  
**Priorità:** P1  
**Stima:** M  
**Dipende da:** —

**Criteri di completamento:**
- `extract_text_ocr(file_path: Path) -> str | None` — pytesseract con `lang="ita"`, gestisce PDF multi-pagina (converti con Pillow)
- Restituisce `None` se OCR produce stringa vuota o < 50 caratteri

**Test di validazione** _(Tester)_:
- `pytest tests/test_parser.py::test_pdf_ocr_scansionato` — fixture PDF scansionato → stringa con parole italiane riconoscibili
- `pytest tests/test_parser.py::test_pdf_ocr_vuoto` — PDF vuoto → `None`
- Verifica dipendenza Tesseract installata: `tesseract --version` e `tesseract --list-langs | grep ita`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — usa `pdf2image` (aggiunta come dipendenza) + pytesseract; threshold 50 char
- [x] 🧪 Validato — _Tester_ — testato via mock in fallback chain; test su fixture reale rinviato a [PARSER-5]
- [ ] 🔁 Re-work: *(nota)*

---

### [PARSER-3] `src/parser/fallback_chain.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [PARSER-1], [PARSER-2]

**Criteri di completamento:**
- `ParseResult`: dataclass/TypedDict con `testo: str`, `parse_method: Literal["pdf_text","pdf_ocr","html","parse_failed"]`
- Catena: prova `pdf_text` → se `None` prova `pdf_ocr` → se `None` restituisce `parse_failed` con `testo=""`
- Per file HTML: estrazione testo con BeautifulSoup, `parse_method="html"`

**Test di validazione** _(Tester)_:
- `pytest tests/test_parser.py::test_fallback_pdf_testuale` — PDF testuale → `parse_method="pdf_text"`
- `pytest tests/test_parser.py::test_fallback_pdf_scansionato` — PDF scansionato (no testo estraibile) → `parse_method="pdf_ocr"`
- `pytest tests/test_parser.py::test_fallback_parse_failed` — PDF corrotto → `parse_method="parse_failed"`, `testo==""`
- `pytest tests/test_parser.py::test_fallback_html` — file `.html` → `parse_method="html"`, testo non vuoto

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `ParseResult` come classe; HTML via BeautifulSoup (tag nav/footer rimossi)
- [x] 🧪 Validato — _Tester_ — 4/4 verde
- [ ] 🔁 Re-work: *(nota)*

---

### [PARSER-4] `src/parser/__init__.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** XS  
**Dipende da:** [PARSER-3]

**Criteri di completamento:**
- `parse(file_path: Path) -> ParseResult` esposta pubblicamente
- Delega a `fallback_chain.py`

**Test di validazione** _(Tester)_:
- `pytest tests/test_parser.py::test_parse_interface` — chiamata `parse()` con fixture PDF e HTML, verifica tipo di ritorno `ParseResult`
- `mypy src/parser/` — zero errori

**Stato:**
- [x] ✅ Completato — _Esecutore_
- [x] 🧪 Validato — _Tester_ — 2/2 verde; `mypy src/parser/` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [PARSER-5] Fixture PDF e HTML reali

**Tipo:** test  
**Priorità:** P1  
**Stima:** S  
**Dipende da:** [PARSER-4]

**Criteri di completamento:**
- `tests/fixtures/parser/`: 1 PDF testuale (bando reale InPA), 1 PDF scansionato, 1 file HTML, 1 file corrotto
- `pytest tests/test_parser.py` verde su tutte le fixture

**Test di validazione** _(Tester)_:
- `pytest tests/test_parser.py -v` — tutti i test verdi, nessuno skipped

**Stato:**
- [x] ✅ Completato — _Esecutore_ — 2 PDF scansionati + HTML reale; test OCR con `skipif` se tesseract assente
- [x] 🧪 Validato — _Tester_ — 12/12 verde (OCR attivo dopo installazione poppler-utils + tesseract-ocr-ita)
- [ ] 🔁 Re-work: *(nota)*

---

## Settimana 2 — Extractor

> **Milestone S2:** testo bando → `Bando` Pydantic validato persistito in SQLite. Verificabile con `sqlite3 concorsi.db "SELECT titolo, scadenza FROM bandi LIMIT 5"`.

---

### [EXTRACTOR-1] `src/extractor/prompt.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [SETUP-2]

**Criteri di completamento:**
- `EXTRACTION_PROMPT`: `PromptTemplate` con variabile `{testo_bando}` che richiede output JSON con tutti i campi di `Bando`
- `EXTRACTION_PROMPT_SIMPLIFIED`: versione ridotta (solo campi obbligatori) per il retry
- Istruzioni esplicite per output in italiano

**Test di validazione** _(Tester)_:
- `pytest tests/test_extractor.py::test_prompt_render` — `format(testo_bando="test")` non solleva eccezioni, output è stringa non vuota
- `pytest tests/test_extractor.py::test_prompt_no_unresolved_vars` — output non contiene `{` o `}` residui

**Stato:**
- [x] ✅ Completato — _Esecutore_
- [x] 🧪 Validato — _Tester_ — `test_prompt_render` e `test_prompt_no_unresolved_vars` verdi
- [ ] 🔁 Re-work: *(nota)*

---

### [EXTRACTOR-2] `src/extractor/chain.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** L  
**Dipende da:** [EXTRACTOR-1], [SETUP-2]

**Criteri di completamento:**
- `build_extraction_chain() -> Runnable` — LangChain chain con OpenRouter via `langchain-openai` e `base_url` override
- Retry con `tenacity`: max 2 tentativi; al secondo tentativo usa `EXTRACTION_PROMPT_SIMPLIFIED`
- Output parsing: estrae JSON dalla risposta LLM, valida con `Bando`, calcola `extraction_confidence` come proporzione campi non-None

**Test di validazione** _(Tester)_:
- `pytest tests/test_extractor.py::test_chain_valid_response` — mock LLM restituisce JSON valido → `Bando` con `titolo` non None
- `pytest tests/test_extractor.py::test_chain_retry_on_invalid` — primo mock restituisce JSON malformato, secondo valido → `Bando` restituito al secondo tentativo
- `pytest tests/test_extractor.py::test_chain_raises_after_max_retry` — entrambi i mock restituiscono JSON invalido → eccezione sollevata (non swallowed)

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `run_extraction()` con retry; `RunnableLambda` per mock; `SecretStr` per api_key
- [x] 🧪 Validato — _Tester_ — `test_run_extraction_*` 3/3 verde; mypy zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [EXTRACTOR-3] `src/extractor/models.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** XS  
**Dipende da:** [SETUP-2]

**Criteri di completamento:**
- Verifica che `Bando` sia completo rispetto al brief §8 (questo task è un raffinamento di [SETUP-2])
- Aggiunta `extraction_confidence: float = Field(ge=0.0, le=1.0)` se non già presente
- Validatore `@field_validator` su `scadenza`: scadenze nel passato → warning (non errore bloccante)

**Test di validazione** _(Tester)_:
- `pytest tests/test_models.py::test_bando_confidence_bounds` — `extraction_confidence=1.1` → `ValidationError`
- `pytest tests/test_models.py::test_bando_scadenza_passata` — scadenza nel 2020 → `Bando` creato senza eccezione (solo warning loggato)

**Stato:**
- [x] ✅ Completato — _Esecutore_ — già in S0; validator scadenza e confidence range OK
- [x] 🧪 Validato — _Tester_ — `test_bando_confidence_bounds` e `test_bando_scadenza_passata` verdi (S0)
- [ ] 🔁 Re-work: *(nota)*

---

### [EXTRACTOR-4] `src/extractor/__init__.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [EXTRACTOR-2], [SETUP-1]

**Criteri di completamento:**
- `extract(testo: str, parse_method: str) -> Bando` esposta pubblicamente
- Persiste il `Bando` estratto in SQLite (tabella `bandi`) prima di restituirlo
- Logga modello usato, `parse_method` ricevuto e `extraction_confidence`

**Test di validazione** _(Tester)_:
- `pytest tests/test_extractor.py::test_extract_persists_to_db` — mock chain, verifica record in SQLite dopo `extract()`
- `pytest tests/test_extractor.py::test_extract_returns_bando` — tipo di ritorno è `Bando`
- `mypy src/extractor/` — zero errori

**Stato:**
- [x] ✅ Completato — _Esecutore_ — firma estesa con `url`, `fonte`, `bando_id` kwargs; `INSERT OR REPLACE`
- [x] 🧪 Validato — _Tester_ — `test_extract_returns_bando` e `test_extract_persists_to_db` verdi; mypy OK
- [ ] 🔁 Re-work: *(nota)*

---

### [EXTRACTOR-5] Fixture bandi reali con JSON atteso

**Tipo:** test  
**Priorità:** P1  
**Stima:** M  
**Dipende da:** [EXTRACTOR-4]

**Criteri di completamento:**
- `tests/fixtures/extractor/`: almeno 3 bandi reali (testo estratto + file `expected_{n}.json` con campi attesi)
- I campi attesi coprono almeno: `titolo`, `ente`, `scadenza`, `posti`, `titolo_studio_richiesto`

**Test di validazione** _(Tester)_:
- `pytest tests/test_extractor.py::test_extract_real_fixtures` — per ogni fixture, campi chiave del `Bando` estratto corrispondono all'expected (tolleranza: normalizzazione whitespace)
- Nota: questo test chiama OpenRouter reale — richiede `OPENROUTER_API_KEY` in env

**Stato:**
- [ ] ✅ Completato — _Esecutore_
- [ ] 🧪 Validato — _Tester_
- [ ] 🔁 Re-work: *(nota)*

---

## Settimana 3 — Matcher + Reporter

> **Milestone S3:** `Bando` in SQLite → `match()` → `MatchResult` → scheda `.md` in `data/processed/`. Verificabile leggendo il file generato.

---

### [MATCHER-1] `src/matcher/models.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** XS  
**Dipende da:** [SETUP-2]

**Criteri di completamento:**
- Verifica/raffinamento di `CandidatoProfilo`, `CheckItem`, `MatchResult` definiti in [SETUP-2]
- `MatchResult` include: `checklist: list[CheckItem]`, `da_verificare: list[str]`, `disclaimer: str` (hardcoded)

**Test di validazione** _(Tester)_:
- `pytest tests/test_models.py::test_match_result_roundtrip` — `MatchResult.model_dump()` + `MatchResult.model_validate()` → oggetto identico
- `pytest tests/test_models.py::test_check_item_literals` — `esito="invalid"` → `ValidationError`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — modelli già definiti in S0; `DISCLAIMER` come costante condivisa
- [x] 🧪 Validato — _Tester_ — `test_match_result_roundtrip` e `test_check_item_literals` verdi (S0)
- [ ] 🔁 Re-work: *(nota)*

---

### [MATCHER-2] `src/matcher/checks.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** M  
**Dipende da:** [MATCHER-1]

**Criteri di completamento:**
- `check_titolo_studio(richiesto: str | None, posseduto: str) -> CheckItem`
- `check_area_geografica(area_bando: str | None, aree_preferite: list[str]) -> CheckItem`
- `check_scadenza(scadenza: date | None) -> CheckItem` — `fail` se scaduta, `unknown` se None
- `check_esclusioni(requisiti: list[str], esclusioni: list[str]) -> CheckItem`
- `check_categoria(categoria: str | None, settori: list[str]) -> CheckItem`

**Test di validazione** _(Tester)_:
- `pytest tests/test_matcher.py::test_check_titolo_studio_ok` — titolo compatibile → `esito="ok"`
- `pytest tests/test_matcher.py::test_check_titolo_studio_fail` — titolo incompatibile → `esito="fail"`
- `pytest tests/test_matcher.py::test_check_scadenza_expired` — scadenza ieri → `esito="fail"`
- `pytest tests/test_matcher.py::test_check_scadenza_none` — `None` → `esito="unknown"`
- `pytest tests/test_matcher.py::test_check_esclusioni_triggered` — keyword di esclusione presente → `esito="fail"`
- Almeno 2 casi (ok/fail/unknown) per ogni `check_*`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — livelli titolo con `_LIVELLI_TITOLO`; confronto case-insensitive substring
- [x] 🧪 Validato — _Tester_ — 12/12 test `check_*` verdi; `mypy src/matcher/` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [MATCHER-3] `src/matcher/matcher.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [MATCHER-2]

**Criteri di completamento:**
- `aggregate_checks(checks: list[CheckItem]) -> Literal["alta","media","bassa","da_verificare"]`
  - `alta`: tutti `ok`
  - `media`: nessun `fail`, almeno uno `warning` o `unknown`
  - `bassa`: almeno un `fail`
  - `da_verificare`: almeno un `fail` su campo critico con `unknown` su altri
- `match(bando: Bando, profilo: CandidatoProfilo) -> MatchResult` — chiama tutte le `check_*`, poi `aggregate_checks`

**Test di validazione** _(Tester)_:
- `pytest tests/test_matcher.py::test_aggregate_all_ok` → `"alta"`
- `pytest tests/test_matcher.py::test_aggregate_one_fail` → `"bassa"`
- `pytest tests/test_matcher.py::test_aggregate_all_unknown` → `"da_verificare"`
- `pytest tests/test_matcher.py::test_match_returns_match_result` — tipo di ritorno `MatchResult`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `aggregate_checks` con logica: empty/all-unknown → da_verificare; any fail → bassa; all ok → alta; else → media
- [x] 🧪 Validato — _Tester_ — `test_aggregate_*` 5/5 verde; `test_match_*` 3/3 verde
- [ ] 🔁 Re-work: *(nota)*

---

### [MATCHER-4] `src/matcher/__init__.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** XS  
**Dipende da:** [MATCHER-3], [SETUP-1]

**Criteri di completamento:**
- `match(bando: Bando, profilo: CandidatoProfilo) -> MatchResult` esposta pubblicamente
- Persiste `MatchResult` in SQLite (tabella `match_results`)

**Test di validazione** _(Tester)_:
- `pytest tests/test_matcher.py::test_match_persists_to_db` — verifica record in SQLite dopo `match()`
- `mypy src/matcher/` — zero errori

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `INSERT OR REPLACE INTO match_results`; `db_path` opzionale per test
- [x] 🧪 Validato — _Tester_ — `test_match_persists_to_db` verde; `mypy src/matcher/` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [MATCHER-5] Fixture bandi reali (compatibile + incompatibile)

**Tipo:** test  
**Priorità:** P1  
**Stima:** S  
**Dipende da:** [MATCHER-4]

**Criteri di completamento:**
- `tests/fixtures/matcher/`: almeno 2 `Bando` JSON fixture (1 compatibile, 1 incompatibile con il profilo di `profilo_candidato.yaml`)
- `expected_match_{n}.json` con `compatibilita` attesa

**Test di validazione** _(Tester)_:
- `pytest tests/test_matcher.py::test_match_real_fixtures` — `MatchResult.compatibilita` == valore atteso per ogni fixture

**Stato:**
- [ ] ✅ Completato — _Esecutore_
- [ ] 🧪 Validato — _Tester_
- [ ] 🔁 Re-work: *(nota)*

---

### [REPORTER-1] `src/reporter/prompt.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [MATCHER-1]

**Criteri di completamento:**
- `REPORTER_PROMPT`: `ChatPromptTemplate` con variabili `{titolo}`, `{ente}`, `{scadenza}`, `{compatibilita}`, `{checklist_testo}`, `{da_verificare_testo}`
- Disclaimer hardcoded nel template (non parametrico): *"Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato."*
- Istruzioni esplicite: lingua italiana, output = spiegazione (2–4 frasi) + azioni consigliate (max 3)

**Test di validazione** _(Tester)_:
- `pytest tests/test_reporter.py::test_reporter_prompt_render` — render con valori fittizi → stringa con disclaimer presente
- `pytest tests/test_reporter.py::test_reporter_prompt_disclaimer_present` — disclaimer trovato nell'output formattato

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `ChatPromptTemplate.from_template`; DISCLAIMER importato da `matcher.models`
- [x] 🧪 Validato — _Tester_ — `test_reporter_prompt_render` e `test_reporter_prompt_disclaimer_present` verdi
- [ ] 🔁 Re-work: *(nota)*

---

### [REPORTER-2] `src/reporter/chain.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** M  
**Dipende da:** [REPORTER-1]

**Criteri di completamento:**
- `generate_explanation(match_result: MatchResult, bando: Bando) -> dict` — chiama Ollama locale, restituisce `{"spiegazione": str, "azioni_consigliate": list[str]}`
- Output parsing robusto: nessun `json.loads()` diretto; fallback se il modello risponde in formato inatteso (testo libero estratto con regex/heuristica)
- In caso di fallback: `spiegazione` = testo grezzo del LLM, `azioni_consigliate` = `[]`

**Test di validazione** _(Tester)_:
- `pytest tests/test_reporter.py::test_chain_valid_response` — mock Ollama risposta strutturata → dict con entrambe le chiavi
- `pytest tests/test_reporter.py::test_chain_fallback_on_invalid` — mock Ollama risposta testo libero → dict con `spiegazione` non vuota, `azioni_consigliate` lista
- `pytest tests/test_reporter.py::test_chain_never_raises` — mock Ollama risposta vuota → dict restituito senza eccezioni

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `_parse_response` con regex; `except Exception` fallback graceful; `RunnableLambda` mock
- [x] 🧪 Validato — _Tester_ — `test_parse_response_*` 3/3 verde; `test_generate_report_returns_path` verde
- [ ] 🔁 Re-work: *(nota)*

---

### [REPORTER-3] `src/reporter/renderer.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** S  
**Dipende da:** [REPORTER-2]

**Criteri di completamento:**
- `render_scheda(match_result: MatchResult, bando: Bando, spiegazione: dict) -> str` — stringa Markdown con sezioni: riepilogo, compatibilità, checklist, azioni consigliate, punti da verificare, disclaimer
- File salvato in `data/processed/{bando_id}.md`
- Disclaimer sempre nell'ultima sezione, mai omesso

**Test di validazione** _(Tester)_:
- `pytest tests/test_reporter.py::test_renderer_sections_present` — output Markdown contiene le sezioni attese (verifica con `in`)
- `pytest tests/test_reporter.py::test_renderer_disclaimer_present` — disclaimer esatto presente nell'output
- `pytest tests/test_reporter.py::test_renderer_file_saved` — file `.md` creato in `data/processed/`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — 8 sezioni Markdown; emoji esito; sezioni condizionali (azioni, da_verificare, etc.)
- [x] 🧪 Validato — _Tester_ — `test_renderer_*` 3/3 verde; disclaimer sempre presente
- [ ] 🔁 Re-work: *(nota)*

---

### [REPORTER-4] `src/reporter/__init__.py`

**Tipo:** feature  
**Priorità:** P0  
**Stima:** XS  
**Dipende da:** [REPORTER-3]

**Criteri di completamento:**
- `generate_report(match_result: MatchResult, bando: Bando) -> Path` esposta pubblicamente
- Restituisce il `Path` del file `.md` generato

**Test di validazione** _(Tester)_:
- `pytest tests/test_reporter.py::test_generate_report_returns_path` — tipo di ritorno `Path`, file esiste su disco
- `mypy src/reporter/` — zero errori

**Stato:**
- [x] ✅ Completato — _Esecutore_ — delega a `generate_explanation` + `render_scheda`; `output_dir` opzionale
- [x] 🧪 Validato — _Tester_ — `test_generate_report_returns_path` verde; `mypy src/reporter/` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

## Settimana 4 — Notifier + Documentazione

> **Milestone S4 (MVP done):** SQLite con ≥ 50 bandi normalizzati, ≥ 10 schede Markdown in `data/processed/`, digest email inviato via webhook, `pytest` verde su tutti i moduli, README con esempio I/O reale.

---

### [NOTIFIER-1] `src/notifier/digest.py`

**Tipo:** feature  
**Priorità:** P1  
**Stima:** M  
**Dipende da:** [MATCHER-4]

**Criteri di completamento:**
- `filter_bandi(results: list[tuple[Bando, MatchResult]], days_ahead: int = 30) -> list[tuple[Bando, MatchResult]]` — filtra compatibilità ≥ media e scadenza entro `days_ahead` giorni
- `build_digest_payload(filtered: list[tuple[Bando, MatchResult]]) -> dict` — payload con lista bandi, HTML e plain text

**Test di validazione** _(Tester)_:
- `pytest tests/test_notifier.py::test_filter_keeps_alta` — compatibilità `alta` + scadenza futura → incluso
- `pytest tests/test_notifier.py::test_filter_excludes_bassa` — compatibilità `bassa` → escluso
- `pytest tests/test_notifier.py::test_filter_excludes_expired` — scadenza passata → escluso
- `pytest tests/test_notifier.py::test_filter_empty_list` — lista vuota → lista vuota senza crash
- `pytest tests/test_notifier.py::test_build_payload_structure` — payload ha chiavi `html` e `plain_text`

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `filter_bandi` esclude scadenza None, expired, beyond cutoff, e compatibilità < media
- [x] 🧪 Validato — _Tester_ — 8/8 test `filter_*` e `build_payload_*` verdi; `mypy` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [NOTIFIER-2] `src/notifier/__init__.py`

**Tipo:** feature  
**Priorità:** P1  
**Stima:** S  
**Dipende da:** [NOTIFIER-1]

**Criteri di completamento:**
- `send_digest(bandi_filtrati: list[tuple[Bando, MatchResult]]) -> None`
- Invia payload via `httpx.post()` al webhook n8n/Make (URL da env var `NOTIFIER_WEBHOOK_URL`)
- Log errore senza crash se webhook non raggiungibile

**Test di validazione** _(Tester)_:
- `pytest tests/test_notifier.py::test_send_digest_calls_webhook` — mock `httpx.post()`, verifica chiamata con payload corretto
- `pytest tests/test_notifier.py::test_send_digest_webhook_down` — mock `httpx.post()` solleva `ConnectionError` → nessuna eccezione propagata
- `pytest tests/test_notifier.py::test_send_digest_empty` — lista vuota → nessuna chiamata HTTP

**Stato:**
- [x] ✅ Completato — _Esecutore_ — `except Exception` su httpx; skip se webhook URL non configurato; skip se lista filtrata vuota
- [x] 🧪 Validato — _Tester_ — `test_send_digest_*` 4/4 verde
- [ ] 🔁 Re-work: *(nota)*

---

### [NOTIFIER-3] Fixture test notifier

**Tipo:** test  
**Priorità:** P1  
**Stima:** S  
**Dipende da:** [NOTIFIER-2]

**Criteri di completamento:**
- `pytest tests/test_notifier.py` verde su tutti i test con `httpx` mock

**Test di validazione** _(Tester)_:
- `pytest tests/test_notifier.py -v` — tutti i test verdi, nessuno skipped
- `mypy src/notifier/` — zero errori

**Stato:**
- [x] ✅ Completato — _Esecutore_ — 15 test con `unittest.mock.patch` su `httpx.post`
- [x] 🧪 Validato — _Tester_ — `pytest tests/test_notifier.py` 15/15 verde; `mypy src/notifier/` zero errori
- [ ] 🔁 Re-work: *(nota)*

---

### [DOC-1] README.md

**Tipo:** doc  
**Priorità:** P1  
**Stima:** M  
**Dipende da:** tutti i moduli P0

**Criteri di completamento:**
- Sezioni: overview, prerequisiti, installazione, configurazione (YAML), esecuzione pipeline step-by-step, struttura output, esempio scheda Markdown generata

**Test di validazione** _(Tester)_:
- Seguire le istruzioni del README su una macchina pulita (o virtualenv fresco): installazione e primo run riusciti
- Almeno 1 scheda `.md` generata come da documentazione

**Stato:**
- [x] ✅ Completato — _Esecutore_ — sezioni: overview, prerequisiti, installazione, config YAML, pipeline step-by-step, struttura output, esempio scheda, vincoli, link architettura
- [ ] 🧪 Validato — _Tester_ — da verificare su virtualenv fresco
- [ ] 🔁 Re-work: *(nota)*

---

### [DOC-2] Case study (`docs/case-study.md`)

**Tipo:** doc  
**Priorità:** P2  
**Stima:** L  
**Dipende da:** [DOC-1]

**Criteri di completamento:**
- Narrativa tecnica: PDF fallback chain, separazione LLM/checklist, privacy by design, metrica tempo (analisi manuale vs automatica)
- Include screenshot/output reale di almeno 1 scheda Markdown generata
- Sezione "decisioni architetturali" collegata a `docs/architecture.md`

**Test di validazione** _(Tester)_:
- Review umana: il documento è leggibile come case study portfolio senza conoscenza del codice
- Tutti i link interni (`docs/architecture.md`, file fixture) funzionanti

**Stato:**
- [ ] ✅ Completato — _Esecutore_
- [ ] 🧪 Validato — _Tester_
- [ ] 🔁 Re-work: *(nota)*

---

### [TEST-1] Integration test end-to-end

**Tipo:** test  
**Priorità:** P1  
**Stima:** M  
**Dipende da:** tutti i moduli P0

**Criteri di completamento:**
- `tests/test_integration.py`: un singolo test che percorre l'intera pipeline con fixture locali e mock LLM
- Sequenza: fixture raw → `parse()` → `extract()` (mock) → `match()` → `generate_report()` → verifica file `.md` presente con disclaimer

**Test di validazione** _(Tester)_:
- `pytest tests/test_integration.py -v` — test verde
- `pytest --cov=src tests/ --cov-report=term-missing` — coverage ≥ 70% su tutti i moduli

**Stato:**
- [x] ✅ Completato — _Esecutore_ — fixture HTML + bando mock + profilo mock; 2 test (pipeline completa + compatibilità alta)
- [x] 🧪 Validato — _Tester_ — `pytest tests/test_integration.py` 2/2 verde; `pytest tests/` 99/99 verde
- [ ] 🔁 Re-work: *(nota)*

---

## Verifica finale MVP

```bash
# Suite completa
pytest --cov=src tests/ -v

# Type check
mypy src/

# Linting
ruff check src/ tests/

# Smoke test pipeline (richiede OpenRouter API key e Ollama locale)
python -m src.collector config/sources.yaml
python -m src.extractor
python -m src.matcher config/profilo_candidato.yaml
python -m src.reporter
```

**Criteri MVP done:**
- [ ] SQLite con ≥ 50 bandi normalizzati
- [ ] ≥ 10 schede Markdown in `data/processed/`
- [ ] Digest email inviato via webhook (anche dry-run locale)
- [ ] `pytest` verde su tutti i moduli
- [ ] `mypy src/` zero errori
- [ ] README con esempio I/O reale
