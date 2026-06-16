import json
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from src.collector.dedup import compute_hash


def download_source(
    source: dict[str, str],
    raw_dir: Path,
    known_hashes: set[str],
) -> list[str]:
    """Scarica bandi da una fonte. Restituisce lista di hash nuovi scaricati."""
    tipo: str = source.get("tipo", "html")

    if tipo == "wordpress":
        return _download_wordpress(source, raw_dir, known_hashes)
    elif tipo == "inpa_portal":
        return _download_inpa_portal(source, raw_dir, known_hashes)
    else:
        return _download_html_or_pdf(source, raw_dir, known_hashes)


def _download_html_or_pdf(
    source: dict[str, str],
    raw_dir: Path,
    known_hashes: set[str],
) -> list[str]:
    url: str = source["url"]
    tipo: str = source.get("tipo", "html")
    today = str(date.today())
    file_hash = compute_hash(url, today)

    if file_hash in known_hashes:
        return []

    raw_dir.mkdir(parents=True, exist_ok=True)

    response = httpx.get(url, follow_redirects=True, timeout=30.0)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    ext = "pdf" if ("pdf" in content_type or tipo == "pdf") else "html"

    dest = raw_dir / f"{file_hash}.{ext}"
    dest.write_bytes(response.content)

    meta = {"url": url, "fonte": source.get("nome", ""), "ext": ext, "scraped_at": today}
    (raw_dir / f"{file_hash}.meta.json").write_text(json.dumps(meta), encoding="utf-8")

    return [file_hash]


def _download_wordpress(
    source: dict[str, str],
    raw_dir: Path,
    known_hashes: set[str],
) -> list[str]:
    """Scarica bandi singoli via WordPress REST API."""
    base_url: str = source["url"].rstrip("/")
    fonte_nome: str = source.get("nome", "")
    per_page: int = int(source.get("per_page", "50"))
    today = str(date.today())

    api_url = f"{base_url}/wp-json/wp/v2/posts"
    params: dict[str, str | int] = {
        "per_page": per_page,
        "_fields": "id,title,link,date,content,categories",
        "orderby": "date",
        "order": "desc",
    }

    resp = httpx.get(api_url, params=params, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    posts = resp.json()

    raw_dir.mkdir(parents=True, exist_ok=True)
    nuovi: list[str] = []

    exclude: list[str] = [kw.lower() for kw in source.get("exclude_keywords", [])]
    include: list[str] = [kw.lower() for kw in source.get("include_keywords", [])]

    for post in posts:
        post_url: str = post["link"]
        post_date: str = post["date"][:10]
        file_hash = compute_hash(post_url, post_date)

        if file_hash in known_hashes:
            continue

        title = BeautifulSoup(post["title"]["rendered"], "html.parser").get_text()

        if exclude and any(kw in title.lower() for kw in exclude):
            continue
        if include and not any(kw in title.lower() for kw in include):
            continue
        body = post["content"]["rendered"]

        html_content = f"<html><head><title>{title}</title></head><body>{body}</body></html>"
        dest = raw_dir / f"{file_hash}.html"
        dest.write_text(html_content, encoding="utf-8")

        meta = {
            "url": post_url,
            "fonte": fonte_nome,
            "ext": "html",
            "scraped_at": today,
            "title": title,
            "published": post_date,
        }
        (raw_dir / f"{file_hash}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        nuovi.append(file_hash)

    return nuovi


_INPA_MEDIA_BASE = "https://portale.inpa.gov.it/api/media"


def _download_allegato_pdf(media_id: str, dest: Path) -> None:
    """Scarica un allegato PDF dal portale InPA. Fallisce silenziosamente."""
    try:
        r = httpx.get(f"{_INPA_MEDIA_BASE}/{media_id}", follow_redirects=True, timeout=30.0)
        r.raise_for_status()
        if "pdf" in r.headers.get("content-type", ""):
            dest.write_bytes(r.content)
    except Exception:
        pass


_INPA_PORTAL_API = (
    "https://portale.inpa.gov.it/concorsi-smart/api/concorso-public-area/search-better"
)


def _download_inpa_portal(
    source: dict[str, str],
    raw_dir: Path,
    known_hashes: set[str],
) -> list[str]:
    """Scarica bandi aperti via API REST del portale InPA."""
    fonte_nome: str = source.get("nome", "")
    per_page: int = int(source.get("per_page", "50"))
    today = str(date.today())

    body = {
        "text": "",
        "categoriaId": None,
        "regioneId": source.get("regioneId") or None,
        "status": ["OPEN"],
        "settoreId": source.get("settoreId") or None,
        "provinciaCodice": None,
        "dateFrom": None,
        "dateTo": None,
        "salaryMin": None,
        "salaryMax": None,
        "enteRiferimentoName": "",
    }

    raw_dir.mkdir(parents=True, exist_ok=True)
    nuovi: list[str] = []
    _min_attivi_per_page = 5

    page = 0
    while True:
        resp = httpx.post(
            _INPA_PORTAL_API,
            params={"page": page, "size": per_page},
            json=body,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        bandi_page = data.get("content", [])
        if not bandi_page:
            break

        attivi_page = [
            b for b in bandi_page
            if b.get("dataScadenza") and b["dataScadenza"] > today + "T"
        ]
        page += 1
        if page > 1 and len(attivi_page) < _min_attivi_per_page:
            break

        for bando in bandi_page:
                bando_id: str = bando["id"]
                pub_date: str = (bando.get("dataPubblicazione") or today)[:10]
                canonical_url = f"https://www.inpa.gov.it/bandi-e-avvisi/dettaglio-bando-avviso/?concorso_id={bando_id}"
                file_hash = compute_hash(canonical_url, pub_date)

                if file_hash in known_hashes:
                    continue

                titolo = bando.get("titolo", "")
                enti = ", ".join(bando.get("entiRiferimento") or [])
                sedi = ", ".join(bando.get("sedi") or [])
                posti = bando.get("numPosti")
                scadenza = (bando.get("dataScadenza") or "")[:10]
                figura = bando.get("figuraRicercata", "")
                tipo_proc = bando.get("tipoProcedura", "")
                link_ext = bando.get("linkReindirizzamento") or ""
                descrizione = bando.get("descrizione") or bando.get("descrizioneBreve") or ""

                html = (
                    f"<html><head><title>{titolo}</title></head><body>"
                    f"<h1>{titolo}</h1>"
                    f"<p><strong>Ente:</strong> {enti}</p>"
                    f"<p><strong>Sede:</strong> {sedi}</p>"
                    f"<p><strong>Posti:</strong> {posti}</p>"
                    f"<p><strong>Scadenza domande:</strong> {scadenza}</p>"
                    f"<p><strong>Figura ricercata:</strong> {figura}</p>"
                    f"<p><strong>Tipo procedura:</strong> {tipo_proc}</p>"
                    + (f"<p><strong>Link candidatura:</strong> {link_ext}</p>" if link_ext else "")
                    + f"<div>{descrizione}</div>"
                    f"</body></html>"
                )

                dest = raw_dir / f"{file_hash}.html"
                dest.write_text(html, encoding="utf-8")

                # Scarica il PDF del bando principale se presente
                allegati = bando.get("allegati") or []
                for allegato in allegati:
                    if allegato.get("tipo") == "BANDO_CONCORSO":
                        media_id = allegato.get("mediaId")
                        if media_id:
                            _download_allegato_pdf(media_id, raw_dir / f"{file_hash}.allegato.pdf")
                        break

                meta = {
                    "url": canonical_url,
                    "fonte": fonte_nome,
                    "ext": "html",
                    "scraped_at": today,
                    "title": titolo,
                    "published": pub_date,
                }
                (raw_dir / f"{file_hash}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
                nuovi.append(file_hash)

    return nuovi
