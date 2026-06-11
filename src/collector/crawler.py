from datetime import date
from pathlib import Path

import httpx

from src.collector.dedup import compute_hash


def download_source(
    source: dict[str, str],
    raw_dir: Path,
    known_hashes: set[str],
) -> list[str]:
    """Scarica HTML o PDF da una fonte. Restituisce lista di hash nuovi scaricati."""
    url: str = source["url"]
    tipo: str = source.get("tipo", "html")
    today = str(date.today())
    file_hash = compute_hash(url, today)

    if file_hash in known_hashes:
        return []

    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except Exception:
        return []

    content_type = response.headers.get("content-type", "")
    if "pdf" in content_type or tipo == "pdf":
        ext = "pdf"
    else:
        ext = "html"

    dest = raw_dir / f"{file_hash}.{ext}"
    dest.write_bytes(response.content)
    return [file_hash]
