# concorsi-qualifier

Sistema AI modulare per il monitoraggio e la qualificazione automatica di bandi di concorso pubblico italiani.

Pipeline: **collector → parser → extractor → matcher → reporter → notifier**

Il LLM non prende mai decisioni di matching. La checklist è deterministica; il modello genera solo la spiegazione testuale.

---

## Prerequisiti

- Python 3.10+
- [Ollama](https://ollama.ai) in esecuzione locale (`llama3.1` o `mistral`)
- Tesseract OCR con lingua italiana (`tesseract-ocr tesseract-ocr-ita`)
- API key OpenRouter (solo per il modulo `extractor`)

### Installazione dipendenze di sistema (Ubuntu/Debian)

```bash
sudo apt install tesseract-ocr tesseract-ocr-ita poppler-utils
```

---

## Installazione

```bash
git clone https://github.com/you/concorsi-qualifier
cd concorsi-qualifier
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Configurazione

### Fonti (collector)

`config/sources.yaml` — elenco delle fonti da monitorare:

```yaml
sources:
  - nome: InPA
    url: https://www.inpa.gov.it/bandi-di-concorso/
    tipo: html
    frequenza: daily
```

### Profilo candidato

`config/profilo_candidato.yaml` — rimane sulla macchina locale, non viene mai inviato a LLM cloud:

```yaml
nome: Mario Rossi
titolo_studio: Laurea magistrale LM-18 Informatica
aree_preferite:
  - Milano
  - Lombardia
settori:
  - informatica
esclusioni:
  - riservato ai dipendenti interni
```

### Variabili d'ambiente

```bash
export OPENROUTER_API_KEY="sk-or-..."     # necessario solo per extractor
export OLLAMA_MODEL="llama3.1"            # default
export OLLAMA_BASE_URL="http://localhost:11434"  # default
export NOTIFIER_WEBHOOK_URL="https://hook.example.com/..."  # per digest email
```

---

## Esecuzione pipeline step-by-step

```bash
# 1. Scarica bandi dalle fonti configurate
python3 -m src.collector config/sources.yaml

# 2. Estrai testo dai file raw (PDF/HTML)
python3 -m src.parser data/raw/

# 3. Struttura i dati con LLM (OpenRouter)
python3 -m src.extractor

# 4. Esegui il matching con il profilo candidato
python3 -m src.matcher config/profilo_candidato.yaml

# 5. Genera le schede Markdown
python3 -m src.reporter

# 6. Invia il digest (richiede NOTIFIER_WEBHOOK_URL)
python3 -m src.notifier
```

---

## Struttura output

```
data/
├── raw/                    # file HTML/PDF scaricati dal collector
│   └── <sha256>.<ext>
├── processed/              # schede Markdown generate dal reporter
│   └── <bando_id>.md
concorsi.db                 # SQLite: bandi, collector_runs, match_results
```

### Esempio scheda Markdown generata

```markdown
# Concorso pubblico – n. 5 posti Informatico categoria D

## Riepilogo
- **Ente:** Comune di Milano
- **Posti:** 5
- **Scadenza:** 2026-12-31
- **Area geografica:** Milano
- **Fonte:** [inpa](https://example.com)

## Compatibilità
**Esito:** ALTA

### Checklist requisiti
- ✅ **Titolo di studio**: ok
- ✅ **Area geografica**: ok
- ✅ **Scadenza**: ok
- ✅ **Esclusioni**: ok
- ✅ **Categoria**: ok

## Analisi
Il bando è compatibile con il profilo del candidato.

## Azioni consigliate
- Verificare i requisiti formali sul bando ufficiale
- Preparare la documentazione richiesta

---
*Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato.*
```

---

## Test

```bash
# Suite completa
pytest tests/ -v

# Con coverage
pytest --cov=src tests/ --cov-report=term-missing

# Type check
mypy src/

# Linting
ruff check src/ tests/
```

---

## Vincoli non negoziabili

- **Nessun invio automatico di candidature** — human-in-the-loop sempre.
- **Il profilo candidato non esce mai dalla macchina locale** — non passa per nessun LLM cloud.
- **Nessuna consulenza legale automatica** — il sistema offre prima qualificazione assistita.
- **Disclaimer obbligatorio su ogni output**: *"Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato."*

---

## Architettura

Vedi [`CLAUDE.md`](CLAUDE.md) per lo stack completo e i principi architetturali.
