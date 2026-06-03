# Prompt di inizializzazione — prima sessione concorsi-qualifier

Da incollare come primo messaggio in una nuova sessione Claude Code aperta nella cartella del progetto.

---

```
Inizializziamo il progetto Python "concorsi-qualifier" (Public Concorsi Intelligence).

Leggi prima questi due file (sono nella stessa cartella del progetto):
- ./project-brief.md
- ./SPEC.md

Poi esegui in ordine:

1. Crea CLAUDE.md in questa cartella. Deve contenere:
   - nome progetto e descrizione in una riga
   - stack (obbligatorio vs opzionale)
   - struttura moduli con responsabilità di ciascuno
   - vincoli non negoziabili (no invio automatico candidature, profilo candidato mai su LLM cloud, human-in-the-loop)
   - principio architetturale chiave: il LLM estrae i dati dal bando, la logica Python decide il match, il LLM locale genera solo la spiegazione testuale
   - convenzioni di codice: Pydantic v2 per tutti i modelli, tipo di ritorno esplicito su ogni funzione, test con pytest + fixture bandi reali

2. Crea la struttura di cartelle del progetto (solo cartelle e file __init__.py, nessun codice ancora):
   - src/ con sottocartelle per ogni modulo (collector, parser, extractor, matcher, reporter, notifier)
   - tests/ con sottocartella fixtures/
   - data/ con sottocartelle raw/ e processed/
   - config/ per profili candidato YAML e configurazione fonti
   - docs/ per architettura e case study

3. Crea pyproject.toml (o requirements.txt) con le dipendenze del progetto.

Fermati dopo il punto 3. Mostrami CLAUDE.md, la struttura cartelle e pyproject.toml prima di procedere con il codice.
```

---

## Note

- Il prompt usa percorsi relativi: funziona da qualsiasi macchina purché `project-brief.md` e `SPEC.md` siano nella cartella radice del progetto.
- Dopo l'approvazione di CLAUDE.md e struttura, la sessione successiva parte dal brief della SPEC.md, Sezione 1 (architettura) — genera il dettaglio prima di scrivere codice.
- I file YAML di configurazione fonti e profilo candidato vanno in `config/` e sono il primo input reale su cui testare il collector.
