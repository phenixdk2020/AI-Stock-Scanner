"""Lokal SQLite-historik og persistent watchlist."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pandas as pd

from stockscanner.core import DEFAULT_TICKERS, ScanResult, parse_tickers


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "scans.sqlite3"
WATCHLIST_PATH = DATA_DIR / "watchlist.txt"


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
    with sqlite3.connect(path) as conn:
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


def save_scans(results: list[ScanResult], path: Path = DB_PATH) -> int:
    if not results:
        return 0
    initialize_db(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(path) as conn:
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
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query(
            """SELECT scanned_at_utc, market_date, ticker, price, currency,
                      change_21d_pct, rsi14, score, signal
               FROM scans ORDER BY scanned_at_utc DESC, id DESC LIMIT ?""",
            conn,
            params=(max(1, min(limit, 1000)),),
        )
