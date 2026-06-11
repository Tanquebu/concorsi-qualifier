from langchain_core.prompts import PromptTemplate

_FULL_TEMPLATE = """Sei un assistente specializzato nell'estrazione di dati strutturati \
da bandi di concorso pubblico italiani.

Analizza il testo seguente e restituisci un oggetto JSON con questi campi:
- "titolo": titolo del concorso (stringa)
- "ente": ente che bandisce (stringa)
- "categoria": categoria professionale, es. "informatica", "amministrativa" (stringa o null)
- "area_geografica": luogo/sede del concorso (stringa o null)
- "posti": numero di posti disponibili (intero o null)
- "scadenza": data di scadenza in formato YYYY-MM-DD (stringa o null)
- "titolo_studio_richiesto": titolo di studio minimo richiesto (stringa o null)
- "requisiti_formali": lista di requisiti formali per partecipare (lista di stringhe)
- "materie_esame": materie d'esame previste (lista di stringhe)
- "tassa_concorso": importo della tassa di partecipazione in euro (numero o null)
- "link_candidatura": URL per inviare la candidatura (stringa o null)
- "documenti_richiesti": documenti da allegare alla domanda (lista di stringhe)

Rispondi SOLO con il JSON, senza spiegazioni, senza markdown.

TESTO BANDO:
{testo_bando}

JSON:"""

_SIMPLIFIED_TEMPLATE = """Dal testo di bando di concorso seguente, estrai solo questi campi JSON:
- "titolo": titolo del concorso
- "ente": ente che bandisce
- "scadenza": formato YYYY-MM-DD o null
- "posti": intero o null
- "titolo_studio_richiesto": stringa o null
- "requisiti_formali": lista di stringhe (può essere vuota [])
- "materie_esame": lista di stringhe (può essere vuota [])
- "documenti_richiesti": lista di stringhe (può essere vuota [])

Rispondi SOLO con il JSON.

TESTO:
{testo_bando}

JSON:"""

EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["testo_bando"],
    template=_FULL_TEMPLATE,
)

EXTRACTION_PROMPT_SIMPLIFIED = PromptTemplate(
    input_variables=["testo_bando"],
    template=_SIMPLIFIED_TEMPLATE,
)
