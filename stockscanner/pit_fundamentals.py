"""Point-in-time fundamentaldata fra SEC companyfacts (B-17).

Hvert tal i companyfacts har en `filed`-dato (dagen regnskabet blev indleveret). `as_of(facts, dato)` bruger KUN
tal med `filed <= dato`, og for hver regnskabsperiode den senest indleverede version før datoen. Et omarbejdet tal
tæller derfor først fra sin egen `filed`-dato; tal indleveret efter datoen ses aldrig.

Nøgletal (så vidt tallene findes): TTM-EPS, ROE, ROA, bruttomargin, gæld/egenkapital, rentedækning, omsætningsvækst.
TTM = seneste regnskabsår + seneste år-til-dato − samme år-til-dato året før (alle kendt på datoen).
Kun US-GAAP-selskaber (10-K/10-Q); udenlandske 20-F/IFRS-selskaber får ingen tal.
Svagheder: tag-valg er forenklet (ét tag pr. begreb, det med den nyeste periode); EPS er ikke splitjusteret
(det gør studiet pr. dato ud fra kursleverandørens splits); ROIC beregnes ikke.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A", "10-K405", "10-Q", "10-Q/A", "10-QT")
MAX_STALE_DAYS = 550   # en periode, der sluttede for mere end ca. 18 måneder siden, tæller ikke som aktuel

FLOW = {  # begreb -> us-gaap-tags i prioriteret rækkefølge
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"),
    "net_income": ("NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    "gross_profit": ("GrossProfit",),
    "op_income": ("OperatingIncomeLoss",),
    "interest": ("InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt", "InterestAndDebtExpense"),
    "eps": ("EarningsPerShareDiluted", "EarningsPerShareBasic"),
}
INSTANT = {
    "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "assets": ("Assets",),
    "debt_lt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "debt_st": ("LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"),
}
_ALL_TAGS = {tag for tags in (*FLOW.values(), *INSTANT.values()) for tag in tags}
METRICS = ("eps_ttm", "roe", "roa", "gross_margin", "debt_equity", "interest_coverage", "revenue_growth")


def facts_table(facts: dict) -> pd.DataFrame:
    """Companyfacts-dokument -> tabel (tag, start, end, val, filed), sorteret efter `filed`."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    rows = []
    for tag in _ALL_TAGS:
        for entries in gaap.get(tag, {}).get("units", {}).values():
            for e in entries:
                if e.get("form") not in FORMS or not e.get("filed") or not e.get("end") or e.get("val") is None:
                    continue
                rows.append((tag, e.get("start"), e["end"], float(e["val"]), e["filed"]))
    table = pd.DataFrame(rows, columns=["tag", "start", "end", "val", "filed"])
    for col in ("start", "end", "filed"):
        table[col] = pd.to_datetime(table[col])
    return table.sort_values("filed", kind="stable").reset_index(drop=True)


def _known(table: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    """Kun rækker med filed <= dato; pr. (tag, start, end) den senest indleverede version."""
    known = table[table["filed"] <= date]
    return known.drop_duplicates(["tag", "start", "end"], keep="last")


def _near(a: pd.Timestamp, b: pd.Timestamp, days: int) -> bool:
    return abs((a - b).days) <= days


def _ttm(rows: pd.DataFrame, date: pd.Timestamp):
    """TTM-sum for ét tag ud fra kendte rækker; None hvis der ikke er et friskt regnskabsår."""
    flows = rows[rows["start"].notna()].copy()
    if flows.empty:
        return None
    days = (flows["end"] - flows["start"]).dt.days
    annual = flows[(days >= 330) & (days <= 400)]
    if annual.empty:
        return None
    fy = annual.loc[annual["end"].idxmax()]
    if (date - fy["end"]).days > MAX_STALE_DAYS:
        return None
    total = float(fy["val"])
    later = flows[(flows["end"] > fy["end"]) & ((flows["end"] - flows["start"]).dt.days < 330)
                  & ((flows["start"] - fy["end"]).dt.days.abs() <= 7)]
    if later.empty:
        return total, fy["end"]
    ytd = later.loc[later["end"].idxmax()]
    prior = flows[[_near(s, ytd["start"] - pd.DateOffset(years=1), 15) and _near(e, ytd["end"] - pd.DateOffset(years=1), 15)
                   for s, e in zip(flows["start"], flows["end"])]]
    if prior.empty:
        return total, fy["end"]  # kan ikke danne TTM; brug seneste hele år
    prior_row = prior.iloc[(prior["end"] - (ytd["end"] - pd.DateOffset(years=1))).abs().argmin()]
    return total + float(ytd["val"]) - float(prior_row["val"]), ytd["end"]


def _flow(known: pd.DataFrame, date: pd.Timestamp, concept: str):
    """TTM for et begreb: blandt tags vinder det med den nyeste periodeslutning (tie: tag-rækkefølgen)."""
    best = None
    for tag in FLOW[concept]:
        part = known[known["tag"] == tag]
        if part.empty:
            continue
        result = _ttm(part, date)
        if result is not None and (best is None or result[1] > best[1]):
            best = result
    return None if best is None else best[0]


def _instant(known: pd.DataFrame, date: pd.Timestamp, concept: str, at_end: pd.Timestamp | None = None):
    """(værdi, slutdato) for seneste balancetal; med `at_end` kun tal for netop den dato."""
    for tag in INSTANT[concept]:
        part = known[(known["tag"] == tag) & known["start"].isna()]
        if at_end is not None:
            part = part[part["end"] == at_end]
        if part.empty:
            continue
        row = part.loc[part["end"].idxmax()]
        if (date - row["end"]).days <= MAX_STALE_DAYS:
            return float(row["val"]), row["end"]
    return None


def _ratio(num, den):
    return None if num is None or den is None or den == 0 else num / den


def as_of(ticker_facts, date) -> dict:
    """Nøgletal ud fra tal indleveret senest `date` (inklusive). `ticker_facts`: companyfacts-dict eller `facts_table`.

    Returnerer {eps_ttm, roe, roa, gross_margin, debt_equity, interest_coverage, revenue_growth, last_filed};
    manglende tal er None. Aldrig tal fra fremtiden: kun rækker med filed <= date.
    """
    table = facts_table(ticker_facts) if isinstance(ticker_facts, dict) else ticker_facts
    date = pd.Timestamp(date)
    known = _known(table, date)
    out = {key: None for key in METRICS}
    out["last_filed"] = None if known.empty else known["filed"].max()
    if known.empty:
        return out
    revenue = _flow(known, date, "revenue")
    income = _flow(known, date, "net_income")
    equity = _instant(known, date, "equity")
    assets = _instant(known, date, "assets")
    out["eps_ttm"] = _flow(known, date, "eps")
    if equity is not None and equity[0] > 0:
        out["roe"] = _ratio(income, equity[0])
        lt = _instant(known, date, "debt_lt", equity[1])
        if lt is not None:
            st = _instant(known, date, "debt_st", equity[1])
            out["debt_equity"] = (lt[0] + (st[0] if st else 0.0)) / equity[0]
    if assets is not None and assets[0] > 0:
        out["roa"] = _ratio(income, assets[0])
    if revenue is not None and revenue > 0:
        out["gross_margin"] = _ratio(_flow(known, date, "gross_profit"), revenue)
        before = _known(table, date - pd.Timedelta(days=365))
        old = _flow(before, date - pd.Timedelta(days=365), "revenue") if not before.empty else None
        if old is not None and old > 0:
            out["revenue_growth"] = revenue / old - 1
    interest = _flow(known, date, "interest")
    if interest is not None and interest > 0:
        out["interest_coverage"] = _ratio(_flow(known, date, "op_income"), interest)
    return out


def snapshots(table: pd.DataFrame, since: str = "2008-01-01") -> pd.DataFrame:
    """Nøgletal på hver dato, hvor nye tal blev indleveret (index = filed-dato). Bruges som trappefunktion:
    værdien for en vilkårlig dato er rækken med den seneste filed-dato <= datoen."""
    dates = [d for d in table["filed"].drop_duplicates().sort_values() if d >= pd.Timestamp(since)]
    rows = {d: as_of(table, d) for d in dates}
    frame = pd.DataFrame.from_dict(rows, orient="index")
    frame.index.name = "filed"
    return frame


def at_dates(snap: pd.DataFrame, dates: pd.DatetimeIndex, lag_days: int = 1) -> pd.DataFrame:
    """Nøgletal pr. dato i `dates`, kun med snapshot-datoer <= dato − `lag_days` (forsinkelse mod kig ind i fremtiden).
    Kolonnen `snap_date` er snapshot'ets filed-dato (bruges til splitjustering af EPS)."""
    if snap.empty:
        return pd.DataFrame(index=dates, columns=[*METRICS, "snap_date"], dtype=float)
    pos = snap.index.searchsorted(dates - pd.Timedelta(days=lag_days), side="right") - 1
    out = snap.iloc[np.clip(pos, 0, len(snap) - 1)].copy()
    out.index = dates
    out.loc[pos < 0, :] = np.nan
    out["snap_date"] = pd.Series(snap.index[np.clip(pos, 0, len(snap) - 1)], index=dates).where(pos >= 0)
    return out


# --- forenklet point-in-time Quality og Value ------------------------------------------------------------------
# NB: Tilnærmelser til MSS' scorer, IKKE samme formel. Quality: percentil i tværsnittet (alle aktier med tal på datoen)
# af ROE, ROA, bruttomargin, rentedækning, omsætningsvækst og (omvendt) gæld/egenkapital, middelværdien rangeret igen
# (som quality_rank.py), kræver mindst halvdelen af nøgletallene. Value: aktiens P/E (kurs / TTM-EPS) mod aktiens egen
# P/E-historik til og med datoen (højst 10 år, mindst 3 år): andelen af tidligere uger med højere P/E, i procent.
QUALITY_HIGHER = ("roe", "roa", "gross_margin", "interest_coverage", "revenue_growth")
QUALITY_LOWER = ("debt_equity",)
MIN_UNIVERSE = 50
PE_MAX = 500.0
PE_MIN_WEEKS, PE_WINDOW_WEEKS = 156, 520


def quality_percentile(metric_tables: dict[str, pd.DataFrame], min_share: float = 0.5) -> pd.DataFrame:
    """Quality 0-100 (række = dato, kolonne = ticker) ud fra {nøgletal: dato x ticker}; NaN hvis for få data.
    Datoer med under MIN_UNIVERSE aktier får ingen score."""
    ranks = []
    for key in (*QUALITY_HIGHER, *QUALITY_LOWER):
        table = metric_tables.get(key)
        if table is None:
            continue
        table = table.replace([np.inf, -np.inf], np.nan)
        ranks.append(table.rank(axis=1, pct=True, ascending=key not in QUALITY_LOWER) * 100)
    if not ranks:
        return pd.DataFrame()
    stack = np.stack([r.to_numpy() for r in ranks])
    count = (~np.isnan(stack)).sum(axis=0)
    mean = np.where(count >= max(1, int(np.ceil(min_share * len(ranks)))), np.nanmean(stack, axis=0), np.nan)
    combined = pd.DataFrame(mean, index=ranks[0].index, columns=ranks[0].columns).rank(axis=1, pct=True) * 100
    enough = combined.notna().sum(axis=1) >= MIN_UNIVERSE
    return combined.where(enough, np.nan)


def value_score(price: pd.Series, eps: pd.Series) -> pd.Series:
    """Value 0-100 pr. uge for én aktie: andel af egne tidligere ugers P/E (til og med i dag, højst 10 år), der er
    højere end dagens. 50 = P/E er lig egen median. Kræver mindst 3 års P/E-historik; EPS <= 0 giver ingen P/E."""
    pe = (price / eps).where((eps > 0) & (price > 0))
    pe = pe.where(pe <= PE_MAX)
    values = pe.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    for i in range(len(values)):
        if not np.isfinite(values[i]):
            continue
        window = values[max(0, i - PE_WINDOW_WEEKS + 1):i + 1]
        window = window[np.isfinite(window)]
        if len(window) >= PE_MIN_WEEKS:
            out[i] = 100.0 * (window > values[i]).sum() / len(window)
    return pd.Series(out, index=pe.index)
