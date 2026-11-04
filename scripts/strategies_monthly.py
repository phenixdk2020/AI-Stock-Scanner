"""B-10 fremadrettet papirsporing af MSS' fire algostrategier (Quality Momentum, TPI Plus, Value Momentum, Value Quality).

Kør én gang om måneden (første handelsdag): rangerer universet (`universe.load()`), skriver de øverste N
(standard 15, MSS tillader 5) med indgangskurs til `data/strategier/<strategi>.csv` (semikolon), og viser
afkastet af tidligere valg (lige vægt, pr. valgmåned) mod RSP siden samme dato. Idempotent pr. måned: kører
man igen i samme måned, tilføjes intet. Indgangskurs = seneste lukkekurs (papir, ingen omkostninger medregnet).
Kørsel: .venv/Scripts/python scripts/strategies_monthly.py [--n 15] [--benchmark RSP] [--ingen-kurser]
Historisk/papir-måling, IKKE en købsanbefaling.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stockscanner import strategies, universe  # noqa: E402

DIR = ROOT / "data" / "strategier"
COLUMNS = ["maaned", "dato", "ticker", "rang", "score", "indgangskurs"]


def load_log(name: str, directory: Path = DIR) -> pd.DataFrame:
    file = directory / f"{name}.csv"
    if not file.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(file, sep=";", encoding="utf-8-sig", dtype={"maaned": str, "dato": str})


def append_month(log: pd.DataFrame, picks: pd.DataFrame, prices: dict[str, float], today: date) -> pd.DataFrame:
    """Tilføj månedens valg. Allerede logget måned (ÅÅÅÅ-MM) gør ingenting; aktier uden kurs springes over."""
    month = f"{today:%Y-%m}"
    if (log["maaned"].astype(str) == month).any():
        return log
    rows = []
    for rank, (ticker, row) in enumerate(picks.iterrows(), 1):
        price = prices.get(ticker)
        if price is None or not price == price:
            continue
        rows.append({"maaned": month, "dato": str(today), "ticker": ticker, "rang": rank,
                     "score": round(float(row["score"]), 2), "indgangskurs": round(float(price), 4)})
    new = pd.DataFrame(rows, columns=COLUMNS)
    return new if log.empty else pd.concat([log, new], ignore_index=True) if rows else log


def returns_by_month(log: pd.DataFrame, last: dict[str, float], bench_entry: dict[str, float],
                     bench_last: float | None) -> pd.DataFrame:
    """Lige vægtet afkast (%) pr. valgmåned til seneste kurs, og RSP over samme periode."""
    out = []
    for month, group in log.groupby("maaned"):
        rets = [last[t] / float(p) - 1 for t, p in zip(group["ticker"], group["indgangskurs"]) if t in last and p]
        entry = bench_entry.get(month)
        out.append({"maaned": month, "antal": len(rets),
                    "afkast_pct": sum(rets) / len(rets) * 100 if rets else None,
                    "rsp_pct": (bench_last / entry - 1) * 100 if entry and bench_last else None})
    return pd.DataFrame(out)


def _last_close(prices: pd.DataFrame | None) -> float | None:
    if prices is None or prices.empty:
        return None
    close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
    return float(close.iloc[-1]) if len(close) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=strategies.TOP_N, help="antal aktier pr. strategi (15 eller 5)")
    ap.add_argument("--benchmark", default="RSP")
    ap.add_argument("--dir", default=str(DIR))
    ap.add_argument("--ingen-kurser", action="store_true", help="spring kursopslag over (kun valg)")
    a = ap.parse_args()
    directory = Path(a.dir)
    directory.mkdir(parents=True, exist_ok=True)
    factors = universe.load()
    if factors is None:
        print("Univers-cachen mangler eller er for gammel – kør build_universe.py først.")
        return 1
    from stockscanner.market_data import fetch_history

    def price_of(ticker):
        try:
            return _last_close(fetch_history(ticker, period="1mo")[0])
        except Exception:
            return None

    picks = strategies.rank_all(factors, a.n)
    today = date.today()
    bench_now = None if a.ingen_kurser else price_of(a.benchmark)
    print(f"Strategier {today} (top {a.n}, univers {len(factors)} aktier, benchmark {a.benchmark} {bench_now})")
    for name in strategies.STRATEGIES:
        log = load_log(name, directory)
        month = f"{today:%Y-%m}"
        fresh = not (log["maaned"].astype(str) == month).any()
        chosen = picks[name]
        prices = {} if a.ingen_kurser else {t: price_of(t) for t in set(chosen.index) | set(log["ticker"])}
        if fresh:
            log = append_month(log, chosen, prices, today)
            log[COLUMNS].to_csv(directory / f"{name}.csv", sep=";", index=False, encoding="utf-8-sig")
        print(f"\n{strategies.LABELS[name]}: {'nye valg ' + month if fresh else 'allerede logget ' + month} "
              f"({len(chosen)} aktier): {', '.join(chosen.index)}")
        # RSP-indgangskurser pr. valgmåned: gemmes som kolonne-fri sidefil, så sammenligningen overlever
        bench_file = directory / f"{a.benchmark}_indgang.csv"
        bench_entry = {}
        if bench_file.exists():
            bench_entry = dict(pd.read_csv(bench_file, sep=";", dtype={"maaned": str}).values)
        if bench_now and month not in bench_entry:
            bench_entry[month] = bench_now
            pd.DataFrame(sorted(bench_entry.items()), columns=["maaned", "kurs"]).to_csv(bench_file, sep=";", index=False)
        if not prices:
            continue
        table = returns_by_month(log, {t: p for t, p in prices.items() if p}, bench_entry, bench_now)
        if not table.empty:
            print(table.to_string(index=False, float_format=lambda v: f"{v:+.1f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
