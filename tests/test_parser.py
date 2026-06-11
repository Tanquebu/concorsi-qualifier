from pathlib import Path
from unittest.mock import patch

from src.parser import ParseResult, parse
from src.parser.fallback_chain import run_fallback_chain
from src.parser.pdf_text import extract_text_pdf

# --- pdf_text ---

def test_pdf_text_corrotto(tmp_path: Path) -> None:
    corrupted = tmp_path / "corrupted.pdf"
    corrupted.write_bytes(b"this is not a pdf at all %%%")
    result = extract_text_pdf(corrupted)
    assert result is None


def test_pdf_text_nonexistent(tmp_path: Path) -> None:
    result = extract_text_pdf(tmp_path / "missing.pdf")
    assert result is None


# --- fallback chain ---

def test_fallback_pdf_testuale(tmp_path: Path) -> None:
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"fake")
    with patch("src.parser.fallback_chain.extract_text_pdf", return_value="Testo bando estratto"):
        with patch("src.parser.fallback_chain.extract_text_ocr", return_value=None):
            result = run_fallback_chain(pdf)
    assert result.parse_method == "pdf_text"
    assert result.testo == "Testo bando estratto"


def test_fallback_pdf_scansionato(tmp_path: Path) -> None:
    pdf = tmp_path / "scansionato.pdf"
    pdf.write_bytes(b"fake")
    _OCR = "src.parser.fallback_chain.extract_text_ocr"
    ocr_patch = patch(_OCR, return_value="Testo via OCR lungo")
    with patch("src.parser.fallback_chain.extract_text_pdf", return_value=None), ocr_patch:
        result = run_fallback_chain(pdf)
    assert result.parse_method == "pdf_ocr"
    assert result.testo == "Testo via OCR lungo"


def test_fallback_parse_failed(tmp_path: Path) -> None:
    pdf = tmp_path / "corrotto.pdf"
    pdf.write_bytes(b"fake")
    with patch("src.parser.fallback_chain.extract_text_pdf", return_value=None):
        with patch("src.parser.fallback_chain.extract_text_ocr", return_value=None):
            result = run_fallback_chain(pdf)
    assert result.parse_method == "parse_failed"
    assert result.testo == ""


def test_fallback_html(tmp_path: Path) -> None:
    html_file = tmp_path / "bando.html"
    html_file.write_text(
        "<html><body><h1>Concorso</h1><p>Testo del bando pubblico</p></body></html>",
        encoding="utf-8",
    )
    result = run_fallback_chain(html_file)
    assert result.parse_method == "html"
    assert "Concorso" in result.testo
    assert result.testo != ""


# --- interfaccia pubblica ---

def test_parse_interface_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"fake")
    with patch("src.parser.fallback_chain.extract_text_pdf", return_value="Testo bando"):
        result = parse(pdf)
    assert isinstance(result, ParseResult)
    assert result.parse_method == "pdf_text"


def test_parse_interface_html(tmp_path: Path) -> None:
    html_file = tmp_path / "bando.html"
    html_file.write_text("<html><body><p>Bando di concorso</p></body></html>", encoding="utf-8")
    result = parse(html_file)
    assert isinstance(result, ParseResult)
    assert result.parse_method == "html"
