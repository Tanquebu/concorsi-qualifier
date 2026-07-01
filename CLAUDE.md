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

## Modificare il workflow concorsi-digest su intake

Il workflow `concorsi-digest` gira sull'istanza n8n di **intake** (progetto separato). Per richiedere modifiche usa il sistema di change request — non modificare mai direttamente workflow n8n da questa sessione.

### Quando serve

- Il payload del notifier cambia formato
- Serve un nuovo nodo (es. split messaggi, filtro, retry)
- Cambia la logica di formattazione del digest

### Procedura

**1. Leggi lo stato attuale del workflow** (tool MCP di intake):
```
mcp__intake__n8n_get_workflow("concorsi-digest")
mcp__intake__n8n_get_node("concorsi-digest", "nome-nodo")  # per il codice completo
```

**2. Prepara il `change_spec`** — JSON con le modifiche da applicare:
```json
{
  "nodes_to_update": [
    {"name": "nome-nodo-esistente", "new_js_code": "...codice JS completo..."}
  ],
  "nodes_to_add": [
    {"name": "nuovo-nodo", "type": "n8n-nodes-base.code", "js_code": "...", "position": [x, y]}
  ],
  "connections_to_replace": {
    "nodo-sorgente": {"main": [[{"node": "nodo-target", "type": "main", "index": 0}], []]}
  },
  "position_updates": {"nodo-da-spostare": [x, y]}
}
```
Includi solo le chiavi rilevanti. Il codice JS nei nodi deve essere **completo** (non diff).

**3. Sottometti la change request**:
```
mcp__intake__submit_change_request(
  project="concorsi-qualifier",
  workflow_name="concorsi-digest",
  title="Breve descrizione",
  description="Descrizione completa del problema e della modifica",
  change_spec='{"nodes_to_update": [...]}'   # JSON come stringa
)
```
Restituisce `{ok: true, airtable_id: "rec..."}` se accettata.

**4. Monitora lo stato**:
```
mcp__intake__list_change_requests(project="concorsi-qualifier")
mcp__intake__get_change_request("rec...")
```

Pipeline: `new` → `in_progress` → `completed` | `rejected` | `error` (entro ~30 min).

### Vincoli di sicurezza (non derogabili)

- **Non chiamare mai** strumenti che modificano workflow direttamente (nessun PUT/PATCH a n8n)
- **Non toccare** workflow con nome `intake-*` — il tool `submit_change_request` li blocca server-side
- Usa `mcp__intake__n8n_get_*` **solo in lettura** per capire la struttura corrente

---

## Note operative

### Matcher — modalità incrementale

Il matcher supporta tre modalità:

| Comando | Comportamento | Quando usarlo |
|---|---|---|
| `python -m src.matcher` | ri-matcha tutti i bandi | dopo cambio profilo o checklist |
| `python -m src.matcher --incremental` | solo bandi senza match result | **default pipeline quotidiana** |
| `python -m src.matcher --bando-id <ID>` | forza (ri)match di un singolo bando | debug, inserimento manuale |

`--bando-id` ignora `--incremental` e sovrascrive sempre il risultato esistente.

La pipeline (`run_pipeline.sh`) usa `--incremental` di default.

### Inserimento manuale di bandi (già candidato)

Per aggiungere bandi scaduti a cui si è già candidati (non presenti in DB perché il collector era offline):

1. Recuperare l'ID dal link InPA (`/ui/public-area/concoursedetail/<ID>`)
2. Inserire via API InPA con `parse_method='html'`, campi lista a `'[]'`, `user_status='applicato'`
3. Impostare `ente` manualmente (l'API InPA restituisce `entiRiferimento: null` per bandi chiusi)
4. Dopo il matcher, portare `match_results.compatibilita` a `'alta'` per i bandi applicato

Il matcher `--incremental` non riprocessa questi bandi una volta inseriti. Per ricalcolarli usare `--force` (senza `--incremental`).

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
