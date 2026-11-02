"""Analytiker-data til køb-filtrene: næste regnskabsdato (B-01) og faldende EPS-estimater (B-02, value trap).

MSS: køb ikke lige før et regnskab, og pas på aktier hvor analytikerne skærer i estimaterne
("Value Traps"). Data fra yfinance (`calendar`, `eps_trend`); alt der mangler giver None og blokerer ikke.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

EARNINGS_BLOCK_DAYS = 7      # intet køb når regnskabet kommer inden for så mange dage
TRAP_DROP_30D_PCT = 2.0      # value trap: estimatet er faldet mindst så meget på 30 dage …
TRAP_DROP_90D_PCT = 5.0      # … eller så meget på 90 dage
TREND_PERIODS = ("0y", "+1y")


@dataclass(frozen=True)
class AnalystInfo:
    earnings_date: date | None = None
    revisions: dict | None = None      # {"+1y": {"30d": -1.2, "90d": -4.0}, …} i procent
    trap: str | None = None            # tekst når estimaterne falder, ellers None


def next_earnings(calendar, today: date) -> date | None:
    """Første regnskabsdato i dag eller senere fra yfinance' `calendar` (dict eller DataFrame)."""
    if calendar is None:
        return None
    if isinstance(calendar, pd.DataFrame):
        calendar = calendar.to_dict()
    raw = calendar.get("Earnings Date") if hasattr(calendar, "get") else None
    if raw is None:
        return None
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    dates = sorted(pd.Timestamp(v).date() for v in values if v is not None and not pd.isna(v))
    upcoming = [d for d in dates if d >= today]
    return upcoming[0] if upcoming else None


def days_to_earnings(earnings: date | None, today: date) -> int | None:
    return None if earnings is None else (earnings - today).days


def earnings_blocks(earnings: date | None, today: date, days: int = EARNINGS_BLOCK_DAYS) -> bool:
    left = days_to_earnings(earnings, today)
    return left is not None and 0 <= left <= days


def revisions(eps_trend: pd.DataFrame | None) -> dict:
    """Procentvis ændring i EPS-estimatet nu mod 30 og 90 dage siden, for indeværende og næste år."""
    result = {}
    if eps_trend is None or getattr(eps_trend, "empty", True):
        return result
    for period in TREND_PERIODS:
        if period not in eps_trend.index:
            continue
        row = eps_trend.loc[period]
        now = row.get("current")
        if now is None or pd.isna(now):
            continue
        changes = {}
        for label, column in (("30d", "30daysAgo"), ("90d", "90daysAgo")):
            old = row.get(column)
            if old is not None and not pd.isna(old) and old > 0:
                changes[label] = 100 * (now - old) / old
        if changes:
            result[period] = changes
    return result


def value_trap(changes: dict) -> str | None:
    """Tekst når et af årenes estimater falder for meget; ellers None."""
    hits = []
    for period, change in changes.items():
        if change.get("30d") is not None and change["30d"] <= -TRAP_DROP_30D_PCT:
            hits.append(f"EPS {period} {change['30d']:+.1f} % på 30 d")
        elif change.get("90d") is not None and change["90d"] <= -TRAP_DROP_90D_PCT:
            hits.append(f"EPS {period} {change['90d']:+.1f} % på 90 d")
    return "value trap: " + ", ".join(hits) if hits else None


def fetch_analyst(ticker: str, today: date | None = None) -> AnalystInfo:
    import yfinance as yf

    today = today or date.today()
    handle = yf.Ticker(ticker)
    try:
        earnings = next_earnings(handle.calendar, today)
    except Exception:
        earnings = None
    try:
        changes = revisions(handle.eps_trend)
    except Exception:
        changes = {}
    return AnalystInfo(earnings, changes or None, value_trap(changes))
