"""B-08 (regressionskanal som salgsregel) og B-12 (ADX(14) > 25 som købsfilter).

Samme køb, samme simulate() og summarize() som `scan_cli.py --salg`. Regressionsreglerne lægges som ekstra
kolonner i salgssignalerne her, så exits.py er uændret. Univers: data/universe.txt (alle aktier, der kan hentes).
Kørsel: .venv/Scripts/python scripts/study_b08_b12.py [--periode 15y] [--urort 2024-11-01] [--max N]
Historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import argparse
import pickle
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stockscanner.exits import (  # noqa: E402
    MAX_DAYS, _daily, exit_signals, simulate, stockmap_entries, stockmap_exit_days, summarize, trend_entries,
)
from stockscanner.market_data import fetch_history  # noqa: E402
from stockscanner.regression import ADX_MIN, adx, regression_break  # noqa: E402

RULES = ["Supertrend x3", "SMA50", "Hybrid 20/50", "Regression 126", "Regression 252", "Fast 60 dage", "StockMap"]


def load_universe() -> list[str]:
    lines = (ROOT / "data" / "universe.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def get_prices(ticker: str, period: str, cache: Path) -> pd.DataFrame:
    file = cache / f"{ticker.replace('^', '_')}_{period}.pkl"
    if file.exists():
        return pickle.loads(file.read_bytes())
    prices = fetch_history(ticker, period=period)[0]
    file.write_bytes(pickle.dumps(prices))
    return prices


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periode", default="15y")
    ap.add_argument("--urort", default="2024-11-01")
    ap.add_argument("--benchmark", default="RSP")
    ap.add_argument("--kurtage", type=float, default=0.1)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--cache", default=str(ROOT / "data" / "cache_b08_b12"))
    a = ap.parse_args()
    warnings.filterwarnings("ignore")
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    tickers = load_universe()[: a.max or None]
    bench = get_prices(a.benchmark, a.periode, cache)
    def prefetch(ticker):
        try:
            get_prices(ticker, a.periode, cache)
        except Exception:
            pass
    with ThreadPoolExecutor(8) as pool:  # hent parallelt til cachen; selve testen kører bagefter
        list(pool.map(prefetch, tickers))
    results: dict[tuple, list] = {}
    used = 0
    for n, ticker in enumerate(tickers, 1):
        try:
            prices = get_prices(ticker, a.periode, cache)
            daily = _daily(prices)
            if len(daily) < 400:
                continue
            exits = exit_signals(prices)
            close = daily["Close"]
            exits["Regression 126"] = regression_break(close, 126).reindex(exits.index, fill_value=False)
            exits["Regression 252"] = regression_break(close, 252).reindex(exits.index, fill_value=False)
            sells = stockmap_exit_days(prices, bench)
            trend_ok = adx(daily) > ADX_MIN
            entry_sets = {"StockMap-køb": stockmap_entries(prices, bench), "Trendkøb": trend_entries(prices)}
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
            continue
        used += 1
        for name, entries in entry_sets.items():
            filtered = [e for e in entries if bool(trend_ok.get((e[0] if isinstance(e, tuple) else e), False))]
            for variant, subset in (("uden filter", entries), ("ADX>25", filtered)):
                for rule in RULES:
                    for t in simulate(prices, subset, rule, exits, sells, a.kurtage):
                        part = "urørt" if t.entry_day >= pd.Timestamp(a.urort) else "udvikling"
                        results.setdefault((name, variant, part, rule), []).append(t)
        if n % 25 == 0:
            print(f"... {n}/{len(tickers)}", file=sys.stderr)
    f = lambda x, d=1: "–" if x is None else f"{x:.{d}f}"
    print("Maks% = andel handler uden salgssignal, holdt til maksimum (504 dage).")
    print(f"B-08/B-12: {used} aktier, {a.periode}, kurtage {a.kurtage} %/handel, urørt fra {a.urort}.\n")
    cols = f"{'Regel':<16}{'Handler':>8}{'Snit %':>8}{'Median':>8}{'Win %':>7}{'PF':>6}{'Dage':>6}{'%/100d':>8}{'Værste':>8}{'Værste5%':>9}{'Fanget':>7}{'Maks%':>7}"
    for name in ("StockMap-køb", "Trendkøb"):
        for variant in ("uden filter", "ADX>25"):
            for part in ("udvikling", "urørt"):
                print(f"[{name}, {variant}, {part}]\n  {cols}")
                for rule in RULES:
                    trades = results.get((name, variant, part, rule), [])
                    s = summarize(trades)
                    if not s["trades"]:
                        continue
                    print(f"  {rule:<16}{s['trades']:>8}{f(s['mean_pct']):>8}{f(s['median_pct']):>8}{f(s['win_rate'], 0):>7}"
                          f"{f(s['profit_factor'], 2):>6}{f(s['days'], 0):>6}{f(s['pct_per_100d'], 2):>8}{f(s['worst_mean']):>8}"
                          f"{f(s['worst_p5']):>9}{f(s['capture'], 0):>7}"
                          f"{100 * sum(t.days >= MAX_DAYS for t in trades) / len(trades):>7.0f}")
                print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
