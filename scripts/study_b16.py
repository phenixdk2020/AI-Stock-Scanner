"""B-16: TPI-analog (mønstergenkendelse) mod TPI-lite, udenfor stikprøve.

Samme signaltidspunkt, samme afkastberegning (køb næste dags åbning, 0,1 % pr. vej) for begge. Udviklingsperiode =
signaler og udfald før --urort; urørt = signaler fra --urort (de blev ikke brugt til at vælge k, funktioner eller
tærskler – de er fastlagt i tpi_analog.py før kørslen). MSS-reglen: lang grøn + oversolgt, hold 130 dage.
Kørsel: .venv/Scripts/python scripts/study_b16.py [--periode 20y] [--urort 2024-11-01] [--max N] [--k 20]
Historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import argparse
import pickle
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stockscanner.market_data import fetch_history  # noqa: E402
from stockscanner.tpi_analog import analog_states, state_returns  # noqa: E402
from stockscanner.tpi_lite import tpi_states  # noqa: E402

HORIZONS = (5, 20, 65, 130)
GROUPS = ["lang grøn / oversolgt", "lang grøn / neutral", "lang grøn / overkøbt",
          "lang rød / oversolgt", "lang rød / neutral", "lang rød / overkøbt"]


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


def one_ticker(args):
    ticker, period, cache, k = args
    warnings.filterwarnings("ignore")
    try:
        prices = get_prices(ticker, period, Path(cache))
        if len(prices) < 1500:
            return ticker, None
        lite = state_returns(tpi_states(prices), prices, HORIZONS)
        ana = state_returns(analog_states(prices, k), prices, HORIZONS)
        lite["ticker"] = ana["ticker"] = ticker
        lite["short_pct"] = tpi_states(prices)["short_pct"].reindex(lite["week"]).to_numpy()
        st = analog_states(prices, k)
        ana["short_pct"] = st["short_pct"].reindex(ana["week"]).to_numpy()
        return ticker, (lite, ana)
    except Exception as exc:  # noqa: BLE001
        return ticker, f"fejl: {exc}"


def period_split(df: pd.DataFrame, cutoff: pd.Timestamp):
    """Udvikling: signal før cutoff og udfaldet slut før cutoff (ingen overlap til den urørte periode)."""
    dev = df[df["week"] < cutoff].copy()
    for h in HORIZONS:
        dev.loc[dev[f"end_{h}d"] >= cutoff, f"{h}d"] = np.nan
    return {"udvikling": dev, "urørt": df[df["week"] >= cutoff].copy()}


def table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = {h: df[f"{h}d"].mean() for h in HORIZONS}
    rows.append({"gruppe": "ALLE uger", "n": len(df), **{f"{h}d": base[h] for h in HORIZONS}})
    for g in GROUPS:
        sub = df[df["group"] == g]
        rows.append({"gruppe": g, "n": len(sub), **{f"{h}d": sub[f"{h}d"].mean() for h in HORIZONS}})
    return pd.DataFrame(rows).set_index("gruppe")


def rule(df: pd.DataFrame) -> dict:
    """MSS-reglen: lang grøn + oversolgt, hold 130 dage."""
    sub = df[(df["long_green"]) & (df["state"] == "oversolgt")]["130d"].dropna()
    allr = df["130d"].dropna()
    green = df[df["long_green"]]["130d"].dropna()
    # uafhængigere mål: ét signal pr. aktie pr. kvartal er ikke muligt uden ticker; brug ugedatoernes gennemsnit
    by_week = sub.groupby(df.loc[sub.index, "week"]).mean()
    return {"n": len(sub), "snit": sub.mean(), "median": sub.median(), "andel_positiv": (sub > 0).mean() * 100,
            "alle_uger": allr.mean(), "lang_groen_alle": green.mean(), "merafkast_mod_alle": sub.mean() - allr.mean(),
            "merafkast_mod_lang_groen": sub.mean() - green.mean(), "uger_med_signal": len(by_week)}


def ic(df: pd.DataFrame, col: str, sign: float, h: int) -> float:
    d = df[[col, f"{h}d"]].dropna()
    return float((sign * d[col]).rank().corr(d[f"{h}d"].rank())) if len(d) > 100 else float("nan")


def md(t: pd.DataFrame) -> str:
    cols = ["n"] + [f"{h}d" for h in HORIZONS]
    lines = ["| gruppe | n | " + " | ".join(f"{h} d %" for h in HORIZONS) + " |", "|---|---:|" + "---:|" * len(HORIZONS)]
    for name, r in t.iterrows():
        lines.append(f"| {name} | {int(r['n'])} | " + " | ".join(fmt(r[c]) for c in cols[1:]) + " |")
    return chr(10).join(lines)


def fmt(x, nd=2):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periode", default="20y")
    ap.add_argument("--urort", default="2024-11-01")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cache", default=str(ROOT / "data" / "cache_b16"))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    warnings.filterwarnings("ignore")
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    tickers = load_universe()[: a.max or None]

    def prefetch(t):
        try:
            get_prices(t, a.periode, cache)
        except Exception:
            pass
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(prefetch, tickers))
    lites, anas, used = [], [], 0
    with ProcessPoolExecutor(a.workers) as pool:
        for ticker, res in pool.map(one_ticker, [(t, a.periode, str(cache), a.k) for t in tickers]):
            if isinstance(res, tuple):
                lites.append(res[0]); anas.append(res[1]); used += 1
            elif isinstance(res, str):
                print(ticker, res)
    lite, ana = pd.concat(lites, ignore_index=True), pd.concat(anas, ignore_index=True)
    # samme (aktie, uge)-mængde for begge, ellers sammenlignes forskellige perioder (analog starter senere)
    keys = lambda d: pd.MultiIndex.from_frame(d[["ticker", "week"]])  # noqa: E731
    common = keys(lite).intersection(keys(ana))
    lite, ana = lite[keys(lite).isin(common)].reset_index(drop=True), ana[keys(ana).isin(common)].reset_index(drop=True)
    cutoff = pd.Timestamp(a.urort)
    print(f"# B-16 TPI-analog mod TPI-lite – {used} aktier, k={a.k}, periode {a.periode}, urørt fra {a.urort}")
    for name, df in (("TPI-lite", lite), ("TPI-analog", ana)):
        print(f"\n## {name}: uger {df['week'].min().date()} – {df['week'].max().date()}, i alt {len(df)}")
        for per, part in period_split(df, cutoff).items():
            print(f"\n### {name} – {per} (n={len(part)})")
            print(md(table(part)))
            r = rule(part)
            print("MSS-regel (lang grøn + oversolgt, 130 d): " + ", ".join(f"{k}={fmt(v)}" for k, v in r.items()))
            ics = {h: ic(part, "short_pct", -1.0 if name == "TPI-lite" else 1.0, h) for h in HORIZONS}
            print("Rang-IC (oversolgthed mod afkast): " + ", ".join(f"{h}d={fmt(v, 3)}" for h, v in ics.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
