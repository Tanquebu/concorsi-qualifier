from pathlib import Path

from src.parser.fallback_chain import ParseResult, run_fallback_chain


def parse(file_path: Path) -> ParseResult:
    return run_fallback_chain(file_path)


__all__ = ["parse", "ParseResult"]
