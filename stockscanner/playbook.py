"""Playbook-snapshot (schema 2) til aktier.hangar18.dk – se docs/PLAYBOOK-SNAPSHOT.md.

Bygges af mandagslisten og sendes med site_sync.send_playbook, så hjemmesiden altid viser seneste kørsel.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd

from stockscanner.exits import exit_signals, supertrend
from stockscanner.sector_rs import sector_name
from stockscanner.universe import liquidity_class, size_class
from stockscanner.valuation import DEFAULT_HORIZON


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


def stock_entry(row, prices: pd.DataFrame, currency: str | None, region: str, atr_value,
                sector: str | None = None) -> dict:
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
        "sector": sector or "ukendt",
        "exit": exit_facts(prices, "StockMap-salg denne uge" in row.reasons),
    }


SCENARIO_NAMES = ("bear", "base", "bull")
MAX_SCENARIO_NOTES = 6


def scenarios_entry(channel, currency: str | None, horizon: float) -> dict | None:
    """Automatisk Bear/Base/Bull (valuation.ValueChannel) til payloaden; None uden beregnede scenariepriser.
    Regnestykket er EPS ved horisonten × P/E (historiske P/E og analytikernes estimater), ikke en prognose.
    Manglende, NaN og uendelige tal bliver til None; uendelig asymmetri markeres med `asymmetry_inf`."""
    if channel is None:
        return None
    prices = {k: _num((channel.scenario_prices or {}).get(k), 4) for k in SCENARIO_NAMES}
    if all(v is None for v in prices.values()):
        return None
    from stockscanner.weekly_list import asymmetry_of

    asymmetry = asymmetry_of(channel)
    infinite = asymmetry is not None and math.isinf(asymmetry)
    pe = {"bear": channel.pe_bear, "base": channel.pe_base, "bull": channel.pe_bull}
    return {
        "currency": currency, "horizon_years": _num(horizon, 1), "price": _num(channel.price, 4),
        "eps_today": _num(channel.eps_today, 4), "eps_horizon": _num(channel.eps_horizon, 4),
        "pe": {k: _num(v, 2) for k, v in pe.items()},
        "prices": prices,
        "upside_pct": {k: _num((channel.upside_pct or {}).get(k), 1) for k in SCENARIO_NAMES},
        "cagr_pct": {k: _num((channel.cagr_pct or {}).get(k), 1) for k in SCENARIO_NAMES},
        "asymmetry": None if infinite else _num(asymmetry, 2), "asymmetry_inf": infinite,
        "peg": _num(channel.peg, 2), "channel_score": _num(channel.score_today, 1),
        "notes": [str(n)[:160] for n in list(channel.notes or ())[:MAX_SCENARIO_NOTES]],
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
                    "size", "liquidity", "sector"]


def universe_section(factors: pd.DataFrame | None, scores: pd.DataFrame | None,
                     regional: pd.DataFrame | None, sector_map: dict | None = None) -> dict:
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
                     size_class(cap), liquidity_class(f.get("x_adv_usd"), f.get("x_idle_days")),
                     sector_name(ticker, factors, sector_map)])
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


def paper_score_section(score: dict | None) -> dict | None:
    """Papirporteføljens stilling mod RSP (paper.score) til payloaden; None uden beregning. Tal rundes, NaN bliver None."""
    if not score:
        return None
    counts = ("antal", "sammenlignet", "udeladt", "dage")
    out = {k: (None if score.get(k) is None else int(score[k])) for k in counts}
    for key in ("afkast_pct", "rsp_pct", "forskel_pp", "vinderandel_pct", "slaar_rsp_pct"):
        out[key] = _num(score.get(key), 2)
    out["start"] = score.get("start")
    out["for_tidligt"] = bool(score.get("for_tidligt", True))
    return out


def build_payload(*, rows, histories, currencies, regions, atrs, research, breadth, benchmark,
                  factors, scores, regional, trades, last_prices, changes, news=None, candidates=(),
                  earnings_risk=None, channels=None, horizon: float = DEFAULT_HORIZON,
                  universe_scenarios=None, sector_map: dict | None = None, paper_score: dict | None = None,
                  now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    market_date = max((pd.Timestamp(h.index[-1]).date() for h in histories.values() if len(h)), default=None)
    stocks = {r.ticker: stock_entry(r, histories[r.ticker], currencies.get(r.ticker), regions.get(r.ticker, ""),
                                    atrs.get(r.ticker), sector_name(r.ticker, factors, sector_map))
              for r in rows if r.ticker in histories}
    for ticker, risk in (earnings_risk or {}).items():
        if ticker in stocks:
            stocks[ticker]["earnings_risk"] = earnings_risk_entry(risk)
    for ticker, channel in (channels or {}).items():
        scenarios = scenarios_entry(channel, currencies.get(ticker), horizon) if ticker in stocks else None
        if scenarios is not None:
            stocks[ticker]["scenarios"] = scenarios     # aktier uden kanal får intet felt
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
        "universe": universe_section(factors, scores, regional, sector_map),
        # Bear/Base/Bull for universets aktier uden fuld analyse; mandagslistens egne ligger i stocks
        "scenarios": {t: s for t, s in (universe_scenarios or {}).items() if t not in stocks},
        "screeners": screener_section(factors, scores, regional),
        "paper": paper_section(trades, last_prices),
        "paper_score": paper_score_section(paper_score),
        "changes": list(changes),
    }
