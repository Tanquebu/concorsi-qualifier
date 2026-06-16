from pathlib import Path
from typing import Literal

from src.parser.pdf_ocr import extract_text_ocr
from src.parser.pdf_text import extract_text_pdf

_OCR_QUEUE = Path("data/ocr_queue.txt")


def _enqueue_ocr(bando_id: str) -> None:
    """Registra il bando_id nella coda OCR se non già presente."""
    _OCR_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if _OCR_QUEUE.exists():
        existing = set(_OCR_QUEUE.read_text().splitlines())
    if bando_id not in existing:
        with _OCR_QUEUE.open("a") as f:
            f.write(bando_id + "\n")

ParseMethod = Literal["pdf_text", "pdf_ocr", "html", "parse_failed"]


class ParseResult:
    def __init__(self, testo: str, parse_method: ParseMethod) -> None:
        self.testo = testo
        self.parse_method: ParseMethod = parse_method


def run_fallback_chain(file_path: Path) -> ParseResult:
    """Applica la chain: pdf_text → pdf_ocr → parse_failed. HTML gestito separatamente."""
    suffix = file_path.suffix.lower()

    if suffix in (".html", ".htm"):
        return _parse_html(file_path)

    if suffix == ".pdf":
        text = extract_text_pdf(file_path)
        if text:
            return ParseResult(testo=text, parse_method="pdf_text")

        text = extract_text_ocr(file_path)
        if text:
            return ParseResult(testo=text, parse_method="pdf_ocr")

    return ParseResult(testo="", parse_method="parse_failed")


def _parse_html(file_path: Path) -> ParseResult:
    try:
        from bs4 import BeautifulSoup

        html = file_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n").strip()

        allegato = file_path.with_suffix("").with_suffix(".allegato.pdf")
        if allegato.exists():
            pdf_text = extract_text_pdf(allegato) or ""
            if pdf_text:
                text = text + "\n\n--- ALLEGATO PDF ---\n\n" + pdf_text
            else:
                _enqueue_ocr(file_path.stem)

        return ParseResult(testo=text, parse_method="html")
    except Exception:
        return ParseResult(testo="", parse_method="parse_failed")
