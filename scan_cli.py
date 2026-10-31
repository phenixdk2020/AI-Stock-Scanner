"""Kør scanneren uden GUI, fx via Windows Opgavestyring."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pandas as pd

from stockscanner.core import DEFAULT_TICKERS, analyze_prices, parse_tickers
from stockscanner.market_data import fetch_history
from stockscanner.storage import load_watchlist, save_scans


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-Stock-Scanner – daglig batchscanning")
    parser.add_argument("--tickers", help="Komma-separerede symboler; ellers gemt watchlist")
    parser.add_argument("--csv", type=Path, help="Skriv seneste resultater til CSV")
    parser.add_argument("--no-save", action="store_true", help="Undlad at gemme i SQLite")
    arguments = parser.parse_args()

    try:
        selected = parse_tickers(arguments.tickers) if arguments.tickers else load_watchlist()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    results = []
    failed = []
    for ticker in selected:
        try:
            frame, currency = fetch_history(ticker)
            results.append(analyze_prices(frame, ticker, currency))
        except Exception as error:
            failed.append({"ticker": ticker, "error": str(error)})

    if results and not arguments.no_save:
        save_scans(results)
    if arguments.csv is not None and results:
        arguments.csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([asdict(item) for item in results]).drop(columns=["checks"]).to_csv(
            arguments.csv, sep=";", index=False, encoding="utf-8-sig"
        )
    print(json.dumps(
        {"count": len(results), "results": [asdict(item) for item in results], "errors": failed},
        ensure_ascii=False, indent=2,
    ))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
