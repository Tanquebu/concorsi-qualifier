from datetime import date

from src.matcher.models import CheckItem

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


def check_esclusioni(requisiti: list[str], esclusioni: list[str]) -> CheckItem:
    for requisito in requisiti:
        r_low = requisito.lower()
        for esclusione in esclusioni:
            if esclusione.lower() in r_low:
                return CheckItem(
                    requisito="Requisiti escludenti",
                    esito="fail",
                    nota=f"Requisito escludente trovato: '{requisito}'",
                )
    return CheckItem(requisito="Requisiti escludenti", esito="ok")


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
