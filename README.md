# concorsi-qualifier

Sistema AI modulare per il monitoraggio e la qualificazione automatica di bandi di concorso pubblico italiani.

Pipeline: **collector → parser → extractor → matcher → reporter → notifier**

Il LLM non prende mai decisioni di matching. La checklist è deterministica; il modello genera solo la spiegazione testuale.

---

## Prerequisiti

- Python 3.10+
- [Ollama](https://ollama.ai) in esecuzione locale o su macchina raggiungibile (`llama3.1` o `mistral`)
- Tesseract OCR con lingua italiana (`tesseract-ocr tesseract-ocr-ita`)
- API key [OpenRouter](https://openrouter.ai) (solo per il modulo `extractor`)

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

`config/sources.yaml` — elenco delle fonti da monitorare. Tipi supportati:

- `tipo: inpa_portal` — interroga l'API REST del portale InPA (`status=OPEN`); restituisce solo bandi aperti con scadenze future. **Fonte consigliata per InPA.**
- `tipo: wordpress` — scarica i post singoli via WordPress REST API
- `tipo: html` — scarica la pagina come singolo file HTML
- `tipo: pdf` — scarica un PDF direttamente

```yaml
sources:
  - nome: InPA Portale
    tipo: inpa_portal
    per_page: 500         # bandi da scaricare per run (su ~1700 aperti totali)
    frequenza: daily

  - nome: InPA Blog
    url: https://www.inpa.gov.it
    tipo: wordpress
    per_page: 50
    frequenza: daily
    exclude_keywords:     # titoli da scartare (case-insensitive)
      - manutenzione sul portale
```

> **Nota:** siti che rendono i contenuti via JavaScript (SPA Angular/React) richiedono Playwright e non sono ancora supportati dal collector base.

### Profilo candidato

`config/profilo_candidato.yaml` — rimane sulla macchina locale, non viene mai inviato a LLM cloud:

```yaml
nome: Mario Rossi
titolo_studio: Laurea magistrale LM-18 Informatica
aree_preferite:
  - Milano
  - Lombardia
  - Italia        # aggiungere per non penalizzare bandi a sede nazionale
settori:
  - informatica
esclusioni:
  - riservato ai dipendenti interni
```

### Variabili d'ambiente

```bash
export OPENROUTER_API_KEY="sk-or-..."          # necessario per extractor
export OPENROUTER_MODEL="mistralai/mistral-small-3.2-24b-instruct"  # default
export OLLAMA_MODEL="llama3.1"                 # default
export OLLAMA_BASE_URL="http://localhost:11434" # default; può essere remoto (es. Tailscale)
export NOTIFIER_WEBHOOK_URL="https://hook.example.com/..."  # per digest email
```

---

## Esecuzione pipeline step-by-step

```bash
# 1. Scarica bandi dalle fonti configurate
python3 -m src.collector config/sources.yaml

# 2. Struttura i dati con LLM (OpenRouter)
python3 -m src.extractor

# 3. Esegui il matching con il profilo candidato
python3 -m src.matcher config/profilo_candidato.yaml

# 4. Genera le schede Markdown
python3 -m src.reporter

# 5. Invia il digest (richiede NOTIFIER_WEBHOOK_URL)
python3 -m src.notifier

# oppure: anteprima senza invio
python3 -m src.notifier --dry-run

# oppure: mostra tutti i bandi compatibili ignorando il filtro scadenza (utile per test)
python3 -m src.notifier --dry-run --all
```

> Il modulo `parser` (`python3 -m src.parser`) è disponibile per estrarre testo da PDF/HTML grezzi in modo standalone, ma non è necessario nel flusso normale: l'extractor lo invoca automaticamente.

---

## Struttura output

```
data/
├── raw/                    # file HTML/PDF scaricati dal collector
│   ├── <sha256>.html
│   └── <sha256>.meta.json  # url, fonte, data scraping
├── processed/              # schede Markdown generate dal reporter
│   └── <bando_id>.md
concorsi.db                 # SQLite: bandi, collector_runs, match_results
```

### Esempio di run reale (12/06/2026)

Output della pipeline su dati InPA reali — 579 bandi aperti al momento dell'esecuzione.

**Extractor** (LangChain + OpenRouter → SQLite):

```
[1/579] OK   — Concorso pubblico – Informatico cat. D (Comune di Bergamo)
[2/579] OK   — Selezione pubblica funzionario informatico (Regione Lombardia)
...
[579/579] OK — Concorso per n. 2 istruttori tecnici (Comune di Varese)

Estratti: 579 | Errori: 0
```

**Matcher** (checklist deterministica → SQLite):

```
[1/579] ✅ alta       — Avviso mobilità esterna (Univ. Milano-Bicocca)
[2/579] 🟡 media      — Concorso docenti scuola secondaria (USR Umbria)
[3/579] ❌ bassa      — Concorso riservato a dipendenti interni (Comune di X)
...
[579/579] 🟡 media

Riepilogo: ✅ 10 alta | 🟡 546 media | ❌ 23 bassa
```

**Reporter** (schede Markdown per alta + media → `data/processed/`):

```
[1/556] ✅ alta  — Avviso mobilità esterna (Univ. Milano-Bicocca)
[2/556] 🟡 media — Concorso docenti scuola secondaria (USR Umbria)
...
[556/556] 🟡 media

Schede generate: 556 | Saltate (già su disco): 0 | Errori Ollama: 0
```

**Scheda generata** (compatibilità ALTA — dati reali da `data/processed/`):

```markdown
# AVVISO di MOBILITÀ ESTERNA ai sensi dell'art. 30 del Decreto Legislativo 30 marzo 2001, n. 165

## Riepilogo
- **Ente:** Universita' degli Studi di Milano - Bicocca
- **Posti:** 1
- **Scadenza:** 2026-07-07
- **Area geografica:** Lombardia
- **Fonte:** [InPA Portale](https://portale.inpa.gov.it/concorso/c36f7a105bc74e21a071712874c75a5d)

## Compatibilità
**Esito:** ALTA

### Checklist requisiti
- ❓ **Titolo di studio**: unknown — Titolo di studio richiesto non specificato nel bando
- ✅ **Area geografica**: ok
- ✅ **Scadenza**: ok
- ✅ **Requisiti escludenti**: ok
- ✅ **Categoria**: ok

## Punti da verificare manualmente
- Titolo di studio richiesto non specificato nel bando

---
*Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato.*
```

> L'esito `ALTA` con un campo `unknown` è il comportamento corretto: la checklist non penalizza i campi mancanti nel bando (non è detto che il requisito non sia soddisfatto — manca solo l'informazione). Solo i check con esito `fail` o `warning` abbassano la compatibilità.

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

## Logica di compatibilità

Il matcher esegue 5 check deterministici e aggrega il risultato:

| Esito | Condizione |
|---|---|
| `alta` | Nessun `fail`, nessun `warning` (campi `null` non penalizzano) |
| `media` | Nessun `fail`, ma almeno un `warning` (es. sede fuori area preferita) |
| `bassa` | Almeno un `fail` (es. bando scaduto, requisito escludente trovato) |
| `da_verificare` | Tutti i campi sono `null` — nessuna informazione disponibile |

I check sono: titolo di studio, area geografica, scadenza, requisiti escludenti, categoria.

---

## Vincoli non negoziabili

- **Nessun invio automatico di candidature** — human-in-the-loop sempre.
- **Il profilo candidato non esce mai dalla macchina locale** — non passa per nessun LLM cloud.
- **Nessuna consulenza legale automatica** — il sistema offre prima qualificazione assistita.
- **Disclaimer obbligatorio su ogni output**: *"Analisi assistita. La verifica finale dei requisiti formali resta responsabilità del candidato."*

---

## Architettura

Vedi [`CLAUDE.md`](CLAUDE.md) per lo stack completo e i principi architetturali.
