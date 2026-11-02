"""Lokal SQLite-historik og persistent watchlist."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

import pandas as pd

from stockscanner.core import DEFAULT_TICKERS, ScanResult, parse_tickers
from stockscanner.fundamentals import FundamentalData, fetch_fundamentals


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "scans.sqlite3"
WATCHLIST_PATH = DATA_DIR / "watchlist.txt"


@contextmanager
def _db(path: Path):
    """Åbn SQLite, commit ved succes og luk altid forbindelsen (kræves på Windows,
    ellers kan databasefilen ikke slettes/flyttes bagefter)."""
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def save_watchlist(symbols: list[str], path: Path = WATCHLIST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    valid = parse_tickers(",".join(symbols))
    path.write_text("\n".join(valid) + "\n", encoding="utf-8")


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[str]:
    if not path.exists():
        return DEFAULT_TICKERS.copy()
    try:
        return parse_tickers(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_TICKERS.copy()


def initialize_db(path: Path = DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _db(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at_utc TEXT NOT NULL,
                market_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                change_21d_pct REAL NOT NULL,
                sma50 REAL NOT NULL,
                sma200 REAL NOT NULL,
                rsi14 REAL NOT NULL,
                macd REAL NOT NULL,
                macd_signal REAL NOT NULL,
                relative_volume REAL,
                score INTEGER NOT NULL,
                signal TEXT NOT NULL,
                checks_json TEXT NOT NULL
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scans_ticker_time ON scans(ticker, scanned_at_utc DESC)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS fundamentals (
                ticker TEXT NOT NULL,
                fetched_at_utc TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (ticker)
            )"""
        )


def save_scans(results: list[ScanResult], path: Path = DB_PATH) -> int:
    if not results:
        return 0
    initialize_db(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db(path) as conn:
        conn.executemany(
            """INSERT INTO scans (
                scanned_at_utc, market_date, ticker, price, currency,
                change_21d_pct, sma50, sma200, rsi14, macd, macd_signal,
                relative_volume, score, signal, checks_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    now, item.market_date, item.ticker, item.price, item.currency,
                    item.change_21d_pct, item.sma50, item.sma200, item.rsi14,
                    item.macd, item.macd_signal, item.relative_volume, item.score,
                    item.signal, json.dumps(asdict(item)["checks"], ensure_ascii=False),
                )
                for item in results
            ],
        )
    return len(results)


def recent_scans(limit: int = 250, path: Path = DB_PATH) -> pd.DataFrame:
    initialize_db(path)
    with _db(path) as conn:
        return pd.read_sql_query(
            """SELECT scanned_at_utc, market_date, ticker, price, currency,
                      change_21d_pct, rsi14, score, signal
               FROM scans ORDER BY scanned_at_utc DESC, id DESC LIMIT ?""",
            conn,
            params=(max(1, min(limit, 1000)),),
        )


def save_fundamentals(data: FundamentalData, path: Path = DB_PATH) -> None:
    """Gem (eller erstat) regnskabstal for ét symbol i cachen."""
    initialize_db(path)
    with _db(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO fundamentals (ticker, fetched_at_utc, payload_json) VALUES (?, ?, ?)",
            (data.ticker, data.fetched_at_utc, json.dumps(data.to_dict(), ensure_ascii=False)),
        )


def get_cached_fundamentals(
    ticker: str,
    max_age_days: float = 7,
    path: Path = DB_PATH,
    now: datetime | None = None,
) -> FundamentalData | None:
    """Returnér cachede regnskabstal, hvis de findes og ikke er ældre end max_age_days."""
    initialize_db(path)
    with _db(path) as conn:
        row = conn.execute(
            "SELECT fetched_at_utc, payload_json FROM fundamentals WHERE ticker = ?", (ticker,)
        ).fetchone()
    if row is None:
        return None
    try:
        fetched = datetime.fromisoformat(row[0])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if (now or datetime.now(timezone.utc)) - fetched > timedelta(days=max_age_days):
            return None
        return FundamentalData.from_dict(json.loads(row[1]))
    except (ValueError, TypeError, KeyError):
        return None


def load_or_fetch_fundamentals(
    ticker: str,
    max_age_days: float = 7,
    path: Path = DB_PATH,
    fetcher=None,
) -> FundamentalData:
    """Brug cachen når den er frisk; ellers hent og gem. Hentefejl rejses videre."""
    cached = get_cached_fundamentals(ticker, max_age_days=max_age_days, path=path)
    if cached is not None:
        return cached
    data = fetch_fundamentals(ticker, fetcher=fetcher)
    save_fundamentals(data, path=path)
    return data
