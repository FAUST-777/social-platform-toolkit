from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from hot_products.config import load_config
from hot_products.pipeline import collect_signals, write_signals
from hot_products.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="hot-products")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Collect product signals and write to Google Sheets.")
    run_parser.add_argument("--config", type=Path, default=Path("config/sources.yml"))
    run_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    load_dotenv()
    settings = Settings()

    if args.command == "run":
        config = load_config(args.config)
        signals = collect_signals(config, settings)
        if args.dry_run:
            print(json.dumps([signal.to_sheet_row() for signal in signals], ensure_ascii=False, indent=2))
            return
        write_signals(settings, signals)
        print(f"Appended {len(signals)} rows to Google Sheet.")
