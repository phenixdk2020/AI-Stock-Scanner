"""Sektor-del til StockMap og MTI-lite (backlog B-07 og B-11). Ren research, ikke koblet på CLI eller hjemmeside.

B-07: et StockMap-køb på en aktie bekræftes kun, hvis aktiens sektor-ETF også tipper op (samme vinkelregel
som aktien, `stockmap.points_up`) mod det brede marked: RSP for USA-aktier, STOXX Europe 600 (EXSA.DE) for
europæiske.
B-11: relativ styrke aktie / sektor-ETF over sit EMA (samme logik som `mti_lite.mti_state`, dag 20 / uge 10),
som ekstra funktion; `mti_lite` er uændret.

Sektor hentes fra yfinance (`info['sector']`, `info['industry']`) og caches i data/sector_map.json.
USA: SPDR-sektor-ETF'erne (XLK, XLF …). Europa/Norden: iShares STOXX Europe 600-sektor-ETF'er på XETRA
(EXV1.DE …) – data verificeret på yfinance 03-11-2026 (15 år, alle 18 serier). Begrænsninger: Yahoos
sektorer er GICS-lignende, ETF'erne ICB-baserede, så mappingen er grov (fx havner kapitalforvaltere under
banker, forbrugsvarer spredes på tre ETF'er); ETF'erne er i EUR, aktierne i DKK/SEK/NOK/CHF/GBP, så valutaen
smitter ind i relativ styrke (som den også gør mod hjemmeindekset). Screening og historisk test, IKKE en
købsanbefaling.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

from stockscanner.mti_lite import DAILY_EMA, DEFAULT_INDEX, WEEKLY_EMA, _dated, home_index
from stockscanner.stockmap import StockMapParams, points_up, rotation

US_BROAD = "RSP"
EU_BROAD = "EXSA.DE"  # iShares STOXX Europe 600

US_SECTOR_ETF = {
    "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
    "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC",
}
# Europa: standard pr. Yahoo-sektor; `EU_INDUSTRY_HINTS` vælger en mere præcis ETF ud fra branchen.
EU_SECTOR_ETF = {
    "Technology": "EXV3.DE", "Financial Services": "EXV1.DE", "Healthcare": "EXV4.DE",
    "Consumer Cyclical": "EXH7.DE", "Consumer Defensive": "EXH3.DE", "Energy": "EXH1.DE",
    "Industrials": "EXH4.DE", "Basic Materials": "EXV6.DE", "Utilities": "EXH9.DE",
    "Real Estate": "EXI5.DE", "Communication Services": "EXV2.DE",
}
EU_INDUSTRY_HINTS = {
    "Financial Services": [("insurance", "EXH5.DE")],
    "Consumer Cyclical": [("auto", "EXV5.DE"), ("retail", "EXH8.DE")],
    "Consumer Defensive": [("household", "EXH7.DE"), ("personal", "EXH7.DE"), ("grocery", "EXH8.DE"),
                           ("discount", "EXH8.DE")],
    "Industrials": [("engineering", "EXV8.DE"), ("building", "EXV8.DE")],
    "Basic Materials": [("chemical", "EXV7.DE"), ("agricultural", "EXV7.DE")],
    "Communication Services": [("entertainment", "EXH6.DE"), ("broadcast", "EXH6.DE"),
                               ("publishing", "EXH6.DE"), ("advertising", "EXH6.DE")],
}


def is_european(ticker: str) -> bool:
    """Alt med kendt børssuffiks (.CO, .ST, .DE …) er europæisk; ellers USA-agtig."""
    return home_index(ticker) != DEFAULT_INDEX


def benchmark_for(ticker: str) -> str:
    return EU_BROAD if is_european(ticker) else US_BROAD


def sector_etf(ticker: str, info: dict | None) -> str | None:
    """Sektor-ETF for aktien ud fra {'sector', 'industry'} (None hvis sektor ukendt, fx ETF'er)."""
    sector = (info or {}).get("sector")
    if not sector:
        return None
    if not is_european(ticker):
        return US_SECTOR_ETF.get(sector)
    industry = str((info or {}).get("industry") or "").lower()
    for hint, etf in EU_INDUSTRY_HINTS.get(sector, []):
        if hint in industry:
            return etf
    return EU_SECTOR_ETF.get(sector)


def fetch_sector_info(ticker: str) -> dict:
    """{'sector', 'industry'} fra yfinance; tom dict ved fejl eller manglende sektor (ETF'er)."""
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return {}
    return {k: info[k] for k in ("sector", "industry") if info.get(k)}


def load_sector_map(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_sector_map(path: Path, mapping: dict[str, dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def ensure_sector_map(tickers: list[str], path: Path,
                      fetch: Callable[[str], dict] = fetch_sector_info) -> dict[str, dict]:
    """Hent kun de tickere, der ikke står i cachen (tomme svar huskes også, så de ikke hentes igen)."""
    mapping = load_sector_map(path)
    missing = [t for t in tickers if t not in mapping]
    for ticker in missing:
        mapping[ticker] = fetch(ticker)
    if missing:
        save_sector_map(path, mapping)
    return mapping


def sector_rotation(sector_prices: pd.DataFrame, benchmark: pd.DataFrame,
                    params: StockMapParams = StockMapParams()) -> pd.DataFrame:
    """StockMap-rotation for sektor-ETF'en (beregnes én gang pr. ETF og genbruges til alle aktier i sektoren)."""
    return rotation(sector_prices, benchmark, params)


def sector_confirmed(sector_rot: pd.DataFrame, date) -> bool | None:
    """True hvis sektorens pil peger op (270–360° / 0–90°) ved seneste afsluttede uge på eller før `date`.
    None hvis der endnu ikke findes en vinkel."""
    rot = sector_rot[sector_rot.index <= pd.Timestamp(date)]
    if rot.empty or pd.isna(rot["angle"].iloc[-1]):
        return None
    return bool(points_up(float(rot["angle"].iloc[-1])))


def _ffill_bool(flag: pd.Series, index: pd.Index) -> pd.Series:
    return flag.astype(float).reindex(index, method="ffill").fillna(0.0) > 0


def rs_flags(prices: pd.DataFrame, ref_prices: pd.DataFrame) -> pd.DataFrame:
    """Dagsserie af MTI-flag mod en reference (sektor-ETF): kolonnerne daily, weekly, double_green (bool) og
    valid (nok data til begge). Samme logik som `mti_lite.mti_state`: referencens lukning fra dagen før,
    RS over EMA20 (dag) og EMA10 (uge); ugeflaget gælder fra ugens fredag (aldrig en uafsluttet uge)."""
    close = _dated(prices["Close"])
    ref = _dated(ref_prices["Close"]).shift(1).reindex(close.index, method="ffill")
    rs = (close / ref).dropna()
    daily = rs > rs.ewm(span=DAILY_EMA, adjust=False).mean()
    weekly_rs = rs.resample("W-FRI").last().dropna()
    weekly_flag = weekly_rs > weekly_rs.ewm(span=WEEKLY_EMA, adjust=False).mean()
    weekly_valid = pd.Series(range(len(weekly_rs)), index=weekly_rs.index) >= WEEKLY_EMA + 1
    out = pd.DataFrame({"daily": daily, "weekly": _ffill_bool(weekly_flag, rs.index)})
    enough_days = pd.Series(range(len(rs)), index=rs.index) >= DAILY_EMA + 4
    out["valid"] = _ffill_bool(weekly_valid, rs.index) & enough_days
    out["double_green"] = out["daily"] & out["weekly"]
    return out


def flags_on(flags: pd.DataFrame, date) -> bool | None:
    """double_green ved seneste dag på eller før `date` (None hvis for lidt data)."""
    rows = flags[flags.index <= pd.Timestamp(date)]
    if rows.empty or not bool(rows["valid"].iloc[-1]):
        return None
    return bool(rows["double_green"].iloc[-1])


def mti_sector_state(prices: pd.DataFrame, sector_prices: pd.DataFrame) -> dict[str, bool | None]:
    """Som `mti_lite.mti_state`, men mod sektor-ETF'en: {'daily', 'weekly', 'double_green'} ved seneste lukning."""
    flags = rs_flags(prices, sector_prices)
    if flags.empty or not bool(flags["valid"].iloc[-1]):
        return {"daily": None, "weekly": None, "double_green": None}
    last = flags.iloc[-1]
    return {"daily": bool(last["daily"]), "weekly": bool(last["weekly"]), "double_green": bool(last["double_green"])}
