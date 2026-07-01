import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from src.extractor.models import Bando
from src.matcher.checks import (
    check_area_geografica,
    check_categoria,
    check_esclusioni,
    check_scadenza,
    check_tipo_atto,
    check_titolo_studio,
)
from src.matcher.matcher import aggregate_checks
from src.matcher.matcher import match as internal_match
from src.matcher.models import DISCLAIMER, CandidatoProfilo, CheckItem


def _bando(**kwargs: object) -> Bando:
    defaults: dict[str, object] = {
        "id": "b001",
        "fonte": "inpa",
        "url": "https://example.com",
        "titolo": "Concorso Test",
        "ente": "Comune Test",
        "parse_method": "pdf_text",
    }
    defaults.update(kwargs)
    return Bando(**defaults)  # type: ignore[arg-type]


def _profilo(**kwargs: object) -> CandidatoProfilo:
    defaults: dict[str, object] = {
        "nome": "Mario Rossi",
        "titolo_studio": "Laurea magistrale LM-18 Informatica",
        "aree_preferite": ["Milano", "Lombardia"],
        "settori": ["informatica"],
        "esclusioni": ["riservato ai dipendenti interni"],
    }
    defaults.update(kwargs)
    return CandidatoProfilo(**defaults)  # type: ignore[arg-type]


# --- check_titolo_studio ---

def test_check_titolo_studio_ok_substring() -> None:
    titolo = "Laurea magistrale LM-18 Informatica"
    item = check_titolo_studio(titolo, titolo)
    assert item.esito == "ok"


def test_check_titolo_studio_ok_livello() -> None:
    item = check_titolo_studio("Diploma di scuola superiore", "Laurea magistrale LM-18")
    assert item.esito == "ok"


def test_check_titolo_studio_fail() -> None:
    item = check_titolo_studio("Dottorato di ricerca", "Diploma di scuola superiore")
    assert item.esito == "fail"
    assert item.nota is not None


def test_check_titolo_studio_unknown() -> None:
    item = check_titolo_studio(None, "Laurea magistrale LM-18")
    assert item.esito == "unknown"


# --- check_area_geografica ---

def test_check_area_geografica_ok() -> None:
    item = check_area_geografica("Milano", ["Milano", "Roma"])
    assert item.esito == "ok"


def test_check_area_geografica_warning() -> None:
    item = check_area_geografica("Palermo", ["Milano", "Roma"])
    assert item.esito == "warning"


def test_check_area_geografica_unknown() -> None:
    item = check_area_geografica(None, ["Milano"])
    assert item.esito == "unknown"


def test_check_area_geografica_nazionale() -> None:
    item = check_area_geografica("Nazionale", ["Milano"])
    assert item.esito == "ok"


def test_check_area_geografica_tutto_territorio() -> None:
    item = check_area_geografica("tutto il territorio nazionale", ["Roma"])
    assert item.esito == "ok"


# --- check_scadenza ---

def test_check_scadenza_ok() -> None:
    item = check_scadenza(date.today() + timedelta(days=30))
    assert item.esito == "ok"


def test_check_scadenza_expired() -> None:
    item = check_scadenza(date(2020, 1, 1))
    assert item.esito == "fail"
    assert item.nota is not None


def test_check_scadenza_none() -> None:
    item = check_scadenza(None)
    assert item.esito == "unknown"


# --- check_esclusioni ---

def test_check_esclusioni_ok() -> None:
    item = check_esclusioni(["Cittadinanza italiana"], ["riservato ai dipendenti interni"])
    assert item.esito == "ok"


def test_check_esclusioni_triggered() -> None:
    item = check_esclusioni(
        ["Riservato ai dipendenti interni all'ente"],
        ["riservato ai dipendenti interni"],
    )
    assert item.esito == "fail"
    assert item.nota is not None


# --- check_tipo_atto ---

def test_check_tipo_atto_concorso_ok() -> None:
    item = check_tipo_atto("Concorso pubblico per n. 3 posti di Informatico cat. D")
    assert item.esito == "ok"


def test_check_tipo_atto_nomina_organismo_fail() -> None:
    titolo = (
        "Avviso Procedura Selettiva Pubblica Nomina Organismo Indipendente Valutazione "
        "della Performance in Forma Monocratica Triennio 2026-2028"
    )
    item = check_tipo_atto(titolo)
    assert item.esito == "fail"
    assert item.nota is not None


def test_check_tipo_atto_nomina_oiv_fail() -> None:
    item = check_tipo_atto("Avviso selezione pubblica nomina OIV")
    assert item.esito == "fail"


def test_check_tipo_atto_procedura_selettiva_nomina_fail() -> None:
    item = check_tipo_atto("Procedura selettiva pubblica per la nomina di componente")
    assert item.esito == "fail"


def test_check_tipo_atto_graduatoria_di_merito_fail() -> None:
    item = check_tipo_atto(
        "Graduatoria di merito per la classe di concorso AM2B per posti Friuli Venezia Giulia"
    )
    assert item.esito == "fail"


def test_check_tipo_atto_graduatoria_codice_fail() -> None:
    item = check_tipo_atto("Graduatoria A041 – Regioni Lazio, Sardegna, Toscana")
    assert item.esito == "fail"


def test_check_tipo_atto_graduatoria_del_concorso_fail() -> None:
    item = check_tipo_atto("Graduatoria del concorso personale docente scuola secondaria")
    assert item.esito == "fail"


def test_check_tipo_atto_formazione_graduatoria_ok() -> None:
    # "formazione di una graduatoria" è una selezione attiva, non uno scorrimento lista
    item = check_tipo_atto("Selezione pubblica per esami per la formazione di una graduatoria")
    assert item.esito == "ok"


def test_check_tipo_atto_mobilita_volontaria_fail() -> None:
    item = check_tipo_atto("AVVISO DI MOBILITA' VOLONTARIA PER LA COPERTURA DI N.1 POSTO DI FUNZIONARIO")
    assert item.esito == "fail"


def test_check_tipo_atto_mobilita_esterna_fail() -> None:
    item = check_tipo_atto("AVVISO DI MOBILITA' ESTERNA PER LA COPERTURA DI UN POSTO DI FUNZIONARIO")
    assert item.esito == "fail"


def test_check_tipo_atto_mobilita_accento_fail() -> None:
    item = check_tipo_atto("Mobilità volontaria per passaggio diretto da altre amministrazioni")
    assert item.esito == "fail"


def test_check_tipo_atto_contratto_collaborazione_fail() -> None:
    item = check_tipo_atto("Avviso selezione per contratto di collaborazione coordinata e continuativa")
    assert item.esito == "fail"


def test_check_tipo_atto_cococo_fail() -> None:
    item = check_tipo_atto("Selezione pubblica per collaborazione coordinata e continuativa (co.co.co)")
    assert item.esito == "fail"


def test_check_tipo_atto_sostituzione_componente_oiv_fail() -> None:
    # Bando reale: sostituzione membro dimissionario OIV — non è un concorso pubblico
    titolo = (
        "AVVISO DI PROCEDURA SELETTIVA PUBBLICA FINALIZZATA ALLA SOSTITUZIONE DEL COMPONENTE "
        "DIMISSIONARIO DELL'O.I.V. IN FORMA COLLEGIALE DELL'ISTITUTO ZOOPROFILATTICO "
        "SPERIMENTALE DELLA SICILIA"
    )
    item = check_tipo_atto(titolo)
    assert item.esito == "fail"


def test_check_tipo_atto_oiv_abbreviazione_fail() -> None:
    item = check_tipo_atto("Selezione pubblica O.I.V. Comune di Roma")
    assert item.esito == "fail"


def test_check_tipo_atto_mobilita_solo_testo_raw_ok() -> None:
    # "mobilità" solo nel testo_raw (non nel titolo) non deve escludere un vero concorso
    item = check_tipo_atto(
        "Concorso pubblico per n. 1 Istruttore Tecnico settore trasporti",
        testo_raw="Il candidato gestirà la mobilità urbana e i trasporti pubblici locali.",
    )
    assert item.esito == "ok"


def test_check_tipo_atto_categorie_protette_riservato_fail() -> None:
    titolo = (
        "Bando di Concorso Pubblico per Titoli ed Esami, interamente riservato agli "
        "appartenenti alle Categorie Protette di cui all'art. 8 Comma 2 della Legge "
        "12 Marzo 1999 n. 68, per n. 1 Istruttore Amministrativo"
    )
    item = check_tipo_atto(titolo)
    assert item.esito == "fail"
    assert "categorie protette" in item.nota.lower()


def test_check_tipo_atto_categorie_protette_solo_testo_raw_ok() -> None:
    # "categorie protette" menzionato solo nel corpo (quota parziale) non esclude il bando
    item = check_tipo_atto(
        "Concorso pubblico per n. 3 posti di Funzionario Informatico cat. D",
        testo_raw="2 posti riservati alle categorie protette ai sensi dell'art. 1 L. 68/1999.",
    )
    assert item.esito == "ok"


def test_match_nomina_organismo_bassa() -> None:
    bando = _bando(
        titolo=(
            "Avviso Procedura Selettiva Pubblica Nomina Organismo Indipendente "
            "Valutazione della Performance Triennio 2026-2028"
        ),
        scadenza=date.today() + timedelta(days=10),
        area_geografica="Sicilia, Catania",
        posti=1,
    )
    result = internal_match(bando, _profilo())
    assert result.compatibilita == "bassa", (
        f"atteso 'bassa', ottenuto '{result.compatibilita}'"
    )


# --- check_categoria ---

def test_check_categoria_ok() -> None:
    item = check_categoria("informatica e sistemi", ["informatica"])
    assert item.esito == "ok"


def test_check_categoria_warning() -> None:
    item = check_categoria("area amministrativa", ["informatica"])
    assert item.esito == "warning"


def test_check_categoria_unknown() -> None:
    item = check_categoria(None, ["informatica"])
    assert item.esito == "unknown"


# --- aggregate_checks ---

def test_aggregate_all_ok() -> None:
    checks = [CheckItem(requisito="X", esito="ok"), CheckItem(requisito="Y", esito="ok")]
    assert aggregate_checks(checks) == "alta"


def test_aggregate_one_fail() -> None:
    checks = [CheckItem(requisito="X", esito="ok"), CheckItem(requisito="Y", esito="fail")]
    assert aggregate_checks(checks) == "bassa"


def test_aggregate_all_unknown() -> None:
    checks = [CheckItem(requisito="X", esito="unknown")]
    assert aggregate_checks(checks) == "da_verificare"


def test_aggregate_mixed_ok_warning() -> None:
    checks = [CheckItem(requisito="X", esito="ok"), CheckItem(requisito="Y", esito="warning")]
    assert aggregate_checks(checks) == "media"


def test_aggregate_empty() -> None:
    assert aggregate_checks([]) == "da_verificare"


# --- match() ---

def test_match_returns_match_result() -> None:
    from src.matcher.models import MatchResult

    bando = _bando(
        scadenza=date.today() + timedelta(days=30),
        titolo_studio_richiesto="Laurea magistrale LM-18 Informatica",
        area_geografica="Milano",
        categoria="informatica",
    )
    result = internal_match(bando, _profilo())
    assert isinstance(result, MatchResult)
    assert result.disclaimer == DISCLAIMER


def test_match_compatible_alta() -> None:
    bando = _bando(
        scadenza=date.today() + timedelta(days=30),
        titolo_studio_richiesto="Laurea magistrale LM-18 Informatica",
        area_geografica="Milano",
        categoria="informatica",
        requisiti_formali=[],
    )
    result = internal_match(bando, _profilo())
    assert result.compatibilita == "alta"


def test_match_incompatible_bassa() -> None:
    bando = _bando(scadenza=date(2020, 1, 1))
    result = internal_match(bando, _profilo())
    assert result.compatibilita == "bassa"


# --- match() pubblica con persistenza ---

def test_match_persists_to_db(tmp_path: Path) -> None:
    from src.matcher import match as public_match

    bando = _bando(
        scadenza=date.today() + timedelta(days=30),
        titolo_studio_richiesto="Laurea magistrale LM-18 Informatica",
        area_geografica="Milano",
        categoria="informatica",
    )
    db = tmp_path / "test.db"
    result = public_match(bando, _profilo(), db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT bando_id, compatibilita FROM match_results WHERE bando_id = 'b001'"
        ).fetchone()
    assert row is not None
    assert row[1] == result.compatibilita


# --- fixture reali ---

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "matcher"


def _load_bando(filename: str) -> Bando:
    data = json.loads((_FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    return Bando(**data)


def test_match_real_fixture_compatibile() -> None:
    bando = _load_bando("bando_compatibile.json")
    result = internal_match(bando, _profilo())
    assert result.compatibilita == "alta", (
        f"atteso 'alta', ottenuto '{result.compatibilita}' — "
        f"checklist: {[(c.requisito, c.esito) for c in result.checklist]}"
    )


def test_match_real_fixture_incompatibile() -> None:
    bando = _load_bando("bando_incompatibile.json")
    result = internal_match(bando, _profilo())
    assert result.compatibilita == "bassa", (
        f"atteso 'bassa', ottenuto '{result.compatibilita}' — "
        f"checklist: {[(c.requisito, c.esito) for c in result.checklist]}"
    )
