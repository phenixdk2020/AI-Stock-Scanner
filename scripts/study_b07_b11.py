"""B-07 (StockMap-køb bekræftet af sektor-ETF) og B-11 (MTI sektor-del: aktie mod sektor-ETF dobbelt grøn).

Samme køb, samme simulate() og summarize() som `scan_cli.py --salg` og scripts/study_b08_b12.py.
Varianter på StockMap-køb: uden filter, sektor tipper op, MTI-sektor dobbelt grøn, begge dele. Alle varianter
måles på samme grundlag (køb hvor begge sektorsignaler kan beregnes), ellers ville ETF'ernes korte historik
(XLRE 2015, XLC 2018) forskyde sammenligningen.
Kørsel: .venv/Scripts/python scripts/study_b07_b11.py [--periode 15y] [--urort 2024-11-01] [--max N]
Historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stockscanner.exits import (  # noqa: E402
    MAX_DAYS, _daily, exit_signals, simulate, stockmap_entries, stockmap_exit_days, summarize,
)
from stockscanner.market_data import fetch_history  # noqa: E402
from stockscanner.sector_rs import (  # noqa: E402
    benchmark_for, ensure_sector_map, flags_on, rs_flags, sector_confirmed, sector_etf, sector_rotation,
)

RULES = ["StockMap", "Supertrend x3", "SMA50", "Fast 60 dage"]
VARIANTS = ["uden filter", "sektor op", "MTI-sektor grøn", "begge"]


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


def welch(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 5 or len(b) < 5:
        return None
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periode", default="15y")
    ap.add_argument("--urort", default="2024-11-01")
    ap.add_argument("--kurtage", type=float, default=0.1)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--cache", default=str(ROOT / "data" / "cache_b07"))
    a = ap.parse_args()
    warnings.filterwarnings("ignore")
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    tickers = load_universe()[: a.max or None]

    # 1) sektor pr. aktie (cache i data/sector_map.json), hentet parallelt
    sector_file = ROOT / "data" / "sector_map.json"
    from stockscanner.sector_rs import fetch_sector_info, load_sector_map, save_sector_map
    mapping = load_sector_map(sector_file)
    todo = [t for t in tickers if t not in mapping]
    with ThreadPoolExecutor(8) as pool:
        for ticker, info in zip(todo, pool.map(fetch_sector_info, todo)):
            mapping[ticker] = info
    if todo:
        save_sector_map(sector_file, mapping)
    etf_of = {t: sector_etf(t, mapping.get(t)) for t in tickers}
    print(f"Sektor kendt for {sum(v is not None for v in etf_of.values())} af {len(tickers)} aktier.", file=sys.stderr)

    # 2) kurser (aktier, sektor-ETF'er, brede benchmarks) til cachen
    needed = set(tickers) | {e for e in etf_of.values() if e} | {"RSP", "EXSA.DE"}

    def prefetch(ticker):
        try:
            get_prices(ticker, a.periode, cache)
        except Exception as error:
            print(f"{ticker}: kunne ikke hentes – {error}", file=sys.stderr)
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(prefetch, sorted(needed)))

    # 3) sektor-rotation pr. ETF (én gang)
    rotations: dict[str, pd.DataFrame] = {}
    for etf in sorted({e for e in etf_of.values() if e}):
        try:
            bench = "EXSA.DE" if etf.endswith(".DE") else "RSP"
            rotations[etf] = sector_rotation(get_prices(etf, a.periode, cache), get_prices(bench, a.periode, cache))
        except Exception as error:
            print(f"{etf}: rotation fejlede – {error}", file=sys.stderr)
    bench_rsp = get_prices("RSP", a.periode, cache)

    results: dict[tuple, list] = {}
    stats = {"aktier": 0, "uden sektor": 0, "køb": 0, "grundlag": 0, "sektor op": 0, "mti": 0, "begge": 0}
    by_sector: dict[str, list[float]] = {}
    for n, ticker in enumerate(tickers, 1):
        etf = etf_of.get(ticker)
        if not etf or etf not in rotations:
            stats["uden sektor"] += 1
            continue
        try:
            prices = get_prices(ticker, a.periode, cache)
            daily = _daily(prices)
            if len(daily) < 400:
                continue
            exits = exit_signals(prices)
            sells = stockmap_exit_days(prices, bench_rsp)
            entries = stockmap_entries(prices, bench_rsp)
            flags = rs_flags(prices, get_prices(etf, a.periode, cache))
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
            continue
        stats["aktier"] += 1
        subsets: dict[str, list] = {v: [] for v in VARIANTS}
        for entry in entries:
            day = entry[0]
            stats["køb"] += 1
            up, green = sector_confirmed(rotations[etf], day), flags_on(flags, day)
            if up is None or green is None:
                continue
            stats["grundlag"] += 1
            subsets["uden filter"].append(entry)
            if up:
                subsets["sektor op"].append(entry)
                stats["sektor op"] += 1
            if green:
                subsets["MTI-sektor grøn"].append(entry)
                stats["mti"] += 1
            if up and green:
                subsets["begge"].append(entry)
                stats["begge"] += 1
        for variant, subset in subsets.items():
            for rule in RULES:
                for t in simulate(prices, subset, rule, exits, sells, a.kurtage):
                    part = "urørt" if t.entry_day >= pd.Timestamp(a.urort) else "udvikling"
                    results.setdefault((variant, part, rule), []).append(t)
        # Forskel bekræftet/ikke bekræftet kræver også de afviste handler
        for label, keep in (("sektor op", set(map(id, subsets["sektor op"]))), ("MTI-sektor grøn", set(map(id, subsets["MTI-sektor grøn"])))):
            rejected = [e for e in subsets["uden filter"] if id(e) not in keep]
            for rule in RULES:
                for t in simulate(prices, rejected, rule, exits, sells, a.kurtage):
                    part = "urørt" if t.entry_day >= pd.Timestamp(a.urort) else "udvikling"
                    results.setdefault((f"ikke: {label}", part, rule), []).append(t)
        if n % 25 == 0:
            print(f"... {n}/{len(tickers)}", file=sys.stderr)

    f = lambda x, d=1: "–" if x is None else f"{x:.{d}f}"
    print(f"B-07/B-11: {stats['aktier']} aktier med sektor-ETF ({stats['uden sektor']} uden sektor), {a.periode}, "
          f"kurtage {a.kurtage} %/handel, urørt fra {a.urort}.")
    print(f"StockMap-køb i alt {stats['køb']}, med begge sektorsignaler (grundlag) {stats['grundlag']}; "
          f"heraf sektor op {stats['sektor op']}, MTI-sektor grøn {stats['mti']}, begge {stats['begge']}.\n")
    cols = f"{'Variant':<22}{'Regel':<15}{'Handler':>8}{'Snit %':>8}{'Median':>8}{'Win %':>7}{'PF':>6}{'Dage':>6}{'%/100d':>8}{'Værste5%':>9}{'Maks%':>7}"
    for part in ("udvikling", "urørt"):
        print(f"[{part}]\n  {cols}")
        for variant in VARIANTS + ["ikke: sektor op", "ikke: MTI-sektor grøn"]:
            for rule in RULES:
                trades = results.get((variant, part, rule), [])
                s = summarize(trades)
                if not s["trades"]:
                    continue
                print(f"  {variant:<22}{rule:<15}{s['trades']:>8}{f(s['mean_pct']):>8}{f(s['median_pct']):>8}{f(s['win_rate'], 0):>7}"
                      f"{f(s['profit_factor'], 2):>6}{f(s['days'], 0):>6}{f(s['pct_per_100d'], 2):>8}{f(s['worst_p5']):>9}"
                      f"{100 * sum(t.days >= MAX_DAYS for t in trades) / len(trades):>7.0f}")
        print()
    print("Forskel i snit % (bekræftet minus ikke bekræftet) og Welch-t (handler overlapper, så t er optimistisk):")
    for part in ("udvikling", "urørt"):
        for label in ("sektor op", "MTI-sektor grøn"):
            for rule in RULES:
                ok = np.array([t.return_pct for t in results.get((label, part, rule), [])])
                no = np.array([t.return_pct for t in results.get((f"ikke: {label}", part, rule), [])])
                if len(ok) and len(no):
                    t = welch(ok, no)
                    print(f"  {part:<10}{label:<17}{rule:<15} {ok.mean():>6.1f} (n={len(ok)}) mod {no.mean():>6.1f} (n={len(no)})  "
                          f"forskel {ok.mean() - no.mean():>+5.1f}  t={f(t, 2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
