"""Regnskabsrisiko: advarsel op til et regnskab, IKKE et købs- eller salgssignal.

Vurderes kun fra `EARNINGS_WINDOW_DAYS` dage før regnskabet. Tre punkter giver hver ét point:
1. analytikerne har sænket EPS-estimaterne de seneste 30 dage (samme grænse som value trap, analyst.TRAP_DROP_30D_PCT),
2. flere negative end positive nyheder de seneste 7 dage,
3. kursen er steget mindst 15 % de seneste 30 handelsdage (høj forventning).
0 point = Lav, 1 = Middel, 2-3 = Høj. Manglende data giver ikke point, men står som "ingen data" i begrundelsen.
Regnskabsbevægelsen (hvor meget aktien plejer at flytte sig) påvirker IKKE niveauet; den vises ved siden af.
Regnskabsrisiko ændrer aldrig handling, salgsregler eller købsspærrer. Hver vurdering logges i
`data/regnskabsrisiko_log.csv`, og udfaldet fyldes ud når regnskabet er passeret, så punkt 1 og 2 (som ikke kan
backtestes) kan vurderes ud fra loggen efter nogle regnskabssæsoner.
"""
from __future__ import annotations

import csv
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from stockscanner.analyst import TRAP_DROP_30D_PCT

EARNINGS_WINDOW_DAYS = 14   # vurderes kun fra så mange dage før regnskabet
NEWS_DAYS = 7
RUN_UP_PCT = 15.0
RUN_UP_TRADING_DAYS = 30
MAX_EARNINGS = 8            # de seneste regnskaber der indgår i bevægelsen
MIN_EARNINGS = 4            # færre end dette: "for få regnskaber"
NO_DATA = "ingen data"
DISCLAIMER = "Risikomål, ikke et salgssignal."

LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "regnskabsrisiko_log.csv"
LOG_COLUMNS = ["dato", "ticker", "regnskabsdato", "niveau", "point", "begrundelser", "lukkekurs", "udfald_pct"]
REASON_SEPARATOR = " | "


def in_window(days_left: int | None) -> bool:
    return days_left is not None and 0 <= days_left <= EARNINGS_WINDOW_DAYS


# --- de tre punkter: True = point, False = intet point, None = ingen data -------------------------------------

def estimates_cut(info) -> bool | None:
    """Er et af årenes EPS-estimater faldet mindst TRAP_DROP_30D_PCT på 30 dage? None uden data (AnalystInfo)."""
    revisions = getattr(info, "revisions", None)
    if not revisions:
        return None
    changes = [c["30d"] for c in revisions.values() if isinstance(c, dict) and c.get("30d") is not None]
    if not changes:
        return None
    return any(change <= -TRAP_DROP_30D_PCT for change in changes)


def negative_news(items, today: date) -> tuple[bool | None, int, int]:
    """(flest negative?, plus, minus) for vurderede nyheder de seneste NEWS_DAYS dage; None uden vurderede nyheder."""
    cutoff = str(today - timedelta(days=NEWS_DAYS))
    recent = [i for i in (items or []) if i.published >= cutoff and i.sentiment in ("positiv", "negativ", "neutral")]
    if not recent:
        return None, 0, 0
    plus = sum(i.sentiment == "positiv" for i in recent)
    minus = sum(i.sentiment == "negativ" for i in recent)
    return minus > plus, plus, minus


def run_up(prices: pd.DataFrame | None) -> tuple[bool | None, float | None]:
    """(steget mindst RUN_UP_PCT de seneste RUN_UP_TRADING_DAYS handelsdage?, ændring i %). None uden nok kurser."""
    if prices is None or prices.empty or "Close" not in prices.columns:
        return None, None
    close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
    if len(close) <= RUN_UP_TRADING_DAYS or close.iloc[-1 - RUN_UP_TRADING_DAYS] <= 0:
        return None, None
    change = 100 * (close.iloc[-1] / close.iloc[-1 - RUN_UP_TRADING_DAYS] - 1)
    return bool(round(change, 6) >= RUN_UP_PCT), float(change)


def level_of(points: int) -> str:
    return "Lav" if points <= 0 else "Middel" if points == 1 else "Høj"


def assess(days_left: int | None, info, news_items, prices, today: date) -> dict | None:
    """None når regnskabet ikke er inden for vinduet (eller datoen er ukendt); ellers niveau, point og begrundelser."""
    if not in_window(days_left):
        return None
    points, reasons = 0, []
    cut = estimates_cut(info)
    if cut is None:
        reasons.append(f"estimater: {NO_DATA}")
    elif cut:
        points += 1
        reasons.append("analytikerne har sænket estimaterne de seneste 30 dage")
    negative, plus, minus = negative_news(news_items, today)
    if negative is None:
        reasons.append(f"nyheder: {NO_DATA}")
    elif negative:
        points += 1
        reasons.append(f"flest negative nyheder de seneste 7 dage ({minus}− mod {plus}+)")
    risen, change = run_up(prices)
    if risen is None:
        reasons.append(f"kursudvikling: {NO_DATA}")
    elif risen:
        points += 1
        reasons.append(f"kursen er steget {change:.0f} % på {RUN_UP_TRADING_DAYS} handelsdage")
    if points == 0 and not reasons:
        reasons.append("ingen advarselstegn")
    return {"level": level_of(points), "points": points, "reasons": reasons}


# --- regnskabsbevægelse ---------------------------------------------------------------------------------------

def move_for(history: pd.DataFrame | None, earnings: date) -> float | None:
    """% fra lukkekursen før datoen til lukkekursen dagen efter datoen (første handelsdag efter). None uden begge."""
    if history is None or history.empty or "Close" not in history.columns:
        return None
    close = pd.to_numeric(history["Close"], errors="coerce").dropna()
    close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    day = pd.Timestamp(earnings)
    before, after = close[close.index < day], close[close.index > day]
    if before.empty or after.empty or before.iloc[-1] <= 0:
        return None
    return float(100 * (after.iloc[0] / before.iloc[-1] - 1))


def past_moves(history: pd.DataFrame | None, dates, limit: int = MAX_EARNINGS) -> list[float]:
    """Bevægelse for de seneste `limit` regnskaber (nyeste først) hvor kurserne dækker både før og efter."""
    moves = []
    for earnings in sorted({_as_date(d) for d in dates if d is not None}, reverse=True):
        move = move_for(history, earnings)
        if move is not None:
            moves.append(move)
        if len(moves) >= limit:
            break
    return moves


def move_stats(moves: list[float]) -> dict:
    """Gennemsnitlig absolut bevægelse, andel fald og antal; med under MIN_EARNINGS regnskaber kun antallet."""
    count = len(moves)
    if count < MIN_EARNINGS:
        return {"count": count, "avg_abs_pct": None, "down_share_pct": None, "note": "for få regnskaber"}
    return {"count": count, "avg_abs_pct": sum(abs(m) for m in moves) / count,
            "down_share_pct": 100 * sum(m < 0 for m in moves) / count, "note": None}


def load_earnings_dates(ticker: str, limit: int = 12) -> list[date]:
    """Tidligere regnskabsdatoer fra yfinance `get_earnings_dates`; enhver fejl giver en tom liste."""
    try:
        import yfinance as yf

        frame = yf.Ticker(ticker).get_earnings_dates(limit=limit)
        if frame is None or getattr(frame, "empty", True):
            return []
        return sorted({_as_date(i) for i in frame.index})
    except Exception:
        return []


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    return value


def build_risks(rows, analyst, news_items, histories, today: date, dates_loader=load_earnings_dates) -> dict[str, dict]:
    """Regnskabsrisiko pr. ticker for rækker med regnskab inden for vinduet. Rører aldrig rækkerne."""
    from stockscanner.analyst import days_to_earnings

    risks = {}
    for row in rows:
        info = analyst.get(row.ticker)
        earnings = None if info is None else info.earnings_date
        history = histories.get(row.ticker)
        result = assess(days_to_earnings(earnings, today), info, news_items.get(row.ticker), history, today)
        if result is None:
            continue
        try:
            stats = move_stats(past_moves(history, dates_loader(row.ticker)))
        except Exception:
            stats = move_stats([])
        close = None
        if history is not None and not history.empty:
            series = pd.to_numeric(history["Close"], errors="coerce").dropna()
            close = float(series.iloc[-1]) if len(series) else None
        risks[row.ticker] = {**result, **stats, "earnings": str(earnings), "close": close}
    return risks


def describe(risk: dict) -> str:
    """Én linje til konsollen: niveau, begrundelser og hvor meget aktien plejer at bevæge sig."""
    text = f"Regnskabsrisiko: {risk['level']} ({'; '.join(risk['reasons'])})"
    if risk.get("avg_abs_pct") is None:
        text += f"; {risk.get('note') or 'for få regnskaber'}"
    else:
        text += (f"; plejer at bevæge sig ±{risk['avg_abs_pct']:.0f} %, falder i {risk['down_share_pct']:.0f} % af "
                 f"{risk['count']} regnskaber")
    return text + ". " + DISCLAIMER


# --- log ------------------------------------------------------------------------------------------------------

def read_log(path: Path = LOG_FILE) -> list[dict]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            return [{c: row.get(c, "") or "" for c in LOG_COLUMNS} for row in csv.DictReader(handle, delimiter=";")]
    except OSError:
        return []


def write_log(rows: list[dict], path: Path = LOG_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def log_assessments(risks: dict[str, dict], today: date, path: Path = LOG_FILE) -> int:
    """Én række pr. (ticker, regnskabsdato); en ny vurdering overskriver den gamle frem til regnskabet.
    Rækker hvor udfaldet er udfyldt røres ikke. Returnerer antal skrevne rækker i alt."""
    rows = read_log(path)
    index = {(r["ticker"], r["regnskabsdato"]): n for n, r in enumerate(rows)}
    for ticker, risk in risks.items():
        entry = {"dato": str(today), "ticker": ticker, "regnskabsdato": risk["earnings"], "niveau": risk["level"],
                 "point": str(risk["points"]), "begrundelser": REASON_SEPARATOR.join(risk["reasons"]),
                 "lukkekurs": "" if risk.get("close") is None else f"{risk['close']:.4f}", "udfald_pct": ""}
        key = (ticker, risk["earnings"])
        if key in index:
            old = rows[index[key]]
            if old["udfald_pct"] != "":
                continue
            rows[index[key]] = entry
        else:
            index[key] = len(rows)
            rows.append(entry)
    if risks:
        write_log(rows, path)
    return len(rows)


def fill_outcomes(histories: dict[str, pd.DataFrame], today: date, path: Path = LOG_FILE) -> int:
    """Udfyld udfaldet (bevægelsen som past_moves) for rækker hvis regnskab er passeret og hvor kurserne dækker dagen
    efter. Idempotent: udfyldte rækker røres ikke. Returnerer antal nyudfyldte rækker."""
    rows = read_log(path)
    filled = 0
    for row in rows:
        if row["udfald_pct"] != "" or row["ticker"] not in histories:
            continue
        try:
            earnings = date.fromisoformat(row["regnskabsdato"])
        except ValueError:
            continue
        if earnings >= today:
            continue
        move = move_for(histories[row["ticker"]], earnings)
        if move is not None:
            row["udfald_pct"] = f"{move:.2f}"
            filled += 1
    if filled:
        write_log(rows, path)
    return filled
