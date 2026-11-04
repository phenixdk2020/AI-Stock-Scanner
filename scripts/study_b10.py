"""B-10: ærlig bagtest af de to PRIS-baserede dele af MSS' fire algostrategier (momentum og TPI-lite oversolgt).

Quality/Value kan ikke bagtestes (ingen point-in-time-regnskaber) – se docs/RESULTAT-B10.md.
Hver måned (første handelsdag) købes top N lige vægt til åbningskursen, signalet bruger kun lukkekurser til og
med dagen før; omkostninger 1,5 %/år (0,125 %/md), benchmark RSP. Udvikling til 2024-10-31, urørt fra 2024-11-01.
Overlevelsesbias: universet er aktier, der findes i dag. Lokale valutaer, ingen FX. IKKE en købsanbefaling.
Kørsel: .venv/Scripts/python scripts/study_b10.py [--periode 15y] [--n 15] [--urort 2024-11-01] [--max N]
"""
from __future__ import annotations

import argparse
import pickle
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stockscanner.market_data import fetch_history  # noqa: E402
from stockscanner.scores import MOMENTUM_MONTHS, percentile_score  # noqa: E402
from stockscanner.tpi_lite import tpi_states  # noqa: E402

COST_PER_MONTH = 1.5 / 12 / 100


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


def _clean(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices[["Open", "Close"]].apply(pd.to_numeric, errors="coerce")
    index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    frame.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    return frame[~frame.index.duplicated(keep="last")].sort_index().dropna()


def momentum_table(close: pd.DataFrame, pos: int) -> pd.DataFrame:
    """Momentumfaktorer pr. ticker ud fra lukkekurser til og med række `pos` (som scores.momentum_factors)."""
    out = {}
    for months in MOMENTUM_MONTHS:
        out[f"ret_{months}m"] = close.iloc[pos] / close.iloc[pos - 21 * months] - 1
    sample = close.iloc[pos - 252: pos + 1: 21]
    out["stability"] = (sample.pct_change().iloc[1:] > 0).mean().where(sample.notna().all())
    return pd.DataFrame(out)


def run(close: pd.DataFrame, opens: pd.DataFrame, tpi: dict, n: int, kind: str):
    """Månedlig rebalancering. Returnerer (månedsafkast-serie, antal valgte pr. md, udskiftning pr. md)."""
    firsts = close.index.to_series().groupby([close.index.year, close.index.month]).first().tolist()
    rets, counts, turns, prev = {}, [], [], set()
    for i, day in enumerate(firsts[:-1]):
        pos = close.index.get_loc(day) - 1  # signal fra dagen før
        if pos < 260:
            continue
        if kind == "mom":
            picks = percentile_score(momentum_table(close, pos)).sort_values(ascending=False).head(n).index
        else:  # TPI-lite oversolgt i lang optrend, mest oversolgt først
            cand = {}
            for t, states in tpi.items():
                s = states[states.index <= close.index[pos]]
                if s.empty or s.index[-1] < close.index[pos] - pd.Timedelta(days=10):
                    continue
                last = s.iloc[-1]
                if last["long_green"] and last["state"] == "oversolgt":
                    cand[t] = last["short_pct"]
            picks = pd.Series(cand, dtype=float).sort_values().head(n).index
        r = (opens.loc[firsts[i + 1], picks] / opens.loc[day, picks] - 1).dropna()
        gross = float(r.mean()) if len(r) else 0.0  # ingen valgte = kontanter
        rets[day] = (1 + gross) * (1 - (COST_PER_MONTH if len(r) else 0.0)) - 1
        counts.append(len(r))
        cur = set(picks)
        turns.append(len(cur - prev) / max(len(cur), 1) if prev else 1.0)
        prev = cur
    return pd.Series(rets), counts, turns


def bench_series(bench_open: pd.Series, firsts) -> pd.Series:
    out = {}
    for d, e in zip(firsts[:-1], firsts[1:]):
        if d in bench_open.index and e in bench_open.index:
            out[d] = bench_open[e] / bench_open[d] - 1
    return pd.Series(out)


def stats(m: pd.Series, bench: pd.Series) -> dict:
    m = m.dropna()
    b = bench.reindex(m.index)
    years = len(m) / 12
    eq = (1 + m).cumprod()
    return {"mdr": len(m), "cagr": (eq.iloc[-1] ** (1 / years) - 1) * 100,
            "maxdd": float((eq / eq.cummax() - 1).min() * 100),
            "bench_cagr": ((1 + b).prod() ** (1 / years) - 1) * 100,
            "slaar_pct": float((m > b).mean() * 100)}


def fmt(label: str, s: dict) -> str:
    return (f"{label:<40} {s['mdr']:>4} md  CAGR {s['cagr']:>6.1f} %  maxDD {s['maxdd']:>6.1f} %  "
            f"RSP {s['bench_cagr']:>5.1f} %  slår RSP {s['slaar_pct']:>3.0f} % af mdr")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periode", default="15y")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--urort", default="2024-11-01")
    ap.add_argument("--benchmark", default="RSP")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--cache", default=str(ROOT / "data" / "cache_b10"))
    a = ap.parse_args()
    warnings.filterwarnings("ignore")
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    tickers = load_universe()[: a.max or None]

    def load(t):
        try:
            return t, _clean(get_prices(t, a.periode, cache))
        except Exception:
            return t, None
    with ThreadPoolExecutor(8) as pool:
        data = {t: p for t, p in pool.map(load, tickers) if p is not None and len(p) >= 600}
    bench = _clean(get_prices(a.benchmark, a.periode, cache))
    close = pd.DataFrame({t: p["Close"] for t, p in data.items()}).reindex(bench.index).ffill(limit=5)
    opens = pd.DataFrame({t: p["Open"] for t, p in data.items()}).reindex(bench.index).ffill(limit=5)
    print(f"{len(data)} af {len(tickers)} aktier med historik; {close.index[0].date()} til {close.index[-1].date()}")
    tpi = {t: tpi_states(p[["Open", "Close"]]) for t, p in data.items()}
    firsts = close.index.to_series().groupby([close.index.year, close.index.month]).first().tolist()
    bm = bench_series(bench["Open"], firsts)
    cut = pd.Timestamp(a.urort)
    lines = []
    for kind, label in (("mom", "Momentum (kurs)"), ("tpi", "TPI-lite oversolgt+lang grøn")):
        m, counts, turns = run(close, opens, tpi, a.n, kind)
        m = m.reindex(m.index.intersection(bm.index))
        for name, part in (("udvikling", m[m.index < cut]), ("URØRT", m[m.index >= cut]), ("hele", m)):
            if len(part) >= 6:
                lines.append(fmt(f"{label} top{a.n} {name}", stats(part, bm)))
        lines.append(f"   gns. antal valgte {np.mean(counts):.1f}, måneder uden valg {sum(c == 0 for c in counts)}, "
                     f"udskiftning/md {np.mean(turns) * 100:.0f} %")
    ew = {}  # lige vægtet univers (uden omkostninger) som reference for overlevelsesbias
    for i, d in enumerate(firsts[:-1]):
        if d in bm.index and i >= 13:
            ew[d] = float((opens.loc[firsts[i + 1]] / opens.loc[d] - 1).dropna().mean())
    ew = pd.Series(ew)
    for name, part in (("udvikling", ew[ew.index < cut]), ("URØRT", ew[ew.index >= cut]), ("hele", ew)):
        lines.append(fmt(f"Lige vægtet univers {name}", stats(part, bm)))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
