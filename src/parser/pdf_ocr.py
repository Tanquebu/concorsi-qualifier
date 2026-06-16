from pathlib import Path


def extract_text_ocr(file_path: Path) -> str | None:
    """OCR su PDF con pytesseract (lingua ita). Restituisce None se testo estratto < 50 char."""
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(str(file_path), last_page=10)
        parts = [pytesseract.image_to_string(img, lang="ita") for img in images]
        text = "\n".join(parts).strip()
        return text if len(text) >= 50 else None
    except Exception:
        return None
