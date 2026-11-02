"""Værdikanal og værdiansættelsesscore (fase 3) – egen, åben udgave inspireret af MSS' valuegraf.

Kurs = EPS × P/E. Kanalen er analytikernes EPS-sti × tre P/E-niveauer:
  base = historisk gennemsnitlig P/E (median af tilgængelige perioder),
  bear = base × (1 − band), bull = base × (1 + band), band = 20 % som standard
(MSS' eksempler: Vestas 18/23/28, CoreCivic 16/20/24, Micron 14/18/23, GN 16–24, Pandora 14–21).
Score: 100 på bear-linjen, 0 på bull-linjen, lineært og ikke afkortet (MSS: over 100 = meget billig,
negativ = meget dyr). Analytikertal er dagens tal (ingen historik), så scoren kan kun sammenlignes
fremad i tid. Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

DEFAULT_BAND = 0.20
DEFAULT_HORIZON = 2.0         # år frem, som MSS' standard
EPS_REPORT_LAG_DAYS = 60      # regnskab kendes først ca. to måneder efter regnskabsårets slutning
MAX_EXTRAPOLATED_GROWTH = 0.5


@dataclass(frozen=True)
class ValuationInputs:
    ticker: str
    price: float                          # i handelsvaluta
    as_of: date
    last_fiscal_year_end: date
    eps_last: float                       # seneste rapporterede årlige EPS (i handelsvaluta)
    eps_current_year: float | None        # konsensus for indeværende regnskabsår ("0y")
    eps_next_year: float | None           # konsensus for næste regnskabsår ("+1y")
    pe_history: pd.Series = field(default_factory=pd.Series)  # daglig trailing P/E (kun positive EPS)
    target_price: float | None = None     # analytikernes gennemsnitlige kursmål
    currency: str = ""


@dataclass(frozen=True)
class ValueChannel:
    ticker: str
    pe_base: float | None
    pe_bear: float | None
    pe_bull: float | None
    eps_today: float | None
    eps_horizon: float | None
    price: float
    scenario_prices: dict[str, float]
    upside_pct: dict[str, float]
    cagr_pct: dict[str, float]
    score: float | None                   # linjer ved horisonten (variant A)
    score_today: float | None             # linjer i dag (variant B)
    asymmetry: float | None               # base-upside / |bear-nedside|; MSS-praksis: mindst 2–4
    peg: float | None
    implied_pe: float | None
    notes: tuple[str, ...] = ()


def eps_path(inputs: ValuationInputs, years_after_fye: float) -> float | None:
    """EPS på et tidspunkt målt i år efter seneste regnskabsårs slutning.

    Knudepunkter: 0 = seneste rapporterede EPS, 1 = indeværende års konsensus, 2 = næste års konsensus.
    Lineært imellem; efter 2 år fremskrives med væksten fra år 1 til 2 (begrænset til ±50 %).
    """
    knots = [inputs.eps_last, inputs.eps_current_year, inputs.eps_next_year]
    if any(k is None or not np.isfinite(k) for k in knots):
        return None
    t = max(0.0, years_after_fye)
    if t <= 2:
        return float(np.interp(t, [0, 1, 2], knots))
    growth = 0.0 if knots[1] <= 0 else knots[2] / knots[1] - 1
    growth = float(np.clip(growth, -MAX_EXTRAPOLATED_GROWTH, MAX_EXTRAPOLATED_GROWTH))
    return knots[2] * (1 + growth) ** (t - 2)


def base_pe(pe_history: pd.Series, as_of: date, min_pe: float = 3.0, max_pe: float = 60.0) -> float | None:
    """Median af gennemsnitlig P/E over 3, 5 og 10 år (de perioder, der er data til).

    Hvert år tæller med sin median-P/E; år uden for [min_pe, max_pe] udelades, fordi en næsten
    forsvundet indtjening giver meningsløse P/E-tal (fx Vestas 2024 ≈ 270, GN 2024 ≈ 97).
    """
    series = pe_history.dropna()
    series = series[(series > 0) & np.isfinite(series) & (series.index <= pd.Timestamp(as_of))]
    if series.empty:
        return None
    yearly = series.groupby(series.index.year).median()
    yearly = yearly[(yearly >= min_pe) & (yearly <= max_pe)]
    if yearly.empty:
        return None
    first_year = int(series.index.year.min())
    averages = []
    for years in (3, 5, 10):
        window = yearly[yearly.index > as_of.year - years]
        if not window.empty and (years == 3 or first_year <= as_of.year - years + 1):
            averages.append(float(window.mean()))
    return float(np.median(averages)) if averages else float(yearly.mean())


def pe_candidates(pe_history: pd.Series, as_of: date, current_pe: float | None,
                  windows=(1, 3, 5, 10, 20), max_pe: float = 500.0) -> list[float]:
    """Median af daglig P/E over 1, 3, 5, 10 og 20 år (de perioder, der er data til) plus nuværende P/E.

    MSS ("Nye features i valuegrafen" 0:02:45): bear = laveste, bull = højeste af disse, base =
    midtpunktet. Varianten er valgt mod 113 høstede amerikanske MSS-kanaler (02-11-2026, SEC-historik):
    rangkorrelation 0,70 for bear/bull-forholdet (årsgennemsnit med P/E 3–60: 0,37).
    """
    series = pe_history.dropna()
    end = pd.Timestamp(as_of)
    series = series[(series > 0) & (series < max_pe) & np.isfinite(series) & (series.index <= end)]
    candidates = []
    if not series.empty:
        for years in windows:
            window = series[series.index > end - pd.DateOffset(years=years)]
            covered = series.index.min() <= end - pd.DateOffset(years=years - 1)
            if len(window) >= 20 and (years == windows[0] or covered):
                candidates.append(float(window.median()))
    if current_pe is not None and 0 < current_pe < max_pe:
        candidates.append(float(current_pe))
    return candidates


def value_channel(inputs: ValuationInputs, horizon: float = DEFAULT_HORIZON, band: float = DEFAULT_BAND,
                  pe_override: tuple[float, float, float] | None = None, band_rule: str = "minmax") -> ValueChannel:
    """Beregn kanalen; `pe_override` = (bear, base, bull) som når brugeren selv trækker kanalen.

    `band_rule`: "minmax" (MSS-reglen: laveste/højeste af historiske gennemsnit og nuværende P/E,
    base = midtpunkt; falder tilbage til "fixed" med færre end to kandidater) eller "fixed"
    (base = historisk gennemsnit, bear/bull = base ∓ `band`).
    """
    notes = []
    years_now = (inputs.as_of - inputs.last_fiscal_year_end).days / 365.25
    eps_today = eps_path(inputs, years_now)
    eps_h = eps_path(inputs, years_now + horizon)
    if pe_override:
        pe_bear, pe_base, pe_bull = pe_override
    else:
        current_pe = inputs.price / inputs.eps_last if inputs.eps_last and inputs.eps_last > 0 else None
        candidates = pe_candidates(inputs.pe_history, inputs.as_of, current_pe) if band_rule == "minmax" else []
        if len(candidates) >= 2 and max(candidates) > min(candidates):
            pe_bear, pe_bull = min(candidates), max(candidates)
            pe_base = (pe_bear + pe_bull) / 2
        else:
            pe_base = base_pe(inputs.pe_history, inputs.as_of)
            pe_bear = None if pe_base is None else pe_base * (1 - band)
            pe_bull = None if pe_base is None else pe_base * (1 + band)
        if pe_base is not None and len(inputs.pe_history.dropna()) < 750:
            notes.append("Under 3 års P/E-historik")
    empty = ValueChannel(inputs.ticker, pe_base, pe_bear, pe_bull, eps_today, eps_h, inputs.price, {}, {}, {},
                         None, None, None, None, None, tuple(notes))
    if _inconsistent_eps(inputs):
        return ValueChannel(**{**empty.__dict__, "notes": tuple(notes + ["EPS-estimater passer ikke med seneste regnskab (datafejl?)"])})
    if pe_base is None:
        return _with_extras(empty, inputs, notes + ["Ingen positiv P/E-historik"])
    if eps_h is None or eps_h <= 0:
        return _with_extras(empty, inputs, notes + ["Mangler positive EPS-estimater"])

    pes = {"bear": pe_bear, "base": pe_base, "bull": pe_bull}
    prices = {k: eps_h * pe for k, pe in pes.items()}
    upside = {k: (v / inputs.price - 1) * 100 for k, v in prices.items()}
    cagr = {k: ((v / inputs.price) ** (1 / horizon) - 1) * 100 for k, v in prices.items()}
    score = 100 * (prices["bull"] - inputs.price) / (prices["bull"] - prices["bear"])
    score_today = None
    if eps_today and eps_today > 0:
        bull_now, bear_now = eps_today * pe_bull, eps_today * pe_bear
        score_today = 100 * (bull_now - inputs.price) / (bull_now - bear_now)
    asymmetry = upside["base"] / -upside["bear"] if upside["bear"] < 0 else None
    channel = ValueChannel(inputs.ticker, pe_base, pe_bear, pe_bull, eps_today, eps_h, inputs.price, prices,
                           upside, cagr, score, score_today, asymmetry, None, None, tuple(notes))
    return _with_extras(channel, inputs, notes)


def _inconsistent_eps(inputs: ValuationInputs, max_ratio: float = 3.0) -> bool:
    """Indeværende års estimat mere end 3 gange fra seneste regnskab tyder på enheds- eller valutafejl
    (set hos yfinance for fx innoscripta og SOBI)."""
    last, current = inputs.eps_last, inputs.eps_current_year
    if not last or not current or last <= 0 or current <= 0:
        return False
    return not (1 / max_ratio <= current / last <= max_ratio)


def _with_extras(channel: ValueChannel, inputs: ValuationInputs, notes) -> ValueChannel:
    """Tilføj PEG (forward P/E / næste års EPS-vækst i %) og implicit P/E (kursmål / næste års EPS)."""
    peg, implied = None, None
    if inputs.eps_current_year and inputs.eps_next_year and inputs.eps_current_year > 0 and inputs.eps_next_year > 0:
        growth = (inputs.eps_next_year / inputs.eps_current_year - 1) * 100
        if growth > 0:
            peg = (inputs.price / inputs.eps_next_year) / growth
        if inputs.target_price:
            implied = inputs.target_price / inputs.eps_next_year
    return ValueChannel(**{**channel.__dict__, "peg": peg, "implied_pe": implied, "notes": tuple(notes)})


def trailing_pe_history(prices: pd.Series, annual_eps: pd.Series, lag_days: int = EPS_REPORT_LAG_DAYS) -> pd.Series:
    """Daglig P/E = kurs / seneste kendte årlige EPS (kendt `lag_days` efter regnskabsårets slutning)."""
    if prices.empty or annual_eps.dropna().empty:
        return pd.Series(dtype=float)
    known = annual_eps.dropna().copy()
    known.index = pd.DatetimeIndex(known.index) + pd.Timedelta(days=lag_days)
    known = known.sort_index()
    eps_daily = known.reindex(prices.index.union(known.index)).ffill().reindex(prices.index)
    pe = prices / eps_daily
    return pe[(eps_daily > 0)].dropna()


def fetch_inputs(symbol: str, as_of: date | None = None, use_sec: bool = True) -> ValuationInputs:
    """Hent data fra yfinance (uofficiel). EPS omregnes til handelsvaluta ved forskellig regnskabsvaluta.

    For amerikanske aktier (`use_sec`) forlænges EPS-historikken med SEC EDGAR, så P/E-gennemsnit
    over 10–20 år kan beregnes (yfinance har ca. 4 års regnskaber).
    """
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    currency = str(info.get("currency") or "")
    fin_currency = str(info.get("financialCurrency") or currency)
    is_us = use_sec and "." not in symbol and currency == "USD" and fin_currency == "USD"
    history = ticker.history(period="21y" if is_us else "11y", interval="1d", auto_adjust=False, actions=False)
    if history is None or history.empty:
        raise ValueError(f"{symbol}: ingen kursdata.")
    close = pd.to_numeric(history["Close"], errors="coerce")
    close.index = _naive(close.index)
    scale = 0.01 if currency in ("GBp", "ILA", "ZAc") else 1.0  # kurser i pence/agorot/cent
    fx = _fx_series(fin_currency, currency, close.index) if fin_currency and currency and fin_currency.upper() != currency.upper() else None

    statement = ticker.income_stmt
    row = next((r for r in ("Diluted EPS", "Basic EPS") if r in statement.index), None)
    if row is None:
        raise ValueError(f"{symbol}: ingen årlig EPS.")
    annual = pd.to_numeric(statement.loc[row], errors="coerce").dropna()
    annual.index = _naive(annual.index)
    annual = annual.sort_index()
    if fx is not None:
        annual = annual * fx.reindex(annual.index, method="ffill").bfill().values
    if is_us:
        annual = _extend_with_sec(symbol, annual, ticker.splits)
    estimates = ticker.earnings_estimate
    fx_now = 1.0 if fx is None else float(fx.iloc[-1])
    eps0 = _estimate(estimates, "0y")
    eps1 = _estimate(estimates, "+1y")
    targets = ticker.analyst_price_targets or {}
    target = _float(targets.get("mean"))
    price = float(close.iloc[-1]) * scale
    pe_hist = trailing_pe_history(close * scale, annual)
    return ValuationInputs(
        ticker=symbol, price=price, as_of=as_of or close.index[-1].date(),
        last_fiscal_year_end=annual.index[-1].date(), eps_last=float(annual.iloc[-1]),
        eps_current_year=None if eps0 is None else eps0 * fx_now,
        eps_next_year=None if eps1 is None else eps1 * fx_now,
        pe_history=pe_hist, target_price=None if target is None else target * scale, currency=currency,
    )


def _extend_with_sec(symbol: str, annual: pd.Series, splits: pd.Series) -> pd.Series:
    """Tilføj ældre årlig EPS fra SEC EDGAR (splitjusteret) før yfinance' første regnskabsår."""
    from stockscanner.sec_edgar import annual_eps, split_adjust

    try:
        sec = annual_eps(symbol)
    except Exception:
        return annual
    if sec.empty:
        return annual
    sec = split_adjust(sec, splits if splits is not None else pd.Series(dtype=float))
    older = sec[sec.index < annual.index.min() - pd.Timedelta(days=200)]
    return pd.concat([older, annual]).sort_index()


def _estimate(frame, period: str) -> float | None:
    try:
        return _float(frame.loc[period, "avg"])
    except Exception:
        return None


def _float(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _naive(index) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(index))
    return (dates.tz_localize(None) if dates.tz is not None else dates).normalize()


def _fx_series(source: str, target: str, index: pd.DatetimeIndex) -> pd.Series:
    """Kurs for 1 `source` i `target`, dagligt (yfinance-symbol fx 'EURDKK=X')."""
    import yfinance as yf

    pair = yf.Ticker(f"{source.upper()}{target.upper()}=X").history(period="11y", interval="1d")
    if pair is None or pair.empty:
        raise ValueError(f"Ingen valutakurs {source}/{target}.")
    rate = pd.to_numeric(pair["Close"], errors="coerce")
    rate.index = _naive(rate.index)
    return rate.reindex(index.union(rate.index)).ffill().bfill().reindex(index)
