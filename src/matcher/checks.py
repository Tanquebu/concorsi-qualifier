import re
from datetime import date

from src.matcher.models import CheckItem

# Rileva atti che non sono concorsi pubblici per assunzione: nomine a organismi, incarichi monocratici
_TIPO_NON_CONCORSO_RE = re.compile(
    r"nomina\s+organismo"
    r"|nomina\s+oiv\b"
    r"|\borganismo\s+indipendente\s+(?:di\s+)?valutazione"
    r"|nomina\s+commissari[oa]\b"
    r"|nomina\s+(?:dei?\s+)?componenti"
    r"|procedura\s+selettiva\s+(?:pubblica\s+)?per\s+(?:la\s+)?nomina"
    # Graduatorie già formate: titolo che inizia con "Graduatoria" = scorrimento lista
    r"|^graduatoria\s+"
    # "Graduatoria di merito" menzionata nel corpo del testo
    r"|\bgraduatoria\s+di\s+merito\b",
    re.IGNORECASE,
)

# Rileva avvisi di mobilità (art. 30 D.Lgs. 165/2001): trasferimento tra PA, richiede già di essere
# dipendente pubblico. Cercata solo nel titolo per evitare falsi positivi su concorsi che menzionano
# "mobilità" nel testo (es. concorso per responsabile ufficio mobilità urbana).
_MOBILITA_RE = re.compile(r"\bmobilit[àa]\b", re.IGNORECASE)

# Rileva contratti a durata fissa: "durata di 24 mesi", "durata biennale", "12 mesi prorogabili"
_DURATA_FISSA_RE = re.compile(
    r"durat\w{0,1}\s+(?:di\s+)?\d+\s*mesi"   # "durata di 24 mesi" + typo "durat di"
    r"|durata\s+(?:annuale|biennale|triennale|quadriennale)"
    r"|\d+\s+mesi\s+(?:rinnovabili|prorogabili)",
    re.IGNORECASE,
)

_LIVELLI_TITOLO: dict[str, int] = {
    "dottorato": 4,
    "phd": 4,
    "magistrale": 3,
    "lm-": 3,
    "lmu": 3,
    "vecchio ordinamento": 3,
    "laurea specialistica": 3,
    "triennale": 2,
    "l-": 2,
    "laurea": 2,
    "diploma universitario": 2,
    "diploma": 1,
    "licenza media": 1,
}


def check_titolo_studio(richiesto: str | None, posseduto: str) -> CheckItem:
    if richiesto is None:
        return CheckItem(
            requisito="Titolo di studio",
            esito="unknown",
            nota="Titolo di studio richiesto non specificato nel bando",
        )
    r_low = richiesto.lower()
    p_low = posseduto.lower()

    if p_low in r_low or r_low in p_low:
        return CheckItem(requisito="Titolo di studio", esito="ok")

    livello_richiesto = max((v for k, v in _LIVELLI_TITOLO.items() if k in r_low), default=0)
    livello_posseduto = max((v for k, v in _LIVELLI_TITOLO.items() if k in p_low), default=0)

    if livello_richiesto == 0:
        return CheckItem(
            requisito="Titolo di studio",
            esito="warning",
            nota=f"Verifica manuale: '{richiesto}'",
        )
    if livello_posseduto >= livello_richiesto:
        return CheckItem(requisito="Titolo di studio", esito="ok")
    return CheckItem(
        requisito="Titolo di studio",
        esito="fail",
        nota=f"Richiesto: '{richiesto}', posseduto: '{posseduto}'",
    )


def check_area_geografica(area_bando: str | None, aree_preferite: list[str]) -> CheckItem:
    if area_bando is None:
        return CheckItem(
            requisito="Area geografica",
            esito="unknown",
            nota="Sede non specificata nel bando",
        )
    a_low = area_bando.lower()
    for area in aree_preferite:
        if area.lower() in a_low or a_low in area.lower():
            return CheckItem(requisito="Area geografica", esito="ok")
    return CheckItem(
        requisito="Area geografica",
        esito="warning",
        nota=f"Sede '{area_bando}' non nelle aree preferite",
    )


def check_scadenza(scadenza: date | None) -> CheckItem:
    if scadenza is None:
        return CheckItem(
            requisito="Scadenza",
            esito="unknown",
            nota="Scadenza non specificata nel bando",
        )
    if scadenza < date.today():
        return CheckItem(
            requisito="Scadenza",
            esito="fail",
            nota=f"Bando scaduto il {scadenza}",
        )
    return CheckItem(requisito="Scadenza", esito="ok")


def check_esclusioni(
    requisiti: list[str],
    esclusioni: list[str],
    titolo: str = "",
    testo_raw: str = "",
) -> CheckItem:
    testi = requisiti + ([titolo] if titolo else [])
    if testo_raw:
        testi.append(testo_raw[:2000])
    for testo in testi:
        t_low = testo.lower()
        for esclusione in esclusioni:
            if esclusione.lower() in t_low:
                return CheckItem(
                    requisito="Requisiti escludenti",
                    esito="fail",
                    nota=f"Clausola escludente: '{esclusione}'",
                )
        if _DURATA_FISSA_RE.search(testo):
            match = _DURATA_FISSA_RE.search(testo)
            return CheckItem(
                requisito="Requisiti escludenti",
                esito="fail",
                nota=f"Contratto a durata fissa: '{match.group(0)}'",
            )
    return CheckItem(requisito="Requisiti escludenti", esito="ok")


_ESPERIENZA_TRIGGERS: list[str] = [
    "esperienza professionale",
    "esperienza maturata",
    "comprovata esperienza",
    "comprovata competenza",
    "esperienza nel ",
    "esperienza nella ",
    "esperienza nelle ",
    "esperienza in ",
    "esperienza di almeno",
    "anni di esperienza",
    "anni di attività",
    "anzianità di servizio",
]

# Parole generiche che non indicano un dominio specifico
_PAROLE_GENERICHE: set[str] = {
    "anni", "mesi", "servizio", "lavoro", "lavorativa", "professionale",
    "almeno", "anche", "non", "con", "per", "nei", "nelle", "degli",
    "delle", "della", "dello", "nel", "nella", "pubblico", "privato",
    "pubblica", "privata", "amministrazione", "settore", "ambito",
    "attività", "incarico", "ruolo", "funzione", "qualificata", "comprovata",
    "maturata", "documentata", "complessiva", "quinquennale", "triennale",
    "biennale", "decennale", "pregressa", "precedente", "precedenti",
    "analogo", "analoga", "simile", "equivalente", "continuativi",
    "anzianità", "seniority", "essere", "avere", "possesso", "possedere",
    "apprezzabile", "dimostrabile", "documentabile", "significativa",
    "mansioni", "mansione", "categoria", "profilo", "figura", "livello",
    "ovvero", "oppure", "quindi", "nonché", "ovvero", "nonche",
}


def check_esperienza_dominio(
    requisiti: list[str],
    settori: list[str],
    parole_chiave: list[str],
) -> CheckItem:
    """Controlla se i requisiti di esperienza di dominio sono allineati con il profilo."""
    profilo_kw = [kw.lower() for kw in settori + parole_chiave]

    for req in requisiti:
        r_low = req.lower()
        if not any(trigger in r_low for trigger in _ESPERIENZA_TRIGGERS):
            continue

        # Estrae le parole significative del requisito (>5 chars, non generiche)
        parole = [
            w.strip("',;:.()") for w in r_low.split()
            if len(w) > 5 and w.strip("',;:.()") not in _PAROLE_GENERICHE
        ]
        # Serve almeno 2 parole di dominio per considerare il requisito specifico
        if len(parole) < 2:
            continue

        # Se almeno una parola chiave del profilo appare nel requisito → ok
        if any(kw in r_low for kw in profilo_kw):
            return CheckItem(requisito="Esperienza di dominio", esito="ok")

        # Dominio specifico rilevato ma non corrisponde al profilo
        dominio_esempio = " ".join(parole[:6])
        return CheckItem(
            requisito="Esperienza di dominio",
            esito="warning",
            nota=f"Esperienza richiesta in dominio non nel profilo: '{dominio_esempio}...'",
        )

    return CheckItem(requisito="Esperienza di dominio", esito="ok")


def check_categoria(categoria: str | None, settori: list[str]) -> CheckItem:
    if categoria is None:
        return CheckItem(
            requisito="Categoria",
            esito="unknown",
            nota="Categoria non specificata nel bando",
        )
    c_low = categoria.lower()
    for settore in settori:
        if settore.lower() in c_low or c_low in settore.lower():
            return CheckItem(requisito="Categoria", esito="ok")
    return CheckItem(
        requisito="Categoria",
        esito="warning",
        nota=f"Categoria '{categoria}' non corrisponde ai settori preferiti",
    )


def check_tipo_atto(titolo: str, testo_raw: str = "") -> CheckItem:
    testo = titolo + " " + testo_raw[:1000]
    if _TIPO_NON_CONCORSO_RE.search(testo) or _MOBILITA_RE.search(titolo):
        return CheckItem(
            requisito="Tipo atto",
            esito="fail",
            nota="Non è un concorso pubblico per assunzione: mobilità, graduatoria già formata o nomina a organismo/incarico",
        )
    return CheckItem(requisito="Tipo atto", esito="ok")
