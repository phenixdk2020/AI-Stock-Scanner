"""Playbook-snapshot (schema 2) til aktier.hangar18.dk – se docs/PLAYBOOK-SNAPSHOT.md.

Bygges af mandagslisten og sendes med site_sync.send_playbook, så hjemmesiden altid viser seneste kørsel.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd

from stockscanner.exits import exit_signals, supertrend
from stockscanner.universe import liquidity_class, size_class


def _num(value, digits: int = 2):
    """JSON-venligt tal: None for manglende/uendelige værdier."""
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(value) else round(value, digits)


def exit_facts(prices: pd.DataFrame, stockmap_sell: bool, days: int = 365) -> dict:
    """Købsdato-uafhængige fakta til salgsreglen; hjemmesiden afgør selv ud fra brugerens købsdato."""
    up = supertrend(prices, 10, 3.0)
    signals = exit_signals(prices)
    def dates(column: str) -> list[str]:
        if signals.empty or column not in signals.columns:
            return []
        index = pd.DatetimeIndex(signals.index)
        since = index.max() - timedelta(days=days)
        hits = signals[signals[column].astype(bool)]
        return [str(pd.Timestamp(d).date()) for d in hits.index if pd.Timestamp(d) >= since]

    # Supertrend tæller kun som salg, hvis den er vendt ned EFTER brugerens købsdato (som portfolio.exit_check)
    return {"supertrend_down": bool(not up.empty and not bool(up.iloc[-1])),
            "supertrend_flips": dates("Supertrend x3"),
            "sma50_breaks": dates("SMA50"), "stockmap_sell": bool(stockmap_sell)}


def stock_entry(row, prices: pd.DataFrame, currency: str | None, region: str, atr_value) -> dict:
    close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
    infinite = row.asymmetry is not None and math.isinf(row.asymmetry)
    return {
        "region": region, "currency": currency, "price": _num(close.iloc[-1] if len(close) else None, 4),
        "atr14": _num(atr_value, 4), "action": row.action, "reasons": row.reasons,
        "stockmap": row.stockmap, "quadrant": row.quadrant, "angle": _num(row.angle, 1),
        "tpi": row.tpi, "mti": row.mti, "quality": _num(row.quality, 0), "moat": _num(row.moat, 0),
        "mss_score": _num(row.mss_score, 0), "value_pct": _num(row.value_pct, 0),
        "momentum": _num(row.momentum, 0), "channel_score": _num(row.channel_score, 0), "peg": _num(row.peg, 2),
        "asymmetry": None if infinite else _num(row.asymmetry, 2), "asymmetry_inf": infinite,
        "earnings": row.earnings, "eps_trend": row.eps_trend, "size": row.size, "liquidity": row.liquidity,
        "exit": exit_facts(prices, "StockMap-salg denne uge" in row.reasons),
    }


MAX_NEWS = 5


def earnings_risk_entry(risk: dict) -> dict:
    """Regnskabsrisiko (earnings_risk.build_risks) til payloaden. Kun en advarsel; ændrer aldrig `action`."""
    return {"level": risk["level"], "points": int(risk["points"]),
            "reasons": [str(r)[:160] for r in risk["reasons"]],
            "avg_move_pct": _num(risk.get("avg_abs_pct"), 1), "down_share_pct": _num(risk.get("down_share_pct"), 0),
            "count": int(risk.get("count") or 0), "note": risk.get("note")}

UNIVERSE_COLUMNS = ["ticker", "region", "quality", "value", "momentum", "moat",
                    "quality_r", "value_r", "momentum_r", "moat_r", "upside", "peg", "mcap_usd_bn",
                    "size", "liquidity"]


def universe_section(factors: pd.DataFrame | None, scores: pd.DataFrame | None,
                     regional: pd.DataFrame | None) -> dict:
    if factors is None or scores is None:
        return {"columns": UNIVERSE_COLUMNS, "rows": []}
    regional = regional if regional is not None else scores
    rows = []
    for ticker in factors.index:
        f, s, r = factors.loc[ticker], scores.loc[ticker], regional.loc[ticker]
        cap = f.get("x_mcap_usd")
        rows.append([ticker, f.get("region"), *(_num(s.get(k), 0) for k in ("quality", "value", "momentum", "moat")),
                     *(_num(r.get(k), 0) for k in ("quality", "value", "momentum", "moat")),
                     _num(f.get("x_upside"), 1), _num(f.get("x_peg"), 2),
                     None if _num(cap) is None else _num(float(cap) / 1e9, 1),
                     size_class(cap), liquidity_class(f.get("x_adv_usd"), f.get("x_idle_days"))])
    return {"columns": UNIVERSE_COLUMNS, "rows": rows}


def screener_section(factors: pd.DataFrame | None, scores: pd.DataFrame | None,
                     regional: pd.DataFrame | None) -> dict:
    from stockscanner.screeners import SCREENERS, screen

    out = {}
    for name, label in SCREENERS.items():
        hits_global = [] if factors is None else list(screen(name, factors, scores).index)
        hits_regional = [] if factors is None else list(screen(name, factors, regional).index)
        out[name] = {"label": label, "global": hits_global, "regional": hits_regional}
    return out


def paper_section(trades: pd.DataFrame, last_prices: dict[str, float]) -> dict:
    from stockscanner.paper import summary

    result = {k: (_num(v, 2) if isinstance(v, float) else v) for k, v in summary(trades, last_prices).items()}
    clean = lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() in ("", "nan") else v
    rows = []
    for _, t in trades.iterrows():
        rows.append({"ticker": t["ticker"], "koebsdato": clean(t["koebsdato"]), "koebskurs": _num(t["koebskurs"], 4),
                     "salgsdato": clean(t["salgsdato"]), "salgskurs": _num(clean(t["salgskurs"]), 4),
                     "salgsgrund": clean(t["salgsgrund"]), "seneste": _num(last_prices.get(t["ticker"]), 4)})
    return {"summary": result, "trades": rows}


def build_payload(*, rows, histories, currencies, regions, atrs, research, breadth, benchmark,
                  factors, scores, regional, trades, last_prices, changes, news=None, candidates=(),
                  earnings_risk=None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    market_date = max((pd.Timestamp(h.index[-1]).date() for h in histories.values() if len(h)), default=None)
    stocks = {r.ticker: stock_entry(r, histories[r.ticker], currencies.get(r.ticker), regions.get(r.ticker, ""),
                                    atrs.get(r.ticker)) for r in rows if r.ticker in histories}
    for ticker, risk in (earnings_risk or {}).items():
        if ticker in stocks:
            stocks[ticker]["earnings_risk"] = earnings_risk_entry(risk)
    for ticker, items in (news or {}).items():
        if ticker in stocks:
            stocks[ticker]["news_summary"] = next((r.news for r in rows if r.ticker == ticker), None)
            stocks[ticker]["news"] = [{"title": i.title[:200], "source": i.source[:80], "url": i.url[:500],
                                       "published": i.published, "sentiment": i.sentiment, "impact": i.impact,
                                       "reason": i.reason[:160]} for i in items[:MAX_NEWS]]
    return {
        "schema_version": 2,
        "generated_at": now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "market_date": None if market_date is None else str(market_date),
        "benchmark": benchmark,
        "breadth": {str(k): _num(v, 1) for k, v in breadth.items()},
        "research": list(research),
        "candidates": [t for t in candidates if t in stocks],  # tragtens fund i hele universet
        "stocks": stocks,
        "universe": universe_section(factors, scores, regional),
        "screeners": screener_section(factors, scores, regional),
        "paper": paper_section(trades, last_prices),
        "changes": list(changes),
    }
