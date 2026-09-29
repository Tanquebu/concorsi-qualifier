from pathlib import Path
from tempfile import TemporaryDirectory


_OCR_TEMP = Path("data/ocr_tmp")


def extract_text_ocr(file_path: Path) -> str | None:
    """OCR delle prime 10 pagine, una alla volta, con immagini su disco."""
    try:
        import pytesseract
        from pdf2image import convert_from_path, pdfinfo_from_path

        pages = min(int(pdfinfo_from_path(str(file_path))["Pages"]), 10)
        _OCR_TEMP.mkdir(parents=True, exist_ok=True)
        parts = []
        for page in range(1, pages + 1):
            # /tmp sull'host è tmpfs: usare data/ per non occupare RAM con le immagini.
            # La directory viene rimossa dopo ogni pagina, anche in caso di errore.
            with TemporaryDirectory(prefix="page-", dir=_OCR_TEMP) as output_dir:
                images = convert_from_path(
                    str(file_path), first_page=page, last_page=page,
                    output_folder=output_dir, paths_only=True, fmt="png", thread_count=1,
                )
                for image_path in images:
                    parts.append(pytesseract.image_to_string(str(image_path), lang="ita"))
        text = "\n".join(parts).strip()
        return text if len(text) >= 50 else None
    except Exception:
        return None
