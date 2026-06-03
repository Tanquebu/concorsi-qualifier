# Public Concorsi Intelligence — Project Brief

> Merge di: `ai-concorsi.md`, `public-career-intelligence-prompt.md`, `proposta-mvp-focalizzato.md`

---

## 1. Overview

**Nome provvisorio:** `concorsi-qualifier` (tecnico/funzionale) — `Public Concorsi Intelligence` (portfolio)

**Sottotitolo:** AI-powered monitoring and qualification system for Italian public job competitions.

**Posizionamento:** non un'app consumer per "trovare concorsi", ma un sistema AI applicabile a contesti organizzativi che supportano candidati. Il progetto dimostra capacità di progettare soluzioni AI controllate, modulari e utili a un processo organizzativo reale, con attenzione a privacy, costi, qualità dell'output e verifica umana.

---

## 2. Problema reale

I concorsi pubblici e i bandi per opportunità lavorative nella PA sono difficili da monitorare e interpretare:

- fonti distribuite su decine di portali (InPA, RIPAM, regioni, comuni, enti);
- bandi pubblicati in PDF lunghi, spesso scansionati, con layout irregolari;
- requisiti formali non sempre immediati da leggere;
- scadenze sparse, aggiornamenti successivi al bando originale;
- difficoltà nel capire rapidamente se vale la pena candidarsi.

Il sistema riduce il costo cognitivo e operativo della prima qualificazione. Non sostituisce la verifica umana o legale: offre una **prima analisi assistita**.

---

## 3. Target d'uso (B2B)

Il sistema non è pensato per il singolo candidato consumer, ma per organizzazioni che gestiscono candidati:

- enti di formazione e centri per l'impiego;
- career service universitari;
- agenzie per il lavoro;
- CAF e patronati;
- società di outplacement;
- associazioni di categoria che segnalano opportunità agli iscritti.

In questi contesti, il sistema gira su profili multipli e produce digest periodici, non ricerche manuali one-shot.

---

## 4. Scope MVP — dentro e fuori

### Dentro l'MVP

- Raccolta automatica da 3–5 fonti pubbliche selezionate
- Parsing HTML + PDF (con fallback chain, vedi §7)
- Estrazione strutturata dei campi chiave del bando via LLM
- Validazione schema con Pydantic
- Matching strutturato tra bando e profilo candidato (checklist deterministica)
- Generazione scheda bando in Markdown con esito match e spiegazione
- Deduplicazione bandi già visti
- Alert periodico via email (n8n/Make)

### Fuori dall'MVP (Variante 2 e 3)

| Feature | Variante |
|---|---|
| Piano di studio personalizzato per bando | V2 |
| Quiz e domande simulate su materie d'esame | V2 |
| RAG su documenti normativi collegati | V2 |
| Dashboard visuale (Streamlit) | V2 |
| Gestione multi-candidato | V3 |
| API esterna per integrazione con altri sistemi | V3 |
| Invio automatico candidature | mai — human-in-the-loop |

---

## 5. Architettura

```
[Sources: InPA, RIPAM, 2–3 enti/portali locali]
        ↓
[Collector — Crawlee (Python)]
        ↓
[Raw Store — file system + SQLite (hash-based dedup)]
        ↓
[Parser — PDF fallback chain: text → OCR → skip+flag]
        ↓
[Extractor — LangChain + LLM → JSON validato Pydantic]
        ↓
[Structured Data Store — SQLite]
        ↓
[Matcher — checklist deterministica vs CandidatoProfilo]
        ↓
[Reporter — scheda Markdown per bando]
        ↓
[Notifier — n8n/Make: digest email settimanale]
```

Separazione dei moduli: ogni componente è indipendente e sostituibile. Il pipeline è sequenziale per il MVP; può diventare asincrono (code-based) in V2.

---

## 6. Stack — scelte fisse e opzionali

### Obbligatori

| Componente | Scelta | Motivazione |
|---|---|---|
| Linguaggio | Python 3.11+ | Ecosistema AI nativo |
| Scraping | Crawlee (Python SDK) | Open source, no vendor lock-in vs Apify cloud |
| Orchestrazione LLM | LangChain | Chain + structured output parser |
| LLM estrazione bandi | OpenRouter (Mistral/Gemma 2) | Dati pubblici, costo basso, no privacy issue |
| LLM matching profilo | Ollama locale (Llama 3.1 / Mistral) | Il profilo candidato è dato privato |
| Validazione output | Pydantic v2 | Schema fisso, campo `_extraction_confidence` |
| Storage | SQLite + file system | Zero infrastruttura, sufficiente per MVP |
| PDF text extraction | pdfplumber / pypdf | Librerie mature |
| PDF OCR fallback | pytesseract + Tesseract (ita) | Gestione bandi scansionati |

### Opzionali per MVP, utili per V2

| Componente | Uso |
|---|---|
| n8n self-hosted o Make | Scheduling + alert email |
| ChromaDB o FAISS | RAG su documenti normativi (V2) |
| Streamlit | Dashboard (V2) |
| PostgreSQL | Scaling multi-tenant (V3) |
| E2B / Modal | Sandbox agente (V3) |

---

## 7. Moduli funzionali

### 7.1 Collector

- Scarica pagine HTML e PDF da fonti configurate
- Salva snapshot su file system con timestamp
- Calcola hash dell'URL + data per deduplicazione
- Registra ogni run in SQLite (fonte, data, status, n_bandi trovati)

### 7.2 Parser — PDF fallback chain

Tre livelli in cascata:

1. **PDF testuale** — `pdfplumber` o `pypdf`: estrazione diretta, veloce
2. **PDF scansionato** — `pytesseract` + Tesseract lingua italiana: OCR su immagine
3. **Fallback** — bando marcato `status: parse_failed`, incluso nel log, escluso dal matching automatico ma conservato per revisione manuale

Il metodo usato viene salvato nel campo `parse_method` del record. Questo è il punto tecnico più narrativo del case study: non il LLM, ma la gestione del dato sporco.

### 7.3 Extractor

- LangChain chain: testo bando → prompt strutturato → output JSON
- LLM: OpenRouter (dati pubblici, no privacy concern)
- Validazione con Pydantic v2: campo obbligatorio / opzionale / `_extraction_confidence`
- Retry con prompt semplificato se la validazione fallisce
- Logging di ogni estrazione con modello usato e confidence media

### 7.4 Matcher

Il matching è **deterministico via checklist**, non qualitativo via LLM:

```python
def match(bando: Bando, profilo: CandidatoProfilo) -> MatchResult:
    checks = []
    checks.append(check_titolo_studio(bando.titolo_studio_richiesto, profilo.titolo_studio))
    checks.append(check_area_geografica(bando.area_geografica, profilo.aree_preferite))
    checks.append(check_scadenza(bando.scadenza))
    checks.append(check_esclusioni(bando.requisiti_formali, profilo.esclusioni))
    checks.append(check_categoria(bando.categoria, profilo.settori))
    return aggregate_checks(checks)
```

L'LLM interviene **solo** per:
1. generare la spiegazione testuale del risultato checklist (nel Reporter)
2. segnalare punti ambigui o da verificare manualmente

Non prende decisioni di matching. Questo è il punto architetturale chiave del case study.

Esito possibile: `alta | media | bassa | da_verificare`

### 7.5 Reporter

Per ogni bando genera una scheda Markdown con:

- riepilogo concorso (ente, posti, sede, scadenza)
- compatibilità con profilo (esito + checklist dettagliata)
- requisiti formali estratti
- materie d'esame
- documenti richiesti
- azioni consigliate
- punti da verificare manualmente
- disclaimer: *"Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato."*

### 7.6 Notifier

- Trigger: run settimanale schedulato (n8n/Make cron)
- Input: bandi nuovi o in scadenza entro N giorni con compatibilità ≥ media
- Output: digest email in plain text o HTML con lista schede + link fonte originale

---

## 8. Modello dati

### `Bando`

```python
class Bando(BaseModel):
    id: str                          # hash(url + data_pubblicazione)
    fonte: str                       # es. "inpa.gov.it"
    url: str
    titolo: str
    ente: str
    categoria: Optional[str]
    area_geografica: Optional[str]
    posti: Optional[int]
    scadenza: Optional[date]
    titolo_studio_richiesto: Optional[str]
    requisiti_formali: list[str]
    materie_esame: list[str]
    tassa_concorso: Optional[float]
    link_candidatura: Optional[str]
    documenti_richiesti: list[str]
    testo_raw: str
    parse_method: Literal["pdf_text", "pdf_ocr", "html", "parse_failed"]
    _extraction_confidence: float    # 0.0–1.0, media sui campi estratti
    status: Literal["ok", "parse_failed", "expired", "duplicate"]
    created_at: datetime
```

### `CandidatoProfilo`

```python
class CandidatoProfilo(BaseModel):
    nome: str
    titolo_studio: str               # es. "Laurea magistrale LM-77"
    aree_preferite: list[str]        # es. ["Milano", "Lombardia", "remoto"]
    settori: list[str]               # es. ["informatica", "sistemi informativi"]
    anni_esperienza: Optional[int]
    parole_chiave: list[str]
    esclusioni: list[str]            # categorie o requisiti che escludono automaticamente
```

### `MatchResult`

```python
class CheckItem(BaseModel):
    requisito: str
    esito: Literal["ok", "warning", "fail", "unknown"]
    nota: Optional[str]

class MatchResult(BaseModel):
    bando_id: str
    profilo_nome: str
    compatibilita: Literal["alta", "media", "bassa", "da_verificare"]
    checklist: list[CheckItem]
    da_verificare: list[str]
    spiegazione: str                 # generata da LLM locale
    disclaimer: str
    created_at: datetime
```

---

## 9. Privacy by design

| Dato | Classificazione | LLM consentito |
|---|---|---|
| Testo bando (pubblico) | Pubblico | OpenRouter OK |
| URL, ente, scadenza | Pubblico | OpenRouter OK |
| Profilo candidato | Privato | Solo Ollama locale |
| Match result (unisce i due) | Privato | Solo Ollama locale |

Il profilo candidato non entra mai in un LLM cloud. La separazione è architetturale, non solo di configurazione.

Audit trail: ogni estrazione e ogni match vengono loggati con modello usato, timestamp e confidence. Il report indica quali campi sono stati estratti automaticamente vs inseriti manualmente.

---

## 10. Definizione MVP

**Input:** file YAML con 1 profilo candidato + lista di 3–5 fonti configurate

**Output:**
- Database SQLite con 50–100 bandi normalizzati
- Schede Markdown per i top 10 bandi per compatibilità
- Digest email settimanale (n8n/Make)
- README + diagramma architetturale + esempi I/O

**Non serve:** UI, login, multi-tenant, API esterna

---

## 11. Timeline — 4 settimane part-time

| Settimana | Focus | Deliverable |
|---|---|---|
| 1 | Collector + Parser | Script funzionante su 3 fonti, fallback chain operativa, 30+ bandi in SQLite |
| 2 | Extractor | Pipeline LangChain → JSON validato su 50+ bandi reali, log confidence |
| 3 | Matcher + Reporter | Checklist match su profilo fisso, schede Markdown generate |
| 4 | Notifier + documentazione | Email digest via n8n, README, diagramma, esempi I/O, sezione case study |

La settimana 4 è interamente dedicata alla documentazione: il case study è il deliverable principale, non il codice.

---

## 12. Vincoli non negoziabili

- Nessun invio automatico di candidature — human-in-the-loop sempre
- Disclaimer chiaro su ogni output: l'analisi è assistita, la verifica finale è umana
- Nessuna consulenza legale automatica sui requisiti di ammissione
- Rispetto dei termini di servizio delle fonti scraped
- Il profilo candidato non esce mai dalla macchina locale

---

## 13. Cosa raccontare nel case study

**Narrativa principale:** ho progettato un sistema AI controllato che separa estrazione (LLM), decisione (logica deterministica) e spiegazione (LLM locale). Non "ho usato LangChain", ma "ho scelto dove il LLM aiuta e dove non deve decidere".

**Punti tecnici da sviluppare:**
1. PDF fallback chain — dato sporco reale, non demo su PDF puliti
2. Separazione LLM vs checklist nel matching — output auditabile e riproducibile
3. Privacy by design — profilo privato mai su cloud, scelta architetturale difendibile
4. Modularità — ogni modulo sostituibile senza toccare gli altri

**Metrica principale:** tempo analisi manuale di un bando (20–40 min) vs scheda automatica (< 2 min). Non perfetta: attendibile come prima qualificazione assistita.

---

## 14. Varianti future

| Variante | Aggiunge | Stack aggiuntivo |
|---|---|---|
| V2 — Prep Assistant | Piano di studio + domande simulate per bando scelto | RAG su regolamenti, ChromaDB |
| V3 — B2B2C Platform | Multi-candidato, dashboard, API | PostgreSQL, Streamlit/FastAPI, autenticazione |
