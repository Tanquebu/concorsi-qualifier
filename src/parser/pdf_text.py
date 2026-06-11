from pathlib import Path


def extract_text_pdf(file_path: Path) -> str | None:
    """Estrae testo da PDF con pdfplumber, fallback pypdf. Restituisce None se fallisce."""
    text = _try_pdfplumber(file_path)
    if text:
        return text
    return _try_pypdf(file_path)


def _try_pdfplumber(file_path: Path) -> str | None:
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            parts = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(parts).strip()
        return text if text else None
    except Exception:
        return None


def _try_pypdf(file_path: Path) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        parts = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(parts).strip()
        return text if text else None
    except Exception:
        return None
