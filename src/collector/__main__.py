import argparse
import logging
from pathlib import Path

import src.env  # noqa: F401
from src.collector import run_collector

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scarica bandi dalle fonti configurate")
    parser.add_argument(
        "sources_config", nargs="?", default="config/sources.yaml", type=Path
    )
    parser.add_argument("--db", default="concorsi.db", type=Path, metavar="PATH")
    parser.add_argument("--raw", default="data/raw", type=Path, metavar="DIR")
    args = parser.parse_args()

    print(f"Collector avviato — fonti: {args.sources_config}")
    result = run_collector(args.sources_config, db_path=args.db, raw_dir=args.raw)
    print(
        f"Completato: {result.n_nuovi} nuovi, {result.n_duplicati} già visti"
        f" | status={result.status}"
    )
    if result.errori:
        print("Errori di download:")
        for e in (result.errori or []):
            print(f"  - {e}")


if __name__ == "__main__":
    main()
