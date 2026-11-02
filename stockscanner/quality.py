"""Gennemsigtig kvalitetsscore ud fra årsregnskaber (vores EGEN model).

Modellen er bygget på offentligt kendt finansteori (ROIC, Piotroski F-score, Altman Z m.fl.)
med eksplicitte tærskler og vægte i denne fil. Den er IKKE en kopi af og IKKE ensbetydende
med nogen anden udbyders score (fx MyStockScanner). Score er en screening, IKKE en
købsanbefaling.

Begrænsninger:
- Absolutte tærskler. Peer-/sektorrelativ scoring er en senere fase og indgår ikke endnu.
- Datakilden (yfinance) er uofficiel og giver typisk kun ca. 4 årsregnskaber.
- Manglende data bliver None og rapporteres; der gættes aldrig.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import statistics

from stockscanner.fundamentals import FundamentalData


# --- Søjler og vægte (summer til 100) ---------------------------------------------------
PILLAR_WEIGHTS = {
    "Lønsomhed": 35,
    "Stabilitet og vækst": 25,
    "Cashflow": 20,
    "Balance": 20,
}

# Hvilken søjle hver måling tilhører.
METRIC_PILLAR = {
    "roic": "Lønsomhed", "roe": "Lønsomhed", "roa": "Lønsomhed", "roce": "Lønsomhed",
    "gross_margin": "Lønsomhed", "operating_margin": "Lønsomhed",
    "margin_stability": "Stabilitet og vækst", "revenue_cagr": "Stabilitet og vækst",
    "fcf_margin": "Cashflow", "cash_conversion": "Cashflow",
    "current_ratio": "Balance", "net_debt_ebitda": "Balance", "interest_coverage": "Balance",
    "altman_z": "Balance", "piotroski": "Balance",
}

METRIC_LABELS = {
    "roic": "ROIC", "roe": "ROE", "roa": "ROA", "roce": "ROCE",
    "gross_margin": "Bruttomargin", "operating_margin": "Driftsmargin",
    "margin_stability": "Driftsmargin – stabilitet (std.afv.)",
    "revenue_cagr": "Omsætningsvækst (CAGR)",
    "fcf_margin": "FCF-margin", "cash_conversion": "Cash conversion (FCF/resultat)",
    "current_ratio": "Likviditetsgrad", "net_debt_ebitda": "Nettogæld / EBITDA",
    "interest_coverage": "Rentedækning (EBIT/renter)",
    "altman_z": "Altman Z", "piotroski": "Piotroski F-score",
}

# Målinger der ikke giver mening for finansielle selskaber (banker, forsikring).
FINANCE_SKIPPED = {
    "roic", "roce", "gross_margin", "current_ratio", "net_debt_ebitda", "altman_z",
    "interest_coverage",  # renter er bankens driftsomkostning, ikke finansieringsbyrde
    "fcf_margin", "cash_conversion",  # cashflow er meningsløst for banker/forsikring
}

# Brancher (yfinance-industry) der behandles som finansielle. Sektoren bruges IKKE:
# fx Visa har sektor "Financial Services" men branchen "Credit Services" og får fuld model.
FINANCE_INDUSTRY_PREFIXES = (
    "banks", "insurance", "capital markets", "asset management",
    "mortgage finance", "financial conglomerates",
)
FINANCE_INDUSTRY_EXCLUDED_PREFIXES = ("insurance brokers",)

# Tærskeltabel: (værdi, point 0-100). Lineær interpolation mellem punkterne;
# værdier uden for yderpunkterne får yderpunktets point. Brøker (0,08 = 8 %).
THRESHOLDS: dict[str, list[tuple[float, float]]] = {
    "roic": [(0.0, 0), (0.10, 50), (0.25, 80), (0.40, 100)],
    "roe": [(0.0, 0), (0.12, 50), (0.30, 80), (0.50, 100)],
    "roa": [(0.0, 0), (0.05, 50), (0.12, 80), (0.20, 100)],
    "roce": [(0.0, 0), (0.12, 50), (0.30, 80), (0.50, 100)],
    "gross_margin": [(0.10, 0), (0.35, 50), (0.60, 80), (0.80, 100)],
    "operating_margin": [(0.0, 0), (0.12, 50), (0.25, 80), (0.40, 100)],
    # Lavere standardafvigelse = mere stabil (faldende kurve).
    "margin_stability": [(0.02, 100), (0.05, 60), (0.10, 30), (0.20, 0)],
    "revenue_cagr": [(-0.05, 0), (0.0, 30), (0.05, 60), (0.15, 100)],
    "fcf_margin": [(0.0, 0), (0.08, 50), (0.20, 100)],
    "cash_conversion": [(0.0, 0), (0.8, 50), (1.2, 100)],
    "current_ratio": [(0.5, 0), (1.0, 40), (1.5, 70), (2.5, 100)],
    # Lavere gæld er bedre; negativ nettogæld (nettokassebeholdning) giver 100.
    "net_debt_ebitda": [(0.0, 100), (2.0, 70), (3.0, 50), (5.0, 10), (7.0, 0)],
    "interest_coverage": [(1.0, 0), (3.0, 40), (8.0, 80), (15.0, 100)],
    # Altmans klassiske zoner: <1,81 nødlidende, >2,99 sikker.
    "altman_z": [(1.0, 0), (1.81, 30), (2.99, 70), (4.0, 100)],
}

MIN_COVERAGE = 0.60          # mindst 60 % af vægten skal være dækket af målinger
MIN_YEARS_STABILITY = 3
MIN_YEARS_CAGR = 3
MIN_PIOTROSKI_CHECKS = 5     # færre beregnelige tests => ingen score
DEFAULT_TAX_RATE = 0.22
MODEL_NOTE = "Fuld model (ikke-finansielt selskab)"
MODEL_NOTE_FINANCE = "begrænset (finans)"


@dataclass(frozen=True)
class MetricResult:
    key: str
    label: str
    pillar: str
    value: float | None
    score: float | None
    reason: str
    applicable: bool = True


@dataclass(frozen=True)
class QualityResult:
    ticker: str
    total: float | None
    label: str                      # Stærk/God/Middel/Svag eller "Utilstrækkelige data"
    pillars: dict[str, float | None]
    metrics: list[MetricResult]
    missing: list[str]              # relevante målinger der ikke kunne beregnes
    coverage: float                 # andel af vægten (0-1) dækket af målinger
    data_years: list[str]           # regnskabsdatoer brugt
    currency: str
    model_note: str
    is_financial: bool
    source: str = ""
    fetched_at_utc: str = ""
    notes: list[str] = field(default_factory=list)


def interpolate(points: list[tuple[float, float]], value: float) -> float:
    """Stykvis lineær interpolation med klemning ved yderpunkterne."""
    pts = sorted(points)
    if value <= pts[0][0]:
        return float(pts[0][1])
    if value >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= value <= x1:
            return float(y0 + (y1 - y0) * (value - x0) / (x1 - x0))
    return float(pts[-1][1])  # kan ikke nås


def score_metric(key: str, value: float) -> float:
    return round(interpolate(THRESHOLDS[key], value), 1)


def label_for(total: float | None) -> str:
    if total is None:
        return "Utilstrækkelige data"
    if total >= 80:
        return "Stærk"
    if total >= 60:
        return "God"
    if total >= 40:
        return "Middel"
    return "Svag"


def is_financial(sector: str, industry: str) -> bool:
    """Finansielt selskab ud fra BRANCHEN (industry), ikke sektoren. `sector` bruges ikke."""
    text = (industry or "").strip().lower()
    if text.startswith(FINANCE_INDUSTRY_EXCLUDED_PREFIXES):
        return False
    return text.startswith(FINANCE_INDUSTRY_PREFIXES)


def _to_date(value) -> date:
    """Regnskabsdato som ISO-streng (som gemt), date eller datetime."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _pct(value: float) -> str:
    return f"{value * 100:.1f} %".replace(".", ",")


def _num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def effective_tax_rate(year: dict[str, float | None]) -> float:
    """Skattesats = skat / resultat før skat, klemt til 0–35 %; ellers 22 %."""
    tax, pretax = year.get("tax_provision"), year.get("pretax_income")
    if tax is None or pretax is None or pretax <= 0:
        return DEFAULT_TAX_RATE
    return min(0.35, max(0.0, tax / pretax))


def _operating_margin(year: dict[str, float | None]) -> float | None:
    op = year.get("operating_income")
    if op is None:
        op = year.get("ebit")
    return _div(op, year.get("revenue"))


PIOTROSKI_NAMES = [
    "ROA > 0", "Driftscashflow > 0", "ROA steget", "Cashflow > resultat",
    "Langfristet gæld/gns. aktiver faldet", "Likviditetsgrad steget", "Ingen nye aktier",
    "Bruttomargin steget", "Aktivomsætning steget",
]


def piotroski(
    years: list[dict[str, float | None]],
    share_labels: list[str | None] | None = None,
) -> tuple[int, int, list[str], list[str]]:
    """Piotroski F-score (9 standardtests), nyeste år først i `years`.
    Returnerer (point, antal beregnelige, beståede tests, ikke-beregnelige tests).

    Standardformer: ROA = resultat / aktiver ved ÅRETS START (forrige årsultimo); ΔROA og
    Δaktivomsætning bruger også startaktiver og kræver derfor 3 regnskabsår; gældsgrad =
    langfristet gæld / GENNEMSNITLIGE aktiver (kræver 3 år til sammenligningen); aktieudstedelse
    sammenlignes kun, hvis begge år har aktieantal fra SAMME yfinance-label.
    En test uden fuldt datagrundlag er "ikke beregnelig" og tæller hverken som bestået eller dumpet."""
    empty: dict[str, float | None] = {}
    y0 = years[0] if len(years) > 0 else empty
    y1 = years[1] if len(years) > 1 else empty
    y2 = years[2] if len(years) > 2 else empty
    labels = list(share_labels or []) + [None, None]

    def avg(a, b):
        return None if a is None or b is None else (a + b) / 2

    def lt(a, b):
        return None if a is None or b is None else a < b

    def gt(a, b):
        return None if a is None or b is None else a > b

    roa0 = _div(y0.get("net_income"), y1.get("total_assets"))
    roa1 = _div(y1.get("net_income"), y2.get("total_assets"))
    ocf, ni = y0.get("operating_cash_flow"), y0.get("net_income")
    lev0 = _div(y0.get("long_term_debt"), avg(y0.get("total_assets"), y1.get("total_assets")))
    lev1 = _div(y1.get("long_term_debt"), avg(y1.get("total_assets"), y2.get("total_assets")))
    cr0 = _div(y0.get("current_assets"), y0.get("current_liabilities"))
    cr1 = _div(y1.get("current_assets"), y1.get("current_liabilities"))
    sh0, sh1 = y0.get("shares"), y1.get("shares")
    same_source = labels[0] is not None and labels[0] == labels[1]
    gm0 = _div(y0.get("gross_profit"), y0.get("revenue"))
    gm1 = _div(y1.get("gross_profit"), y1.get("revenue"))
    at0 = _div(y0.get("revenue"), y1.get("total_assets"))
    at1 = _div(y1.get("revenue"), y2.get("total_assets"))

    results: list[bool | None] = [
        None if roa0 is None else roa0 > 0,
        None if ocf is None else ocf > 0,
        gt(roa0, roa1),
        None if ocf is None or ni is None else ocf > ni,
        lt(lev0, lev1),
        gt(cr0, cr1),
        None if sh0 is None or sh1 is None or not same_source else sh0 <= sh1,
        gt(gm0, gm1),
        gt(at0, at1),
    ]
    passed = [name for name, ok in zip(PIOTROSKI_NAMES, results) if ok]
    not_run = [name for name, ok in zip(PIOTROSKI_NAMES, results) if ok is None]
    return len(passed), len(PIOTROSKI_NAMES) - len(not_run), passed, not_run


def altman_z(year: dict[str, float | None], market_cap: float | None) -> float | None:
    """Altman Z (original 1968, børsnoterede producenter):
    1,2*(AK/A) + 1,4*(OR/A) + 3,3*(EBIT/A) + 0,6*(Markedsværdi/Gæld) + 1,0*(Omsætning/A)."""
    ta = year.get("total_assets")
    ca, cl = year.get("current_assets"), year.get("current_liabilities")
    re_, ebit = year.get("retained_earnings"), year.get("ebit")
    tl, sales = year.get("total_liabilities"), year.get("revenue")
    needed = [ta, ca, cl, re_, ebit, tl, sales, market_cap]
    if any(item is None for item in needed) or not ta or not tl:
        return None
    return (
        1.2 * (ca - cl) / ta + 1.4 * re_ / ta + 3.3 * ebit / ta
        + 0.6 * market_cap / tl + 1.0 * sales / ta
    )


def _missing_inputs(year: dict[str, float | None], fields: list[str]) -> str:
    absent = [name for name in fields if year.get(name) is None]
    return ", ".join(absent)


def score_quality(data: FundamentalData) -> QualityResult:
    """Beregn kvalitetsscore for ét selskab ud fra normaliserede regnskabstal."""
    finance = is_financial(data.sector, data.industry)
    years = [item.values for item in data.years]
    dates = [item.end_date for item in data.years]
    notes: list[str] = []
    metrics: list[MetricResult] = []

    def add(key: str, value: float | None, reason: str, score: float | None = None, scored: bool = True) -> None:
        """Registrér måling. score beregnes ud fra tærsklen hvis ikke angivet og value findes."""
        if score is None and value is not None and scored:
            score = score_metric(key, value)
        metrics.append(MetricResult(key, METRIC_LABELS[key], METRIC_PILLAR[key], value, score, reason))

    def skip(key: str) -> None:
        metrics.append(MetricResult(
            key, METRIC_LABELS[key], METRIC_PILLAR[key], None, None,
            "Ikke relevant for finansielle selskaber – springes over.", applicable=False,
        ))

    def unavailable(key: str, why: str) -> None:
        metrics.append(MetricResult(key, METRIC_LABELS[key], METRIC_PILLAR[key], None, None, why))

    new = years[0] if years else {}
    old = years[1] if len(years) > 1 else None

    # --- Lønsomhed ---
    if finance:
        skip("roic")
    else:
        ebit, debt, equity, cash = new.get("ebit"), new.get("total_debt"), new.get("stockholders_equity"), new.get("cash")
        if None in (ebit, debt, equity, cash):
            unavailable("roic", "Mangler: " + _missing_inputs(new, ["ebit", "total_debt", "stockholders_equity", "cash"]))
        else:
            invested = debt + equity - cash
            if invested <= 0:
                unavailable("roic", "Investeret kapital er nul eller negativ – ROIC ikke meningsfuld.")
            else:
                tax = effective_tax_rate(new)
                roic = ebit * (1 - tax) / invested
                add("roic", roic, f"NOPAT/investeret kapital ({_pct(roic)}), skattesats {_pct(tax)}.")

    roe = _div(new.get("net_income"), new.get("stockholders_equity"))
    if roe is None or (new.get("stockholders_equity") or 0) <= 0:
        unavailable("roe", "Mangler resultat eller positiv egenkapital.")
    else:
        add("roe", roe, f"Resultat/egenkapital ({_pct(roe)}).")

    roa = _div(new.get("net_income"), new.get("total_assets"))
    if roa is None:
        unavailable("roa", "Mangler: " + _missing_inputs(new, ["net_income", "total_assets"]))
    else:
        add("roa", roa, f"Resultat/aktiver ({_pct(roa)}).")

    if finance:
        skip("roce")
    else:
        ta, cl, ebit = new.get("total_assets"), new.get("current_liabilities"), new.get("ebit")
        if None in (ta, cl, ebit) or ta - cl <= 0:
            unavailable("roce", "Mangler: " + (_missing_inputs(new, ["total_assets", "current_liabilities", "ebit"]) or "kapital ≤ 0"))
        else:
            roce = ebit / (ta - cl)
            add("roce", roce, f"EBIT/(aktiver − kortfristet gæld) ({_pct(roce)}).")

    if finance:
        skip("gross_margin")
    else:
        gm = _div(new.get("gross_profit"), new.get("revenue"))
        if gm is None:
            unavailable("gross_margin", "Mangler: " + _missing_inputs(new, ["gross_profit", "revenue"]))
        else:
            add("gross_margin", gm, f"Bruttoresultat/omsætning ({_pct(gm)}).")

    om = _operating_margin(new) if years else None
    if om is None:
        unavailable("operating_margin", "Mangler driftsresultat eller omsætning.")
    else:
        add("operating_margin", om, f"Driftsresultat/omsætning ({_pct(om)}).")

    # --- Stabilitet og vækst ---
    margins = [m for m in (_operating_margin(y) for y in years) if m is not None]
    if len(margins) < MIN_YEARS_STABILITY:
        unavailable("margin_stability", f"Kræver mindst {MIN_YEARS_STABILITY} år med driftsmargin; har {len(margins)}.")
    else:
        sd = statistics.stdev(margins)
        add("margin_stability", sd, f"Standardafvigelse af driftsmargin over {len(margins)} år: {_pct(sd)}-point (lavere er bedre).")

    revs = [(d, y.get("revenue")) for d, y in zip(dates, years) if y.get("revenue") is not None]
    if len(revs) < MIN_YEARS_CAGR:
        unavailable("revenue_cagr", f"Kræver mindst {MIN_YEARS_CAGR} år med omsætning; har {len(revs)}.")
    else:
        first, last = revs[-1][1], revs[0][1]
        if first <= 0 or last <= 0:
            unavailable("revenue_cagr", "Omsætning ≤ 0 i start eller slut – CAGR kan ikke beregnes.")
        else:
            # Forløbet tid ud fra regnskabsdatoerne (ikke antal rækker), så huller i data ikke forvrider CAGR.
            elapsed = (_to_date(revs[0][0]) - _to_date(revs[-1][0])).days / 365.25
            if elapsed <= 0:
                unavailable("revenue_cagr", "Regnskabsdatoerne giver ingen forløbet tid – CAGR kan ikke beregnes.")
            else:
                cagr = (last / first) ** (1 / elapsed) - 1
                add("revenue_cagr", cagr, f"Gennemsnitlig årlig vækst over {_num(elapsed, 1)} år ({_pct(cagr)}).")

    # --- Cashflow ---
    fcf = new.get("free_cash_flow")
    fm = _div(fcf, new.get("revenue"))
    ni = new.get("net_income")
    if finance:
        skip("fcf_margin")
        skip("cash_conversion")
    elif fm is None:
        unavailable("fcf_margin", "Mangler fri cashflow eller omsætning.")
    else:
        add("fcf_margin", fm, f"Fri cashflow/omsætning ({_pct(fm)}).")

    if finance:
        pass
    elif fcf is None or ni is None:
        unavailable("cash_conversion", "Mangler fri cashflow eller resultat.")
    elif ni <= 0:
        unavailable("cash_conversion", "Resultatet er ≤ 0 – cash conversion ikke meningsfuld.")
    else:
        conv = fcf / ni
        add("cash_conversion", conv, f"Fri cashflow/resultat ({_num(conv)}).")

    # --- Balance ---
    if finance:
        skip("current_ratio")
        skip("net_debt_ebitda")
        skip("interest_coverage")
        skip("altman_z")
    else:
        cr = _div(new.get("current_assets"), new.get("current_liabilities"))
        if cr is None:
            unavailable("current_ratio", "Mangler omsætningsaktiver eller kortfristet gæld.")
        else:
            add("current_ratio", cr, f"Omsætningsaktiver/kortfristet gæld ({_num(cr)}).")

        debt, cash, ebitda = new.get("total_debt"), new.get("cash"), new.get("ebitda")
        if None in (debt, cash, ebitda):
            unavailable("net_debt_ebitda", "Mangler: " + _missing_inputs(new, ["total_debt", "cash", "ebitda"]))
        else:
            net_debt = debt - cash
            if ebitda <= 0:
                score = 100.0 if net_debt <= 0 else 0.0
                add("net_debt_ebitda", None, "EBITDA ≤ 0 – kvotient ikke meningsfuld; " + (
                    "nettokassebeholdning giver fuld score." if net_debt <= 0 else "nettogæld uden positiv EBITDA giver 0."), score=score)
            else:
                ratio = net_debt / ebitda
                add("net_debt_ebitda", ratio, f"Nettogæld/EBITDA ({_num(ratio)}); negativ = nettokassebeholdning.")

        ebit, interest = new.get("ebit"), new.get("interest_expense")
        if ebit is None or interest is None:
            unavailable("interest_coverage", "Mangler: " + _missing_inputs(new, ["ebit", "interest_expense"]))
        elif interest == 0:
            add("interest_coverage", None, "Ingen renteudgifter oplyst.", score=100.0)
        else:
            cover = ebit / abs(interest)
            add("interest_coverage", cover, f"EBIT/renteudgifter ({_num(cover)}).")

        if data.currency and data.reporting_currency and data.currency != data.reporting_currency:
            unavailable("altman_z", f"Markedsværdi i {data.currency}, regnskab i {data.reporting_currency} – ikke sammenlignelige.")
        else:
            z = altman_z(new, data.market_cap)
            if z is None:
                unavailable("altman_z", "Mangler: " + (_missing_inputs(new, [
                    "total_assets", "current_assets", "current_liabilities", "retained_earnings",
                    "ebit", "total_liabilities", "revenue"]) or "") + ("" if data.market_cap is not None else " market_cap"))
            else:
                add("altman_z", z, f"Altman Z (original 1968, aktuel markedsværdi): {_num(z)}.")

    if old is None:
        unavailable("piotroski", "Kræver mindst 2 regnskabsår.")
    else:
        points, computed, passed, not_run = piotroski(years, [item.share_label for item in data.years])
        if computed < MIN_PIOTROSKI_CHECKS:
            unavailable("piotroski", f"Kun {computed} af 9 tests kunne beregnes (kræver {MIN_PIOTROSKI_CHECKS}). "
                        f"Ikke beregnelige: {', '.join(not_run)}.")
        else:
            reason = f"{points} af {computed} beregnelige tests bestået (9 findes). Bestået: {', '.join(passed) or 'ingen'}."
            if not_run:
                reason += f" Ikke beregnelige: {', '.join(not_run)}."
                notes.append(f"Piotroski: kun {computed} af 9 tests var beregnelige.")
            add("piotroski", float(points), reason, score=round(100 * points / computed, 1))

    # --- Aggregering ---
    pillar_scores: dict[str, float | None] = {}
    coverage = 0.0
    relevant_weight = 0
    for pillar, weight in PILLAR_WEIGHTS.items():
        applicable = [m for m in metrics if m.pillar == pillar and m.applicable]
        scored = [m.score for m in applicable if m.score is not None]
        pillar_scores[pillar] = round(sum(scored) / len(scored), 1) if scored else None
        if applicable:
            # Søjler uden relevante målinger (fx Cashflow for banker) udgår af vægtningen.
            relevant_weight += weight
            coverage += weight * len(scored) / len(applicable)
    coverage = coverage / relevant_weight if relevant_weight else 0.0

    with_data = {p: s for p, s in pillar_scores.items() if s is not None}
    if coverage < MIN_COVERAGE or not with_data:
        total = None
    else:
        weight_sum = sum(PILLAR_WEIGHTS[p] for p in with_data)
        total = round(sum(PILLAR_WEIGHTS[p] * s for p, s in with_data.items()) / weight_sum, 1)

    if total is None:
        notes.append(f"Dækning {coverage * 100:.0f} % er under kravet på {MIN_COVERAGE * 100:.0f} %.")
    missing = [m.label for m in metrics if m.applicable and m.score is None]
    return QualityResult(
        ticker=data.ticker, total=total, label=label_for(total), pillars=pillar_scores,
        metrics=metrics, missing=missing, coverage=round(coverage, 3), data_years=dates,
        currency=data.reporting_currency or data.currency,
        model_note=MODEL_NOTE_FINANCE if finance else MODEL_NOTE, is_financial=finance,
        source=data.source, fetched_at_utc=data.fetched_at_utc, notes=notes,
    )
