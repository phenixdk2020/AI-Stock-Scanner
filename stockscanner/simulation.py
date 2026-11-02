"""Porteføljesimulering (byggeplan punkt 6): MSS-lignende regler samlet, uge for uge.

Køb (fredag lukning → mandag åbning): StockMap simpelt køb; valgfrit krav om MTI-lite på ugebasis og
markedsindeks (andel af universet over SMA50 > 50 %). Salg: Supertrend ×3 er vendt ned eller StockMap-
salg (tjekkes ugentligt). Højst `max_positions` lige store positioner (MSS: ca. 40 à 2,5 %).
Kun kursbaserede regler: Quality/Value kan ikke testes ærligt bagud (ingen point-in-time-regnskaber).
Overlevelsesbias: universet er aktier, der findes i dag. Historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from stockscanner.exits import supertrend
from stockscanner.stockmap import rotation, signals


def _daily(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce").copy()
    index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    frame.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    return frame[~frame.index.duplicated(keep="last")].sort_index().dropna()


def weekly_panel(histories: dict[str, pd.DataFrame], benchmark: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Pr. ticker en ugetabel: buy, sell, st_down, rs_up (MTI-lite uge), above50, close, next_open."""
    panel = {}
    for ticker, raw in histories.items():
        daily = _daily(raw)
        if len(daily) < 300:
            continue
        rot = rotation(daily, benchmark)
        if rot.empty:
            continue
        sig = signals(rot)
        weeks = rot.index
        up = supertrend(daily, 10, 3.0)
        sma50 = daily["Close"].rolling(50, min_periods=50).mean()
        positions = daily.index.searchsorted(weeks, side="right") - 1  # sidste handelsdag i ugen
        valid = positions >= 0
        last_day = daily.index[np.clip(positions, 0, len(daily) - 1)]
        next_pos = np.clip(positions + 1, 0, len(daily) - 1)
        table = pd.DataFrame({
            "buy": (sig == "køb").to_numpy(),
            "sell": (sig == "salg").to_numpy(),
            "st_down": ~up.reindex(last_day).fillna(True).to_numpy(dtype=bool),
            "rs_up": (rot["x"] > rot["x"].ewm(span=10, adjust=False).mean()).to_numpy(),
            "above50": (daily["Close"].reindex(last_day) > sma50.reindex(last_day)).to_numpy(),
            "close": daily["Close"].reindex(last_day).to_numpy(),
            "next_open": np.where(positions + 1 < len(daily), daily["Open"].to_numpy()[next_pos], np.nan),
        }, index=weeks)[valid]
        panel[ticker] = table
    return panel


@dataclass(frozen=True)
class SimResult:
    equity: pd.Series
    trades: pd.DataFrame
    cagr: float
    max_drawdown: float
    win_rate: float | None


def simulate(panel: dict[str, pd.DataFrame], start: str, end: str | None = None, max_positions: int = 40,
             require_mti: bool = False, require_breadth: bool = False, cost_pct: float = 0.1) -> SimResult:
    weeks = sorted(set().union(*(t.index for t in panel.values())))
    weeks = [w for w in weeks if w >= pd.Timestamp(start) and (end is None or w <= pd.Timestamp(end))]
    cash, holdings, trades, curve = 1.0, {}, [], {}
    breadth = pd.concat({t: p["above50"] for t, p in panel.items()}, axis=1).mean(axis=1)
    for week in weeks:
        rows = {t: p.loc[week] for t, p in panel.items() if week in p.index}
        # værdi ved ugens lukning
        value = cash + sum(h["shares"] * rows[t]["close"] for t, h in holdings.items() if t in rows and np.isfinite(rows[t]["close"]))
        curve[week] = value
        # salg
        for ticker in list(holdings):
            row = rows.get(ticker)
            if row is None or not np.isfinite(row["next_open"]):
                continue
            if row["st_down"] or row["sell"]:
                h = holdings.pop(ticker)
                proceeds = h["shares"] * row["next_open"] * (1 - cost_pct / 100)
                cash += proceeds
                trades.append({"ticker": ticker, "buy_week": h["week"], "sell_week": week,
                               "return_pct": (row["next_open"] / h["price"] - 1) * 100 - 2 * cost_pct})
        # køb
        market_ok = (not require_breadth) or breadth.get(week, 0) > 0.5
        if market_ok and len(holdings) < max_positions:
            candidates = [t for t, r in rows.items() if t not in holdings and r["buy"] and np.isfinite(r["next_open"])
                          and (not require_mti or r["rs_up"])]
            slot = value / max_positions
            for ticker in sorted(candidates):
                if len(holdings) >= max_positions or cash < slot * 0.5:
                    break
                price = rows[ticker]["next_open"]
                spend = min(slot, cash)
                holdings[ticker] = {"shares": spend * (1 - cost_pct / 100) / price, "price": price, "week": week}
                cash -= spend
    equity = pd.Series(curve).sort_index()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    max_dd = float((equity / equity.cummax() - 1).min())
    trade_frame = pd.DataFrame(trades)
    win = float((trade_frame["return_pct"] > 0).mean() * 100) if len(trade_frame) else None
    return SimResult(equity, trade_frame, float(cagr), max_dd, win)


def buy_and_hold(prices: pd.DataFrame, start: str, end: str | None = None) -> tuple[float, float]:
    """(CAGR, max drawdown) for køb-og-hold af fx RSP på ugelukninger."""
    close = _daily(prices)["Close"].resample("W-FRI").last().dropna()
    close = close[(close.index >= pd.Timestamp(start)) & ((close.index <= pd.Timestamp(end)) if end else True)]
    years = max((close.index[-1] - close.index[0]).days / 365.25, 1e-9)
    return float((close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1), float((close / close.cummax() - 1).min())
