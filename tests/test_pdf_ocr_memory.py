from pathlib import Path
from unittest.mock import Mock

import pdf2image
import pytesseract

from src.parser import pdf_ocr


def test_ocr_renders_one_page_at_a_time_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_ocr, '_OCR_TEMP', tmp_path / 'ocr')
    monkeypatch.setattr(pdf2image, 'pdfinfo_from_path', Mock(return_value={'Pages': 14}))
    rendered = []

    def convert(source, **kwargs):
        assert kwargs['first_page'] == kwargs['last_page']
        assert kwargs['paths_only'] is True
        assert kwargs['thread_count'] == 1
        assert all(not path.exists() for path in rendered)
        image = Path(kwargs['output_folder']) / 'page.png'
        image.write_bytes(b'fake image')
        rendered.append(image)
        return [str(image)]

    def recognize(path, lang):
        assert isinstance(path, str)
        assert Path(path).exists()
        return 'Testo riconosciuto per questa pagina'

    monkeypatch.setattr(pdf2image, 'convert_from_path', convert)
    monkeypatch.setattr(pytesseract, 'image_to_string', recognize)
    result = pdf_ocr.extract_text_ocr(tmp_path / 'test.pdf')
    assert result.count('Testo riconosciuto') == 10
    assert len(rendered) == 10
    assert list((tmp_path / 'ocr').iterdir()) == []


def test_ocr_error_cleans_temporary_images(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_ocr, '_OCR_TEMP', tmp_path / 'ocr')
    monkeypatch.setattr(pdf2image, 'pdfinfo_from_path', Mock(return_value={'Pages': 1}))

    def fail(source, **kwargs):
        (Path(kwargs['output_folder']) / 'partial.png').write_bytes(b'partial')
        raise RuntimeError('conversion failed')

    monkeypatch.setattr(pdf2image, 'convert_from_path', fail)
    assert pdf_ocr.extract_text_ocr(tmp_path / 'test.pdf') is None
    assert list((tmp_path / 'ocr').iterdir()) == []
