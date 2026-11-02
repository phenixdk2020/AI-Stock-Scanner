"""Kør scanneren uden GUI, fx via Windows Opgavestyring."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import warnings

import pandas as pd

from stockscanner.candles import PATTERNS, backtest, eligible_signals, trade_backtest
from stockscanner.core import DEFAULT_TICKERS, analyze_prices, parse_tickers
from stockscanner.market_data import fetch_history
from stockscanner.quality import score_quality
from stockscanner.storage import load_or_fetch_fundamentals, load_watchlist, save_scans


def print_quality(tickers: list[str]) -> int:
    """Udskriv kvalitetsscore pr. symbol. Screening, ikke en købsanbefaling."""
    shown = 0
    for ticker in tickers:
        try:
            result = score_quality(load_or_fetch_fundamentals(ticker))
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
            continue
        shown += 1
        total = "–" if result.total is None else f"{result.total:.1f}"
        pillars = ", ".join(
            f"{name} {'–' if score is None else f'{score:.0f}'}" for name, score in result.pillars.items()
        )
        print(f"{result.ticker}: kvalitet {total}/100 ({result.label}) | dækning {result.coverage * 100:.0f} % | "
              f"{pillars} | {result.model_note} | år: {', '.join(result.data_years)}")
        if result.missing:
            print(f"    mangler: {', '.join(result.missing)}")
    print("Screening ud fra uofficielle regnskabsdata – ikke en købsanbefaling.")
    return 0 if shown else 1


def print_candles(tickers: list[str], period: str, cost_pct: float, require_pullback: bool,
                  target_r: float | None = None) -> int:
    """Seneste candle-signaler pr. symbol og backtest mod en tilfældig dag."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
    histories = {}
    for ticker in tickers:
        try:
            histories[ticker] = fetch_history(ticker, period=period)[0]
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
    if not histories:
        return 1
    print(f"Seneste signaler (kun i optrend{' efter tilbagerekyl' if require_pullback else ''}, sidste 5 dage):")
    for ticker, frame in histories.items():
        recent = eligible_signals(frame, require_pullback=require_pullback).tail(5)
        hits = [f"{day.date()} {PATTERNS[name]}" for day, row in recent.iterrows() for name in PATTERNS if row[name]]
        print(f"  {ticker}: {'; '.join(hits) or '–'}")
    print(f"\nBacktest {period}, {len(histories)} aktier, kurtage {cost_pct} % pr. handel "
          "(signal ved lukning, køb næste åbning, salg ved lukning efter N dage):")
    print("  Basis = alle dage; Kontekst = kun dage i samme optrend/rekyl. Edge = mønster minus basis.")
    print(f"  {'Mønster':<44}{'N':>6}{'Snit %':>9}{'Median %':>10}{'Hit %':>8}"
          f"{'Basis %':>9}{'Edge %':>9}{'Kontekst %':>12}{'K-edge %':>10}")
    fmt = lambda x: "–" if x is None else f"{x:.2f}"
    for row in backtest(histories, cost_pct=cost_pct, require_pullback=require_pullback):
        print(f"  {PATTERNS[row.pattern] + ' ' + row.horizon:<44}{row.signals:>6}{fmt(row.mean_pct):>9}"
              f"{fmt(row.median_pct):>10}{fmt(row.hit_rate_pct):>8}{fmt(row.baseline_mean_pct):>9}"
              f"{fmt(row.edge_pct):>9}{fmt(row.context_baseline_pct):>12}{fmt(row.context_edge_pct):>10}")
    print(f"\nHandler som i Daytrader.dk-guiden, på dagsdata: købsstop over trigger inden for 5 dage, stop-loss "
          f"under mønsteret{f', mål {target_r} R' if target_r else ''}, ellers salg ved lukning efter N holdedage.")
    print("  Basis = køb ved åbning en tilfældig dag, samme holdetid.")
    print(f"  {'Mønster':<44}{'Handler':>8}{'Snit %':>9}{'Hit %':>8}{'Snit R':>8}{'Stoppet %':>11}"
          f"{'Basis %':>9}{'Edge %':>9}")
    for row in trade_backtest(histories, hold_days=(1, 5, 20, 60), target_r=target_r,
                              cost_pct=cost_pct, require_pullback=require_pullback):
        print(f"  {PATTERNS[row.pattern] + f' {row.hold_days}d':<44}{row.trades:>8}{fmt(row.mean_pct):>9}"
              f"{fmt(row.hit_rate_pct):>8}{fmt(row.mean_r):>8}{fmt(row.stopped_pct):>11}"
              f"{fmt(row.baseline_pct):>9}{fmt(row.edge_pct):>9}")
    print("Historisk test på få aktier (overlevelsesbias, ingen out-of-sample) – ikke en købsanbefaling.")
    return 0


def main() -> int:
    # Dansk tekst skal være læsbar, også når output sendes gennem en pipe på Windows (cp1252).
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="AI-Stock-Scanner – daglig batchscanning")
    parser.add_argument("--tickers", help="Komma-separerede symboler; ellers gemt watchlist")
    parser.add_argument("--csv", type=Path, help="Skriv seneste resultater til CSV")
    parser.add_argument("--no-save", action="store_true", help="Undlad at gemme i SQLite")
    parser.add_argument(
        "--kvalitet", action="store_true",
        help="Vis kvalitetsscore (regnskabstal, cachet i 7 dage) i stedet for teknisk scanning",
    )
    parser.add_argument("--candles", action="store_true", help="Vis candle-signaler og backtest mod tilfældig dag")
    parser.add_argument("--periode", default="10y", help="Kurshistorik til --candles (yfinance-periode, fx 5y)")
    parser.add_argument("--kurtage", type=float, default=0.1, help="Kurtage i %% pr. handel til --candles")
    parser.add_argument("--uden-rekyl", action="store_true", help="--candles: kræv kun optrend, ikke tilbagerekyl")
    parser.add_argument("--maal", type=float, help="--candles: kursmål i R (fx 2 = to gange risikoen)")
    arguments = parser.parse_args()

    try:
        selected = parse_tickers(arguments.tickers) if arguments.tickers else load_watchlist()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if arguments.kvalitet:
        return print_quality(selected)
    if arguments.candles:
        return print_candles(selected, arguments.periode, arguments.kurtage, not arguments.uden_rekyl, arguments.maal)

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
