# Case study — Public Concorsi Intelligence

> Sistema AI modulare per il monitoraggio e la qualificazione automatica di bandi di concorso pubblico italiani.

---

## Il problema

Candidarsi ai concorsi pubblici in Italia richiede un lavoro di monitoraggio continuo e dispersivo. Le fonti sono almeno una decina (InPA, RIPAM, siti di singoli enti), i bandi arrivano in formati eterogenei — HTML, PDF testuale, PDF scansionato — e ogni candidato deve valutare manualmente se possiede i requisiti prima ancora di decidere se approfondire.

Per un profilo tecnico (es. informatico con laurea magistrale LM-18) il processo tipico è:

1. Aprire 5–10 portali ogni settimana
2. Leggere titolo e requisiti di 20–40 bandi
3. Scartare quelli non pertinenti (area geografica sbagliata, titolo di studio non soddisfatto, settore non affine)
4. Approfondire i 3–5 rimanenti

Stimando 3–5 minuti per bando, si arriva a **1–3 ore settimanali** di lavoro ripetitivo, a bassa intensità cognitiva ma ad alta attenzione — il tipo di task che si presta all'automazione.

Ho progettato un sistema a sei moduli (`collector → parser → extractor → matcher → reporter → notifier`) che copre l'intero percorso dal download al digest email. Ogni modulo ha una sola responsabilità, un'interfaccia pubblica minimale, e comunica con gli altri tramite SQLite — non tramite chiamate dirette. Questo rende ogni componente sostituibile in isolamento. Il tempo di analisi scende da **3–5 minuti** a **< 5 secondi** per bando; il controllo finale resta al candidato.

---

## Tre decisioni architetturali che vale la pena raccontare

### 1. Il LLM non decide mai il match

La scelta più importante del progetto non è tecnologica, è di principio.

Ho progettato il matching tra bando e profilo candidato come un processo interamente deterministico: cinque funzioni Python puro (`check_titolo_studio`, `check_area_geografica`, `check_scadenza`, `check_esclusioni`, `check_categoria`) producono una checklist di `CheckItem`, ognuno con esito `ok | warning | fail | unknown`. L'aggregazione segue una regola esplicita:

- tutti `ok` → `alta`
- almeno un `fail` → `bassa`
- mix `ok`/`warning` → `media`
- tutto `unknown` → `da_verificare`

Il LLM locale (Ollama) entra in scena solo *dopo* che la decisione è già stata presa, per generare la spiegazione testuale in linguaggio naturale. Non può alterare l'esito.

**Perché conta:** l'output è auditabile e riproducibile indipendentemente dal modello disponibile. Sostituire `llama3.1` con `mistral` non cambia di una virgola quale bando viene classificato `alta` e quale `bassa`.

---

### 2. La PDF fallback chain a tre livelli

I bandi di concorso pubblico arrivano in tre forme, spesso imprevedibili:

| Tipo | Frequenza | Soluzione |
|---|---|---|
| PDF testuale (layer di testo incorporato) | ~60% | `pdfplumber` / `pypdf` |
| PDF scansionato (immagine) | ~30% | `pytesseract` + Tesseract OCR (lingua `ita`) + `pdf2image` |
| HTML della pagina del bando | ~10% | `BeautifulSoup` + pulizia nav/footer |

Ho scelto una chain lineare: si prova `pdf_text`, se restituisce meno di 50 caratteri si passa a `pdf_ocr`, se anche quello fallisce il bando viene marcato come `parse_failed` — non scartato, ma conservato per revisione manuale con `status = "parse_failed"` in SQLite.

Questa scelta — *fallire visibilmente invece di fallire silenziosamente* — ha un costo (qualche bando richiede intervento manuale) ma elimina la categoria peggiore di bug: quelli invisibili dove il sistema sembra funzionare ma perde dati.

---

### 3. Privacy by design — strutturale, non configurabile

Il profilo del candidato (nome, titolo di studio, aree preferite, parole chiave) è il dato più sensibile del sistema. Ho scelto che **non possa fisicamente raggiungere un LLM cloud**, non per policy ma per costruzione del codice.

Ho separato i due LLM con ruoli distinti:

| Modulo | LLM | Dati che riceve |
|---|---|---|
| `extractor` | OpenRouter (cloud) | Solo testo pubblico del bando |
| `reporter` | Ollama (locale) | Checklist anonimizzata + esito aggregato |

Il `matcher` — l'unico modulo che vede sia il `Bando` che il `CandidatoProfilo` — non chiama nessun LLM. Il profilo non esce dalla macchina locale in nessun punto del flusso normale.

Questa separazione non è un flag di configurazione: non esiste un `use_cloud=True` da passare al reporter.

---

## Esempio di output

Per un bando informatico del Comune di Milano, compatibile con un profilo LM-18:

```markdown
# Concorso pubblico – n. 3 posti di Informatico cat. D

## Riepilogo
- **Ente:** Comune di Milano — **Posti:** 3 — **Scadenza:** 2026-12-31

## Compatibilità: ALTA
- ✅ Titolo di studio — ✅ Area geografica — ✅ Scadenza — ✅ Categoria

Il bando è compatibile su tutti i criteri verificabili automaticamente.
Il titolo LM-18 soddisfa il requisito, l'area è tra quelle preferite,
la scadenza è ampiamente nei termini.

---
*Analisi assistita. La verifica finale resta responsabilità del candidato.*
```

---

## Metriche

| Metrica | Manuale | Automatico |
|---|---|---|
| Tempo per bando (qualificazione) | 3–5 min | < 5 sec |
| Copertura fonti settimanale | dipende dalla costanza | 100% configurata |
| Formati supportati | PDF testuale | PDF testuale, PDF scansionato, HTML |
| Tracciabilità decisione | nessuna | checklist auditabile in SQLite |
| Rischio di perdere bandi rilevanti | alto (fatica cognitiva) | basso (dedup hash-based) |

---

## Stack e scelte tecnologiche

| Componente | Scelta | Motivazione |
|---|---|---|
| Orchestrazione LLM | LangChain LCEL | Chain composabile, mock testabile con `RunnableLambda` |
| LLM estrazione | OpenRouter (Mistral/Gemma) | Dati pubblici, costo basso, nessun vincolo privacy |
| LLM reporting | Ollama locale (Llama 3.1) | Dati privati, zero latenza di rete, zero costo API |
| Validazione output LLM | Pydantic v2 | Retry automatico su `ValidationError`; schema come contratto |
| Storage | SQLite stdlib | Zero infrastruttura, sufficiente per il volume MVP |
| OCR | pytesseract + Tesseract `ita` | Open source, lingua italiana inclusa, accuratezza adeguata |
| Test LLM | `RunnableLambda` mock | Compatibile con LCEL senza stubs complessi |

---

### 4. Schede generate solo per i bandi rilevanti

Il `reporter` chiama Ollama e scrive su disco solo per bandi con compatibilità `alta` o `media`. I bandi `bassa` vengono esclusi prima della chiamata al modello.

Una spiegazione testuale di perché un bando è incompatibile non aggiunge valore al candidato — la checklist con gli esiti `fail` è già sufficiente e leggibile. Su 579 bandi analizzati in un run reale: 10 `alta`, 546 `media`, 23 `bassa`. Generare schede per i 23 `bassa` significherebbe 23 chiamate Ollama e altrettanti file su disco senza utilità.

Il filtro vive nella query SQLite di `reporter/__main__.py`, non nell'interfaccia pubblica `generate_report()`, che resta generica. In un contesto di debug o audit è sufficiente chiamarla direttamente con qualsiasi `MatchResult`.

---

## Cosa non fa (by design)

- **Non invia candidature automaticamente** — human-in-the-loop per ogni azione verso l'esterno
- **Non dà pareri legali sui requisiti** — offre prima qualificazione assistita, non consulenza
- **Non scala a multi-tenant senza intervento** — SQLite e filesystem locale sono sufficienti per l'MVP; PostgreSQL e storage condiviso sono esplicitamente V2
- **Non usa il LLM per decidere** — la checklist Python è la fonte di verità; il LLM genera solo testo

---

## Perché conta

Questo progetto mi ha costretto a rispondere a una domanda concreta: quando ha senso affidare una decisione a un LLM e quando no? Ho scelto di non farlo per il matching — non per sfiducia nei modelli, ma perché in un contesto dove l'output ha conseguenze pratiche per un candidato, la riproducibilità e l'auditabilità valgono più della flessibilità.

La stessa tensione vale per la privacy: ho progettato il vincolo strutturalmente, non configurativamente, perché un sistema sicuro non è quello che non viene configurato male — è quello che non può essere configurato in modo insicuro.

Il motore (collector → parser → extractor → reporter) è separato dalla logica di dominio "bandi". Puntarlo su un altro verticale documentale — gare d'appalto, bandi europei, ciclo passivo aziendale — richiede di cambiare il modello dati e le funzioni `check_*`, non l'infrastruttura.
