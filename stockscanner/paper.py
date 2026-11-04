"""Papirportefølje (B-14): mandagslistens køb-kandidater "købes" på papir til lukkekursen, og samme
salgsregler som for ejede aktier lukker dem. Måler fremad, uge for uge, om reglerne virker – uden
look-ahead, fordi hver handel logges den dag, den sker. `data/papir_portefolje.csv` (semikolon).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from stockscanner.portfolio import Position, exit_check

PAPER_FILE = Path(__file__).resolve().parent.parent / "data" / "papir_portefolje.csv"
COLUMNS = ["ticker", "koebsdato", "koebskurs", "salgsdato", "salgskurs", "salgsgrund"]
AMOUNT = 10000.0   # samme beløb pr. papirhandel


def load(path: Path = PAPER_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype={"salgsgrund": str})


def save(frame: pd.DataFrame, path: Path = PAPER_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame[COLUMNS].to_csv(path, sep=";", index=False, encoding="utf-8-sig")


def open_positions(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["salgsdato"].isna() | (frame["salgsdato"].astype(str).str.strip() == "")]


def _last_close(prices: pd.DataFrame) -> float | None:
    close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
    return None if close.empty else float(close.iloc[-1])


def update(frame: pd.DataFrame, rows, histories: dict, today: date) -> tuple[pd.DataFrame, list[str]]:
    """Luk åbne papirhandler hvor en salgsregel rammer, og åbn nye for dagens køb-kandidater.
    `rows`: mandagslistens WeeklyRow'er. Returnerer ny tabel og en liste med beskeder."""
    frame = frame.copy()
    messages = []
    by_ticker = {r.ticker: r for r in rows}
    for index, trade in open_positions(frame).iterrows():
        prices = histories.get(trade["ticker"])
        if prices is None or prices.empty or str(trade["koebsdato"]) >= str(today):
            continue  # aldrig salg samme dag som købet (flere kørsler samme dag)
        row = by_ticker.get(trade["ticker"])
        position = Position(trade["ticker"], 0, float(trade["koebskurs"]), pd.Timestamp(trade["koebsdato"]).date())
        reasons = exit_check(prices, position, row is not None and row.action == "pil ned")
        price = _last_close(prices)
        if reasons and price is not None:
            frame.loc[index, ["salgsdato", "salgskurs", "salgsgrund"]] = [str(today), price, "; ".join(reasons)]
            messages.append(f"PAPIR SALG {trade['ticker']} {price:.2f} ({(price / float(trade['koebskurs']) - 1) * 100:+.1f} %)")
    held = set(open_positions(frame)["ticker"])
    for row in rows:
        if row.action != "KØB-KANDIDAT" or row.ticker in held:
            continue
        price = _last_close(histories.get(row.ticker, pd.DataFrame({"Close": []})))
        if price is None:
            continue
        frame = pd.concat([frame, pd.DataFrame([{"ticker": row.ticker, "koebsdato": str(today), "koebskurs": price}])],
                          ignore_index=True)
        messages.append(f"PAPIR KØB {row.ticker} {price:.2f}")
    return frame.reindex(columns=COLUMNS), messages


def summary(frame: pd.DataFrame, last_prices: dict[str, float]) -> dict:
    """Afkast pr. handel (lukkede til salgskurs, åbne til seneste kurs) og samlet med samme beløb pr. handel."""
    if frame.empty:
        return {"handler": 0, "aabne": 0, "afkast_pct": None, "gevinst": 0.0, "vundne_pct": None}
    returns = []
    for _, trade in frame.iterrows():
        sold = pd.notna(trade["salgskurs"]) and str(trade["salgskurs"]).strip() != ""
        end = float(trade["salgskurs"]) if sold else last_prices.get(trade["ticker"])
        if end is not None:
            returns.append(end / float(trade["koebskurs"]) - 1)
    if not returns:
        return {"handler": len(frame), "aabne": len(open_positions(frame)), "afkast_pct": None, "gevinst": 0.0,
                "vundne_pct": None}
    mean = sum(returns) / len(returns)
    return {"handler": len(frame), "aabne": len(open_positions(frame)), "afkast_pct": mean * 100,
            "gevinst": sum(returns) * AMOUNT, "vundne_pct": 100 * sum(r > 0 for r in returns) / len(returns)}
