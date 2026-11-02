"""Årlig EPS-historik for amerikanske selskaber fra SEC EDGAR (gratis, officielle XBRL-data).

Bruges til værdikanalens P/E-historik over 10–20 år, som yfinance ikke har (ca. 4 år).
Ticker → CIK via EDGAR's søgeindeks; EPS fra companyfacts (us-gaap EarningsPerShareDiluted,
ellers Basic), kun 10-K/20-F med en periode på ca. et år; den senest indleverede værdi for hver
periode vinder (omarbejdede tal). Resultater caches i data/sec/.
SEC's adgangsregler: højst 10 kald/sek; kontakt kan sættes i miljøvariablen SEC_USER_AGENT.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

CACHE = Path(__file__).resolve().parent.parent / "data" / "sec"
USER_AGENT = os.environ.get("SEC_USER_AGENT", "AI-Stock-Scanner/0.6 private research")
MIN_INTERVAL = 0.2  # sekunder mellem kald (højst 5/sek)
CACHE_DAYS = 30
_last_call = 0.0


def _get(url: str) -> dict:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()
    response = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}, timeout=30)
    response.raise_for_status()
    return response.json()


def _cached(name: str, fetch, max_age_days: int = CACHE_DAYS):
    path = CACHE / name
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_days * 86400:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _ticker_map() -> dict[str, int]:
    """SEC's officielle ticker→CIK-liste (company_tickers.json), cachet; nøgler med store bogstaver."""
    raw = _cached("company_tickers.json", lambda: _get("https://www.sec.gov/files/company_tickers.json"))
    return {str(row["ticker"]).upper(): int(row["cik_str"]) for row in raw.values() if row.get("ticker")}


def cik_for(ticker: str) -> int | None:
    """CIK for en amerikansk ticker: eksakt match i SEC's ticker-liste (BRK-B/BRK.B begge), ellers EDGAR's søgeindeks."""
    symbol = ticker.upper().replace(".", "-")
    try:
        mapping = _ticker_map()
    except (requests.RequestException, ValueError, KeyError):
        mapping = {}
    for key in (symbol, symbol.replace("-", ".")):
        if key in mapping:
            return mapping[key]
    for key, cik in mapping.items():  # SEC bruger '-' eller '.' som delimiter
        if key.replace(".", "-") == symbol:
            return cik
    hits = _cached(f"cik_{symbol}.json", lambda: _get(
        f"https://efts.sec.gov/LATEST/search-index?keysTyped={symbol}"), max_age_days=365)
    for hit in hits.get("hits", {}).get("hits", []):
        tickers = [t.strip().upper() for t in str(hit.get("_source", {}).get("tickers", "")).split(",")]
        if symbol in tickers:
            return int(hit["_id"])
    return None


def annual_eps_from_facts(facts: dict) -> pd.Series:
    """Årlig EPS pr. regnskabsårets slutdato ud fra et companyfacts-dokument."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for concept in ("EarningsPerShareDiluted", "EarningsPerShareBasic"):
        units = gaap.get(concept, {}).get("units", {})
        entries = units.get("USD/shares") or next(iter(units.values()), [])
        best: dict[str, tuple[str, float]] = {}
        for entry in entries:
            if entry.get("form") not in ("10-K", "10-K/A", "20-F") or not entry.get("start"):
                continue
            days = (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days
            if not 330 <= days <= 400:
                continue
            filed = entry.get("filed", "")
            if entry["end"] not in best or filed > best[entry["end"]][0]:
                best[entry["end"]] = (filed, float(entry["val"]))
        if best:
            series = pd.Series({pd.Timestamp(end): val for end, (_, val) in best.items()}).sort_index()
            return series
    return pd.Series(dtype=float)


def split_adjust(eps: pd.Series, splits: pd.Series) -> pd.Series:
    """Del EPS før hvert aktiesplit med split-faktoren, så den passer til splitjusterede kurser."""
    adjusted = eps.astype(float).copy()
    for when, ratio in splits.items():
        if ratio and ratio > 0 and ratio != 1:
            moment = pd.Timestamp(when)
            moment = moment.tz_localize(None) if moment.tz is not None else moment
            adjusted[adjusted.index < moment] /= ratio
    return adjusted


def annual_eps(ticker: str) -> pd.Series:
    """Årlig EPS-historik (ikke splitjusteret) for en amerikansk ticker; tom ved ukendt selskab."""
    cik = cik_for(ticker)
    if cik is None:
        return pd.Series(dtype=float)
    facts = _cached(f"facts_{cik:010d}.json", lambda: _get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"))
    return annual_eps_from_facts(facts)
