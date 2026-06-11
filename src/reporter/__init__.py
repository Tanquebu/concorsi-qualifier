from pathlib import Path

from src.extractor.models import Bando
from src.matcher.models import MatchResult
from src.reporter.chain import generate_explanation
from src.reporter.renderer import render_scheda

_DEFAULT_OUTPUT = Path("data/processed")


def generate_report(
    match_result: MatchResult,
    bando: Bando,
    output_dir: Path = _DEFAULT_OUTPUT,
) -> Path:
    """Genera la scheda Markdown per un bando e la salva in output_dir."""
    spiegazione = generate_explanation(match_result, bando)
    _, dest = render_scheda(match_result, bando, spiegazione, output_dir)
    return dest


__all__ = ["generate_report"]
