"""Mellem to mandagslister: opdatér Entry for de fulgte aktier i den seneste playbook.

StockMap følger afsluttede uger, så tjekket finder ikke nye ugesignaler midt på ugen. Det fanger, at kurs,
værdikanal, regnskabsspærring eller estimater ændrer, om alle købskrav er opfyldt. Kvalitet, nyheder og resten af
playbooken bliver stående fra mandagskørslen. Ejede aktier røres ikke; deres salgsregler hører til mandagslisten.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from stockscanner import playbook

BUY = "KØB-KANDIDAT"
OWNED = ("BEHOLD (ejet)", "SÆLG (ejet)")
FRESH_FIELDS = ("action", "reasons", "stockmap", "quadrant", "angle", "price", "channel_score", "peg",
                "asymmetry", "asymmetry_inf", "earnings", "eps_trend", "candle")


def latest_factors(path: Path) -> pd.DataFrame:
    """Seneste række pr. aktie fra mandagslistens historik, med tal uden afrunding."""
    history = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    return history.sort_values("dato").groupby("ticker").tail(1).set_index("ticker")


def followed(payload: dict, wanted) -> list[str]:
    """De ønskede aktier, der har en fuld analyse og ikke er ejede."""
    wanted = set(wanted)
    return [ticker for ticker, stock in payload["stocks"].items()
            if ticker in wanted and stock.get("action") not in OWNED]


def apply(payload: dict, rows, histories: dict, now: datetime) -> list[str]:
    """Skriv rækkerne ind i `payload` og returnér ændringerne ind og ud af Entry."""
    changes = []
    stocks = payload["stocks"]
    for row in rows:
        stock = stocks.get(row.ticker)
        if stock is None or stock.get("action") in OWNED:
            continue
        before = stock.get("action")
        if before != row.action and row.action == BUY:
            changes.append(f"{row.ticker}: Entry nu (var {before})")
        elif before == BUY and row.action != BUY:
            changes.append(f"{row.ticker}: ikke længere Entry ({row.reasons})")
        fresh = playbook.stock_entry(row, histories[row.ticker], None, "", None)
        stock.update({field: fresh[field] for field in FRESH_FIELDS})
        stock["entry_checked"] = now.date().isoformat()
    dates = [pd.Timestamp(h.index[-1]).date() for h in histories.values() if len(h)]
    if dates:
        payload["market_date"] = str(max(dates))
    payload["changes"] = changes + list(payload.get("changes") or [])
    return changes
