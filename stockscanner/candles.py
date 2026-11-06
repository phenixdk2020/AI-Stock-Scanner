"""Candle-detektor til timing (Playbook punkt 3) og simpel backtest.

Alle mønstre bruger kun data til og med signaldagen (ingen look-ahead).
Signal ved lukning, køb næste dags åbning. Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


PATTERNS = {
    "inside_bar_breakout": "Inside Bar-udbrud",
    "bullish_engulfing": "Bullish engulfing",
    "hammer": "Hammer",
    "morning_star": "Morning star",
    "close_above_prev_high_volume": "Lukning over forrige top med volumen",
}

DEFAULT_HORIZONS = (5, 10, 20)
DEFAULT_COST_PCT = 0.1  # kurtage pr. handel (køb og salg hver), i procent


def _ohlcv(prices: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in ("Open", "High", "Low", "Close") if c not in prices.columns]
    if missing:
        raise ValueError(f"Mangler kolonner: {', '.join(missing)}")
    frame = prices[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce")
    volume = prices["Volume"] if "Volume" in prices.columns else pd.Series(np.nan, index=prices.index)
    frame["Volume"] = pd.to_numeric(volume, errors="coerce")
    return frame.replace([np.inf, -np.inf], np.nan)


def detect_patterns(prices: pd.DataFrame, breakout_window: int = 5, volume_factor: float = 1.5) -> pd.DataFrame:
    """Én boolsk kolonne pr. mønster; True betyder signal ved dagens lukning.

    Rækker med manglende OHLC giver aldrig signal.
    """
    f = _ohlcv(prices)
    o, h, l, c, v = f["Open"], f["High"], f["Low"], f["Close"], f["Volume"]
    valid = f[["Open", "High", "Low", "Close"]].notna().all(axis=1)
    body = (c - o).abs()
    rng = h - l
    out = pd.DataFrame(index=f.index)

    # Inside bar: dagens range ligger strengt inden for gårsdagens (mother bar).
    inside = (h < h.shift(1)) & (l > l.shift(1)) & valid & valid.shift(1, fill_value=False)
    mother_high = h.shift(1).where(inside)
    # Første lukning over mother bar-toppen inden for breakout_window dage efter inside bar.
    breakout = pd.Series(False, index=f.index)
    hi = mother_high.to_numpy()
    closes = c.to_numpy()
    for i in np.flatnonzero(inside.to_numpy()):
        for j in range(i + 1, min(i + 1 + breakout_window, len(f))):
            if np.isnan(closes[j]):
                break
            if closes[j] > hi[i]:
                breakout.iloc[j] = True
                break
    out["inside_bar_breakout"] = breakout & valid

    prev_red = c.shift(1) < o.shift(1)
    out["bullish_engulfing"] = (
        valid & valid.shift(1, fill_value=False) & prev_red & (c > o)
        & (o <= c.shift(1)) & (c >= o.shift(1)) & (body > body.shift(1))
    )

    lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    out["hammer"] = (
        valid & (rng > 0) & (body > 0) & (lower_wick >= 2 * body)
        & (upper_wick <= 0.3 * rng) & (c >= l + 2 / 3 * rng)
    )

    body2, rng2 = body.shift(2), rng.shift(2)
    red2 = c.shift(2) < o.shift(2)
    mid2 = (o.shift(2) + c.shift(2)) / 2
    out["morning_star"] = (
        valid & valid.shift(1, fill_value=False) & valid.shift(2, fill_value=False)
        & red2 & (rng2 > 0) & (body2 >= 0.5 * rng2)
        & (body.shift(1) <= 0.3 * body2) & (c > o) & (c > mid2)
    )

    avg_volume = v.shift(1).rolling(20, min_periods=20).mean()
    out["close_above_prev_high_volume"] = (
        valid & (c > h.shift(1)) & (avg_volume > 0) & (v >= volume_factor * avg_volume)
    )
    return out.fillna(False).astype(bool)


def trend_context(prices: pd.DataFrame, pullback_days: int = 10, pullback_pct: float = 5.0) -> pd.DataFrame:
    """Optrend og tilbagerekyl målt ved dagens lukning.

    Optrend: lukning over SMA200 og SMA50 over SMA200.
    Tilbagerekyl: inden for de seneste `pullback_days` dage har kursen rørt SMA50
    (low ≤ SMA50) eller ligget mindst `pullback_pct` % under 20-dages toppen.
    """
    f = _ohlcv(prices)
    c, l = f["Close"], f["Low"]
    sma50 = c.rolling(50, min_periods=50).mean()
    sma200 = c.rolling(200, min_periods=200).mean()
    uptrend = (c > sma200) & (sma50 > sma200)
    touched = (l <= sma50).astype(float).rolling(pullback_days, min_periods=1).max() > 0
    drawdown = (c / c.rolling(20, min_periods=20).max() - 1) * 100
    dipped = (drawdown <= -pullback_pct).astype(float).rolling(pullback_days, min_periods=1).max() > 0
    return pd.DataFrame({"uptrend": uptrend, "pullback": touched | dipped}, index=f.index).fillna(False)


def eligible_signals(prices: pd.DataFrame, require_pullback: bool = True) -> pd.DataFrame:
    """Mønstre der kun tæller i optrend (og efter tilbagerekyl, som standard)."""
    patterns = detect_patterns(prices)
    context = trend_context(prices)
    ok = context["uptrend"] & (context["pullback"] if require_pullback else True)
    return patterns.mul(ok, axis=0).astype(bool)


def latest_text(prices: pd.DataFrame, days: int = 5) -> str | None:
    """Mønstre de seneste `days` handelsdage som tekst. Kun oplysning: det ændrer aldrig en købsvurdering."""
    hits = []
    for day, row in eligible_signals(prices).tail(days).iterrows():
        hits += [f"{label} {pd.Timestamp(day).date()}" for name, label in PATTERNS.items() if row[name]]
    return ", ".join(hits[-3:]) or None


def forward_returns(prices: pd.DataFrame, horizons=DEFAULT_HORIZONS, cost_pct: float = DEFAULT_COST_PCT) -> pd.DataFrame:
    """Afkast i % for signal ved lukning dag t: køb åbning t+1, sælg lukning t+h.

    Kurtage trækkes for både køb og salg. NaN når fremtiden mangler.
    """
    f = _ohlcv(prices)
    entry = f["Open"].shift(-1)
    out = pd.DataFrame(index=f.index)
    for horizon in horizons:
        exit_ = f["Close"].shift(-horizon)
        out[f"{horizon}d"] = (exit_ / entry - 1) * 100 - 2 * cost_pct
    return out


def setups(prices: pd.DataFrame, require_pullback: bool = True) -> pd.DataFrame:
    """Handelsopsætninger i stil med Daytrader.dk-guidens Inside Bar.

    Én række pr. opsætning: dagen den kendes (lukning), købsstop-niveau (trigger)
    og stop-loss. Inside bar: trigger = mother bar-top, stop = mother bar-bund.
    Øvrige mønstre: trigger = signaldagens top, stop = laveste bund i mønsteret.
    Kun i optrend (og efter tilbagerekyl, som standard) på opsætningsdagen.
    """
    f = _ohlcv(prices)
    h, l = f["High"], f["Low"]
    valid = f[["Open", "High", "Low", "Close"]].notna().all(axis=1)
    context = trend_context(prices)
    ok = context["uptrend"] & (context["pullback"] if require_pullback else True)
    patterns = detect_patterns(prices)
    inside = (h < h.shift(1)) & (l > l.shift(1)) & valid & valid.shift(1, fill_value=False)
    candidates = {
        "inside_bar_breakout": (inside, h.shift(1), l.shift(1)),
        "bullish_engulfing": (patterns["bullish_engulfing"], h, l.rolling(2).min()),
        "hammer": (patterns["hammer"], h, l),
        "morning_star": (patterns["morning_star"], h, l.rolling(3).min()),
        "close_above_prev_high_volume": (patterns["close_above_prev_high_volume"], h, l),
    }
    rows = []
    for name, (mask, trigger, stop) in candidates.items():
        for position in np.flatnonzero((mask & ok).to_numpy()):
            rows.append((name, position, float(trigger.iloc[position]), float(stop.iloc[position])))
    return pd.DataFrame(rows, columns=["pattern", "position", "trigger", "stop"])


def simulate_trade(prices: pd.DataFrame, position: int, trigger: float, stop: float, hold_days: int,
                   entry_window: int = 5, target_r: float | None = None, cost_pct: float = DEFAULT_COST_PCT):
    """Købsstop over `trigger` de næste `entry_window` dage; stop-loss ved `stop`.

    Konservativ ved dagsdata: rammer entrydagen også stoppet, regnes det som stoppet.
    Gap over trigger giver køb til åbningskursen; gap under stop giver salg til åbningen.
    Ellers salg ved lukning på holdedag nr. `hold_days` (1 = samme dag som købet).
    Returnerer (afkast %, R-multipel, exit-årsag) eller None, hvis købet aldrig udløses.
    """
    if hold_days < 1:
        raise ValueError("hold_days skal være mindst 1.")
    f = _ohlcv(prices)
    o, h, l, c = (f[col].to_numpy() for col in ("Open", "High", "Low", "Close"))
    if not (trigger > stop > 0):
        return None
    n = len(f)
    entry_day = None
    for j in range(position + 1, min(position + 1 + entry_window, n)):
        if np.isnan(o[j]) or np.isnan(h[j]):
            return None
        if l[j] <= stop and h[j] < trigger:
            return None  # opsætningen brudt nedad, før købet blev udløst
        if h[j] >= trigger:
            entry_day = j
            break
    if entry_day is None:
        return None
    entry = max(o[entry_day], trigger)
    last_day = entry_day + hold_days - 1
    if last_day >= n:
        return None  # horisonten rækker ud over data: tæl hverken vindere eller tabere (som baseline)
    risk = entry - stop
    target = entry + target_r * risk if target_r else None
    exit_price, reason = None, "tid"
    for j in range(entry_day, last_day + 1):
        if np.isnan(o[j]) or np.isnan(h[j]) or np.isnan(l[j]):
            return None
        if j > entry_day and o[j] <= stop:
            exit_price, reason = o[j], "stop (gap)"
            break
        if l[j] <= stop:
            exit_price, reason = stop, "stop"
            break
        # Mål først fra dagen efter købet: på dagsdata ved vi ikke, om toppen kom før købet.
        if target is not None and j > entry_day and h[j] >= target:
            exit_price, reason = max(o[j], target), "mål"
            break
    if exit_price is None:
        exit_price = c[last_day]
    if np.isnan(exit_price):
        return None
    pct = (exit_price / entry - 1) * 100 - 2 * cost_pct
    r_multiple = (exit_price - entry) / risk - 2 * cost_pct / 100 * entry / risk
    return pct, r_multiple, reason


@dataclass(frozen=True)
class TradeRow:
    pattern: str
    hold_days: int
    trades: int
    mean_pct: float | None
    hit_rate_pct: float | None
    mean_r: float | None
    stopped_pct: float | None
    baseline_pct: float | None
    edge_pct: float | None


def trade_backtest(histories: dict[str, pd.DataFrame], hold_days=(1, 5, 10, 20), entry_window: int = 5,
                   target_r: float | None = None, cost_pct: float = DEFAULT_COST_PCT,
                   require_pullback: bool = True) -> list[TradeRow]:
    """Guidens handelsregler på dagsdata, sammenlignet med køb på åbning en tilfældig dag.

    Baseline: køb ved åbning og salg ved lukning efter samme antal holdedage, alle dage.
    Overlappende handler tælles hver for sig.
    """
    results = {(name, days): [] for name in PATTERNS for days in hold_days}
    baseline = {days: [] for days in hold_days}
    for frame in histories.values():
        f = _ohlcv(frame)
        for days in hold_days:
            base = (f["Close"].shift(-(days - 1)) / f["Open"] - 1) * 100 - 2 * cost_pct
            baseline[days].append(base.dropna())
        for row in setups(frame, require_pullback=require_pullback).itertuples(index=False):
            for days in hold_days:
                trade = simulate_trade(frame, row.position, row.trigger, row.stop, days,
                                       entry_window, target_r, cost_pct)
                if trade is not None:
                    results[(row.pattern, days)].append(trade)
    rows = []
    for days in hold_days:
        base_values = pd.concat(baseline[days]) if baseline[days] else pd.Series(dtype=float)
        base_mean = float(base_values.mean()) if len(base_values) else None
        for name in PATTERNS:
            trades = results[(name, days)]
            if not trades:
                rows.append(TradeRow(name, days, 0, None, None, None, None, base_mean, None))
                continue
            pct = np.array([t[0] for t in trades])
            r = np.array([t[1] for t in trades])
            stopped = np.mean([t[2].startswith("stop") for t in trades]) * 100
            mean = float(pct.mean())
            rows.append(TradeRow(name, days, len(trades), mean, float((pct > 0).mean() * 100), float(r.mean()),
                                 float(stopped), base_mean, None if base_mean is None else mean - base_mean))
    return rows


@dataclass(frozen=True)
class BacktestRow:
    pattern: str
    horizon: str
    signals: int
    mean_pct: float | None
    median_pct: float | None
    hit_rate_pct: float | None
    baseline_mean_pct: float | None
    edge_pct: float | None
    context_baseline_pct: float | None = None
    context_edge_pct: float | None = None


def backtest(histories: dict[str, pd.DataFrame], horizons=DEFAULT_HORIZONS,
             cost_pct: float = DEFAULT_COST_PCT, require_pullback: bool = True) -> list[BacktestRow]:
    """Sammenlign mønstrenes afkast med en tilfældig dag.

    Baseline = gennemsnit over ALLE dage med kendt fremtid for de samme aktier og
    samme købs-/salgsregel (svarer til forventningen ved en tilfældigt valgt dag).
    Kontekst-baseline = kun dage i samme optrend/tilbagerekyl; viser om fordelen
    kommer fra mønsteret eller blot fra konteksten.
    """
    signal_parts, return_parts, context_parts = [], [], []
    for ticker, frame in histories.items():
        signals = eligible_signals(frame, require_pullback=require_pullback)
        returns = forward_returns(frame, horizons, cost_pct)
        context = trend_context(frame)
        ok = context["uptrend"] & (context["pullback"] if require_pullback else True)
        index = pd.MultiIndex.from_product([[ticker], frame.index])
        signal_parts.append(signals.set_axis(index))
        return_parts.append(returns.set_axis(index))
        context_parts.append(ok.set_axis(index))
    if not signal_parts:
        return []
    signals = pd.concat(signal_parts)
    returns = pd.concat(return_parts)
    in_context = pd.concat(context_parts).astype(bool)

    def stats(values: pd.Series):
        values = values.dropna()
        if values.empty:
            return 0, None, None, None
        return len(values), float(values.mean()), float(values.median()), float((values > 0).mean() * 100)

    rows = []
    for horizon in returns.columns:
        baseline = stats(returns[horizon])[1]
        context_baseline = stats(returns.loc[in_context, horizon])[1]
        for pattern in PATTERNS:
            count, mean, median, hit = stats(returns.loc[signals[pattern], horizon])
            edge = None if mean is None or baseline is None else mean - baseline
            context_edge = None if mean is None or context_baseline is None else mean - context_baseline
            rows.append(BacktestRow(pattern, horizon, count, mean, median, hit, baseline, edge,
                                    context_baseline, context_edge))
    return rows
