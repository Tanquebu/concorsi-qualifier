# SPEC.md — Public Concorsi Intelligence

Istruzioni operative per generare i deliverable tecnici del progetto tramite LLM.
Usa `project-brief.md` come contesto di riferimento per tutte le sezioni.

---

## Come usare questo documento

Ogni sezione contiene un **prompt autonomo**: può essere inviato a un LLM (Claude, GPT-4o, Gemini) con o senza `project-brief.md` allegato. Se alleghi il brief, il prompt fa riferimento esplicito a quel contesto. Se non lo alleghi, le sezioni includono il contesto minimo necessario.

Formato di output atteso: specificato per ogni sezione.
Lingua output: italiano, salvo dove indicato (nomi variabili e codice in inglese).

---

## SEZIONE 1 — Architettura tecnica

### Prompt

```
Sei un software architect. Ti fornisco il brief di un progetto Python chiamato "Public Concorsi Intelligence".

Il progetto è un sistema AI modulare che:
1. Raccoglie bandi di concorso pubblico da portali web (Crawlee, Python)
2. Estrae dati strutturati dai bandi in formato PDF/HTML (LangChain + OpenRouter)
3. Valida l'output con Pydantic v2
4. Confronta i bandi con un profilo candidato tramite checklist deterministica (nessun LLM per la decisione di matching)
5. Genera una scheda Markdown per ogni bando con esito match e spiegazione (LLM locale Ollama)
6. Invia un digest email settimanale (n8n o Make)

Stack obbligatorio: Python 3.11+, Crawlee, LangChain, OpenRouter (per estrazione bando), Ollama (per matching/reporting), Pydantic v2, SQLite, pdfplumber, pytesseract.

Genera:
1. Descrizione testuale dell'architettura complessiva (max 300 parole), con flusso dati esplicito da fonte a notifica finale.
2. Diagramma ASCII del flusso tra moduli (usa frecce → e nomi moduli in snake_case).
3. Responsabilità di ogni modulo in formato tabella: | Modulo | Input | Output | Dipendenze |
4. Decisioni architetturali chiave da documentare nel README (lista puntata, max 6 voci).
5. Struttura delle cartelle del repository Python (albero directory).

Vincoli da rispettare:
- Il profilo candidato non deve mai passare per un LLM cloud (privacy by design).
- Il matching usa solo logica deterministica (checklist), il LLM genera solo la spiegazione testuale del risultato.
- L'architettura deve essere modulare: ogni componente sostituibile indipendentemente.
- Nessun invio automatico di candidature.
```

---

## SEZIONE 2 — Backlog

### Prompt

```
Sei un product manager tecnico. Devi creare il backlog di sviluppo per un MVP Python chiamato "Public Concorsi Intelligence".

Il sistema è composto da questi moduli, in ordine di dipendenza:
- collector: scarica HTML e PDF da fonti configurate, deduplicazione via hash
- parser: estrae testo da PDF con fallback chain (text → OCR → skip+flag)
- extractor: LangChain + LLM (OpenRouter) → JSON validato Pydantic
- matcher: checklist deterministica profilo candidato vs bando
- reporter: genera scheda Markdown per ogni bando con esito match
- notifier: digest email settimanale via n8n/Make

Il progetto è sviluppato part-time in 4 settimane. Non ha UI. Non ha API esterna. Non ha multi-utente.

Genera il backlog in formato Markdown con questa struttura per ogni task:

### [MODULO] Titolo task
**Tipo:** feature | fix | chore | doc
**Priorità:** P0 (bloccante) | P1 (MVP) | P2 (nice-to-have)
**Stima:** XS (< 1h) | S (1–2h) | M (2–4h) | L (4–8h)
**Dipende da:** [lista task precedenti, se applicabile]
**Criteri di completamento:** [lista puntata, verificabile]

Requisiti:
- Includi almeno 3–4 task per modulo.
- Includi task di documentazione (README, diagramma, esempi I/O).
- Includi task di test (almeno 1 per modulo: test con fixture di bando reale).
- Segna come P0 solo i task senza i quali l'MVP non gira end-to-end.
- Non includere task per feature fuori MVP (dashboard, multi-utente, API, quiz).
```

---

## SEZIONE 3 — Schema database SQLite

### Prompt

```
Sei un database engineer. Progetta lo schema SQLite per il progetto "Public Concorsi Intelligence", un sistema Python che raccoglie bandi di concorso pubblico, li normalizza e li confronta con profili candidato.

Le entità principali sono:

**Bando**: un concorso pubblico estratto da una fonte web. Campi principali: id (hash), fonte, url, titolo, ente, categoria, area_geografica, posti, scadenza, titolo_studio_richiesto, requisiti_formali (lista), materie_esame (lista), tassa_concorso, link_candidatura, documenti_richiesti (lista), testo_raw, parse_method (enum), extraction_confidence (float), status (enum), created_at.

**CandidatoProfilo**: il profilo di un candidato contro cui fare il matching. Campi: id, nome, titolo_studio, aree_preferite (lista), settori (lista), anni_esperienza, parole_chiave (lista), esclusioni (lista), created_at.

**MatchResult**: risultato del confronto tra un bando e un profilo. Campi: id, bando_id (FK), profilo_id (FK), compatibilita (enum: alta/media/bassa/da_verificare), checklist (JSON), da_verificare (lista), spiegazione (testo LLM), disclaimer, created_at.

**CollectorRun**: log di ogni esecuzione del collector. Campi: id, fonte, started_at, completed_at, n_trovati, n_nuovi, n_duplicati, status, errori (JSON).

Genera:
1. DDL SQL completo (CREATE TABLE con tipi, constraint, indici utili).
2. Note su come gestire i campi lista/JSON in SQLite (approccio consigliato).
3. Query SQLite utili per l'operatività: bandi in scadenza entro 7 giorni, bandi con compatibilità alta per profilo X, bandi con parse_failed non ancora revisionati.
4. Considerazioni sulla migrazione a PostgreSQL per la Variante 3 (multi-tenant): quali campi cambierebbero e perché.
```

---

## SEZIONE 4 — Roadmap 4 settimane

### Prompt

```
Sei un technical lead che deve pianificare lo sviluppo part-time di un MVP Python in 4 settimane.

Il progetto "Public Concorsi Intelligence" ha questi moduli (in ordine di dipendenza):
1. collector (Crawlee, SQLite)
2. parser (pdfplumber, pytesseract, fallback chain)
3. extractor (LangChain, OpenRouter, Pydantic)
4. matcher (checklist Python deterministica)
5. reporter (generazione Markdown con LLM locale Ollama)
6. notifier (n8n/Make, email digest)

Vincoli:
- Sviluppo part-time: max 2–3 ore/giorno, non tutti i giorni
- Nessuna UI, nessuna API esterna, nessun multi-utente
- La settimana 4 è dedicata principalmente a documentazione e case study
- Ogni settimana deve avere un output verificabile (non solo codice intermedio)

Genera:
1. Roadmap settimanale in formato tabella: | Settimana | Obiettivo | Moduli coinvolti | Output verificabile | Rischi |
2. Per ogni settimana: lista dei 3–5 task principali con stima in ore.
3. Milestone di fine MVP: criteri di "done" per dichiarare l'MVP completo (lista puntata, oggettiva).
4. Dipendenze critiche: cosa sblocca cosa (lista o grafo testuale).
5. Rischi principali e mitigazioni (max 4 rischi).
```

---

## SEZIONE 5 — Prompt di matching (LangChain)

### Prompt

```
Sei un prompt engineer specializzato in LangChain e output strutturato con Pydantic.

Devi scrivere il prompt template LangChain per il modulo "reporter" del progetto "Public Concorsi Intelligence".

Contesto: il matcher ha già prodotto un MatchResult strutturato (checklist di requisiti con esito ok/warning/fail/unknown, lista "da_verificare"). Il reporter chiede a un LLM locale (Ollama, Llama 3.1 o Mistral) di generare:
1. Una spiegazione testuale del risultato (2–4 frasi, tono professionale, non burocratico)
2. Una lista di azioni consigliate al candidato (max 3 voci)

Il LLM NON deve rivedere la compatibilità: quella è già decisa dalla checklist. Deve solo spiegare e tradurre in linguaggio leggibile.

Input disponibile per il prompt:
- titolo bando
- ente
- scadenza
- compatibilita (alta/media/bassa/da_verificare)
- checklist: lista di {requisito, esito, nota}
- da_verificare: lista di stringhe

Genera:
1. Il prompt template LangChain completo (usa PromptTemplate o ChatPromptTemplate, con variabili {titolo}, {ente}, {scadenza}, {compatibilita}, {checklist_testo}, {da_verificare_testo}).
2. La funzione Python che:
   a. prepara l'input dal MatchResult
   b. chiama il chain
   c. restituisce un dict con chiavi "spiegazione" e "azioni_consigliate"
3. Un esempio di input e output atteso (fixture da usare nei test).
4. Note su come adattare il prompt se il LLM locale produce output verboso o in lingua sbagliata.

Vincoli:
- Il prompt deve funzionare con modelli piccoli (7B–13B parametri) senza garantire JSON output nativo.
- Usa output parsing robusto (no json.loads() diretto, gestisci fallback).
- Includi il disclaimer fisso nel template: "Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato."
- Lingua output: italiano.
```

---

## Note operative

- **Ordine consigliato:** genera Sezione 1 (architettura) e Sezione 3 (schema DB) per prime — sono le basi su cui tutto il resto si appoggia.
- **Iterazione:** i prompt sono pensati per una singola chiamata LLM. Se l'output è incompleto, aggiungi al prompt: "Completa la sezione [X] che mancava nella risposta precedente."
- **Coerenza tra sezioni:** quando generi Sezione 2 (backlog) e 4 (roadmap), allega l'output di Sezione 1 come contesto aggiuntivo per evitare incongruenze.
- **Modello consigliato:** Claude Sonnet o GPT-4o per Sezioni 1–4 (ragionamento architetturale); Claude Sonnet o Gemini per Sezione 5 (prompt engineering tecnico).
