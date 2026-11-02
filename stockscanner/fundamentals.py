"""Hentning og normalisering af regnskabstal (årsregnskaber) fra yfinance.

Datakilden er uofficiel (Yahoo Finance via yfinance) og kan være ufuldstændig.
Manglende felter forbliver None og rapporteres i `missing`; der opfindes aldrig værdier.
Tallene er til screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
import re
from typing import Any, Callable

import pandas as pd


SOURCE = "yfinance (uofficiel)"

# Standardfelter pr. regnskabsår.
FIELDS = [
    "revenue", "gross_profit", "operating_income", "ebit", "ebitda", "net_income",
    "interest_expense", "pretax_income", "tax_provision",
    "total_assets", "current_assets", "current_liabilities", "total_liabilities",
    "stockholders_equity", "total_debt", "long_term_debt", "cash", "retained_earnings", "shares",
    "operating_cash_flow", "capital_expenditure", "free_cash_flow",
]

# Mappingtabel: standardfelt -> (regnskab, rækkelabels i prioriteret rækkefølge).
# yfinance-labels varierer mellem versioner og selskaber, så der er flere kandidater.
LABELS: dict[str, tuple[str, list[str]]] = {
    "revenue": ("income", ["Total Revenue", "Operating Revenue", "Revenue"]),
    "gross_profit": ("income", ["Gross Profit"]),
    "operating_income": ("income", ["Operating Income", "Total Operating Income As Reported"]),
    "ebit": ("income", ["EBIT"]),
    "ebitda": ("income", ["EBITDA", "Normalized EBITDA"]),
    "net_income": ("income", [
        "Net Income", "Net Income Common Stockholders",
        "Net Income From Continuing Operation Net Minority Interest",
    ]),
    "interest_expense": ("income", ["Interest Expense", "Interest Expense Non Operating"]),
    "pretax_income": ("income", ["Pretax Income", "Income Before Tax"]),
    "tax_provision": ("income", ["Tax Provision", "Income Tax Expense"]),
    "total_assets": ("balance", ["Total Assets"]),
    "current_assets": ("balance", ["Current Assets", "Total Current Assets"]),
    "current_liabilities": ("balance", ["Current Liabilities", "Total Current Liabilities"]),
    "total_liabilities": ("balance", [
        "Total Liabilities Net Minority Interest", "Total Liabilities",
    ]),
    "stockholders_equity": ("balance", [
        "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest",
    ]),
    "total_debt": ("balance", ["Total Debt"]),
    "long_term_debt": ("balance", ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]),
    "cash": ("balance", [
        "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments",
        "Cash Financial", "Cash And Short Term Investments",
    ]),
    "retained_earnings": ("balance", ["Retained Earnings"]),
    "shares": ("balance", ["Ordinary Shares Number", "Share Issued"]),
    "operating_cash_flow": ("cashflow", [
        "Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
        "Total Cash From Operating Activities",
    ]),
    "capital_expenditure": ("cashflow", ["Capital Expenditure", "Purchase Of PPE"]),
    "free_cash_flow": ("cashflow", ["Free Cash Flow"]),
}


@dataclass
class FiscalYear:
    """Ét regnskabsår med normaliserede felter (None = mangler)."""
    end_date: str
    values: dict[str, float | None]
    # Hvilken yfinance-label aktieantallet kom fra; kun år med samme label sammenlignes.
    share_label: str | None = None


@dataclass
class FundamentalData:
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    currency: str = ""              # kursvaluta (info.currency)
    reporting_currency: str = ""    # regnskabsvaluta (info.financialCurrency)
    market_cap: float | None = None
    shares_outstanding: float | None = None
    years: list[FiscalYear] = field(default_factory=list)   # nyeste først
    missing: list[str] = field(default_factory=list)        # felter der mangler i nyeste år
    fetched_at_utc: str = ""
    source: str = SOURCE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FundamentalData":
        data = dict(payload)
        data["years"] = [FiscalYear(**year) for year in data.get("years", [])]
        return cls(**data)


def _norm(label: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(label).lower())


def _number(value: Any) -> float | None:
    """Konvertér til endeligt tal; NaN/inf/tekst bliver None."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _lookup_label(frame: pd.DataFrame | None, labels: list[str], column: Any) -> tuple[float | None, str | None]:
    """Første label (case- og mellemrumsufølsom) med en værdi i kolonnen: (værdi, label)."""
    if frame is None or frame.empty:
        return None, None
    index: dict[str, Any] = {}
    for name in frame.index:
        index.setdefault(_norm(name), name)
    for label in labels:
        row = index.get(_norm(label))
        if row is None:
            continue
        cell = frame.at[row, column]
        if isinstance(cell, pd.Series):
            continue
        value = _number(cell)
        if value is not None:
            return value, label
    return None, None


def _lookup(frame: pd.DataFrame | None, labels: list[str], column: Any) -> float | None:
    return _lookup_label(frame, labels, column)[0]


def _date_key(column: Any) -> str:
    try:
        return pd.Timestamp(column).strftime("%Y-%m-%d")
    except Exception:
        return str(column)


def normalize_statements(
    income: pd.DataFrame | None,
    balance: pd.DataFrame | None,
    cashflow: pd.DataFrame | None,
) -> list[FiscalYear]:
    """Slå de tre regnskaber sammen til regnskabsår (nyeste først) med standardfelter."""
    frames = {"income": income, "balance": balance, "cashflow": cashflow}
    dates: dict[str, dict[str, Any]] = {}
    for name, frame in frames.items():
        if frame is None or frame.empty:
            continue
        for column in frame.columns:
            dates.setdefault(_date_key(column), {})[name] = column

    years: list[FiscalYear] = []
    for end_date in sorted(dates, reverse=True):
        columns = dates[end_date]
        values: dict[str, float | None] = {}
        share_label: str | None = None
        for key, (source, labels) in LABELS.items():
            column = columns.get(source)
            if column is None:
                values[key] = None
                continue
            value, used = _lookup_label(frames[source], labels, column)
            values[key] = value
            if key == "shares":
                share_label = used
        # Investeringer gemmes som negativt udgående cashflow (yfinance-konvention).
        capex = values["capital_expenditure"]
        if capex is not None and capex > 0:
            values["capital_expenditure"] = -capex
        # Afledte felter – kun når alle input findes.
        if values["free_cash_flow"] is None:
            ocf, capex = values["operating_cash_flow"], values["capital_expenditure"]
            if ocf is not None and capex is not None:
                values["free_cash_flow"] = ocf + capex
        if values["ebit"] is None:
            pretax, interest = values["pretax_income"], values["interest_expense"]
            if pretax is not None and interest is not None:
                values["ebit"] = pretax + abs(interest)
        if values["gross_profit"] is None and "income" in columns:
            cost = _lookup(income, ["Cost Of Revenue", "Reconciled Cost Of Revenue"], columns["income"])
            if values["revenue"] is not None and cost is not None:
                values["gross_profit"] = values["revenue"] - cost
        years.append(FiscalYear(end_date=end_date, values=values, share_label=share_label))

    # Fjern år helt uden data (fx tom kolonne).
    return [year for year in years if any(v is not None for v in year.values.values())]


def _default_fetcher(ticker: str) -> dict[str, Any]:
    """Standardhenter via yfinance. Importeres sent, så tests aldrig rammer netværket."""
    import yfinance as yf

    handle = yf.Ticker(ticker)
    info: dict[str, Any] = {}
    try:
        info = dict(handle.info or {})
    except Exception:
        info = {}
    return {
        "income_stmt": handle.income_stmt,
        "balance_sheet": handle.balance_sheet,
        "cashflow": handle.cashflow,
        "info": info,
    }


def fetch_fundamentals(
    ticker: str,
    fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> FundamentalData:
    """Hent og normalisér årsregnskaber. `fetcher(ticker)` skal returnere en dict med
    nøglerne income_stmt, balance_sheet, cashflow (DataFrames, kolonner = regnskabsdatoer)
    og info (dict). Rejser ValueError hvis der slet ingen regnskabsdata findes."""
    raw = (fetcher or _default_fetcher)(ticker)
    info = raw.get("info") or {}
    years = normalize_statements(raw.get("income_stmt"), raw.get("balance_sheet"), raw.get("cashflow"))
    if not years:
        raise ValueError(f"{ticker}: ingen regnskabsdata fra udbyderen.")
    missing = [name for name in FIELDS if years[0].values.get(name) is None]
    return FundamentalData(
        ticker=ticker,
        name=str(info.get("shortName") or info.get("longName") or ""),
        sector=str(info.get("sector") or ""),
        industry=str(info.get("industry") or ""),
        currency=str(info.get("currency") or ""),
        reporting_currency=str(info.get("financialCurrency") or ""),
        market_cap=_number(info.get("marketCap")),
        shares_outstanding=_number(info.get("sharesOutstanding")),
        years=years,
        missing=missing,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=SOURCE,
    )
