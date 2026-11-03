"""B-15: Kalibrér vores værktøjer mod facitlisten data/mss_video_observations.csv (MSS' værdier set i videoer).

Trin: (1) behold rækker med brugbar dato (fuld dato, år-måned eller optagelsesdato udledt af videotitlen),
(2) oversæt selskabsnavne til yfinance-tickers (data/b15_ticker_map.csv – kan rettes i hånden),
(3) beregn VORES værdi på datoen med kun data til og med datoen (ingen look-ahead) for StockMap, TPI-lite,
MTI-lite, 200-dages glidende gennemsnit, regressionskanal og P/E-kanal/P/E,
(4) skriv hit-rate, forvekslingstabeller, rangkorrelationer og misses.
Kvalitets-percentiler sammenlignes kun løst: vores tal er dagens, ikke point-in-time.
Kørsel: .venv/Scripts/python scripts/calibrate_b15.py [--ingen-net] [--max-miss 12]
Resultater: data/b15_resultater.csv og data/b15_rapport.md. Facitlisten rettes aldrig. Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

import argparse
import csv
import pickle
import re
import sys
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stockscanner import calibration as cal  # noqa: E402
from stockscanner.mti_lite import home_index, mti_state  # noqa: E402
from stockscanner.regression import regression_channel  # noqa: E402
from stockscanner.stockmap import points_up, rotation, signals  # noqa: E402
from stockscanner.tpi_lite import tpi_states  # noqa: E402
from stockscanner.valuation import pe_candidates  # noqa: E402

OBS = ROOT / "data" / "mss_video_observations.csv"
MAP = ROOT / "data" / "b15_ticker_map.csv"
CACHE = ROOT / "data" / "cache_b15"
RESULTS = ROOT / "data" / "b15_resultater.csv"
REPORT = ROOT / "data" / "b15_rapport.md"
BENCH = "RSP"

# Manuelt kontrollerede navne -> yfinance-ticker (nøgle = cal.normalize_name). Gæt på stavefejl i
# transskriptionen (MSS' tale er auto-transskriberet) står i GUESS og tæller ikke med i statistikken.
SEED = {
    "novo nordisk": "NOVO-B.CO", "novo": "NOVO-B.CO", "genmab": "GMAB.CO", "genmap": "GMAB.CO", "visa": "V",
    "tesla": "TSLA", "nvidia": "NVDA", "pandora": "PNDORA.CO", "getinge": "GETI-B.ST", "betsson": "BETS-B.ST",
    "hennes & mauritz": "HM-B.ST", "mattel": "MAT", "netcompany": "NETC.CO", "royal unibrew": "RBREW.CO",
    "vestas": "VWS.CO", "gn store nord": "GN.CO", "carlsberg": "CARL-B.CO", "dsv": "DSV.CO",
    "maersk": "MAERSK-B.CO", "orsted": "ORSTED.CO", "danske bank": "DANSKE.CO", "demant": "DEMANT.CO",
    "fl smith": "FLS.CO", "sandvik": "SAND.ST", "volvo": "VOLV-B.ST", "texas instruments": "TXN",
    "amazon": "AMZN", "apple": "AAPL", "microsoft": "MSFT", "micron": "MU", "tsm": "TSM", "taiwan semi": "TSM",
    "rheinmetall": "RHM.DE", "regnmetall": "RHM.DE", "freeport mcmoran": "FCX", "barrick mining": "B",
    "rio tinto": "RIO.L", "glencore": "GLEN.L", "royal caribbean": "RCL", "carvana": "CVNA", "coinbase": "COIN",
    "crowdstrike": "CRWD", "kroger": "KR", "synchrony financials": "SYF", "teva": "TEVA", "paypal": "PYPL",
    "adobe": "ADBE", "amd": "AMD", "adi": "ADI", "nxpi": "NXPI", "rtx": "RTX", "first solar": "FSLR",
    "ferrari": "RACE", "kering": "KER.PA", "nkt": "NKT.CO", "iss": "ISS.CO", "solar": "SOLAR-B.CO",
    "simcorp": "SIM.CO", "ringkobing landbobank": "RILBA.CO", "matas": "MATAS.CO", "ambu": "AMBU-B.CO",
    "arjo": "ARJO-B.ST", "fingerprint": "FING-B.ST", "bioporto": "BIOPOR.CO", "per aarsleff": "PAAL-B.CO",
    "per aarhusleff": "PAAL-B.CO", "tryg": "TRYG.CO", "munters group": "MTRS.ST", "modern times group": "MTG-B.ST",
    "protector forsikring": "PROT.OL", "stolt nielsen": "SNI.OL", "hafnia": "HAFNI.OL", "evolution": "EVO.ST",
    "daimler truck": "DTG.DE", "quanta services": "PWR", "cdns": "CDNS", "amgen": "AMGN", "walmart": "WMT",
    "target": "TGT", "lundbaek": "LUN.CO", "tk tankers": "TNK", "ultra beauty": "ULTA",
    # gæt (navnet i transskriptionen er forvansket) – bruges ikke i statistikken
    "alcabello": "ALK-B.CO", "algebello": "ALK-B.CO", "kemomatic": "CHEMM.CO", "chemomatic": "CHEMM.CO",
    "celan pharma": "ZEAL.CO", "orphazine": "ORPHA.CO", "plejt": "PLEJD.ST", "bill finger": "GBF.DE",
    "nokian tyres": "TYRES.HE", "ceylon farma": "", "shape robotics": "", "tall brothers": "", "seloxid": "",
}
GUESS = {"alcabello", "algebello", "kemomatic", "chemomatic", "celan pharma", "orphazine", "plejt",
         "bill finger", "nokian tyres"}


@dataclass
class Obs:
    row: dict
    day: date
    precision: str
    uncertain: bool
    name: str
    ticker: str
    group: str

    def candidates(self) -> list[date]:
        return cal.candidate_dates(self.day, self.precision, self.uncertain)


@dataclass
class Result:
    tool: str
    kind: str          # delmåling inden for værktøjet
    obs: Obs
    mss: object
    ours: object
    hit: bool | None
    lenient: bool | None = None
    detail: str = ""


@dataclass
class Store:
    prices: dict[str, pd.DataFrame] = field(default_factory=dict)
    pe: dict[str, pd.Series] = field(default_factory=dict)


# ---------------------------------------------------------------- data

def naive(frame: pd.DataFrame) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    frame = frame.copy()
    frame.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def cached(name: str, loader, tries: int = 3):
    """Pickle-cache; tomme resultater (None) og fejl gemmes ikke, så en forbigående netfejl kan prøves igen."""
    import time
    CACHE.mkdir(parents=True, exist_ok=True)
    file = CACHE / (re.sub(r"[^A-Za-z0-9._-]", "_", name) + ".pkl")
    if file.exists():
        value = pickle.loads(file.read_bytes())
        if value is not None:
            return value
    value = None
    for attempt in range(tries):
        try:
            value = loader()
        except Exception:  # noqa: BLE001
            if attempt == tries - 1:
                raise
        if value is not None:
            break
        time.sleep(2 * (attempt + 1))
    if value is not None:
        file.write_bytes(pickle.dumps(value))
    return value


def get_prices(ticker: str, offline: bool) -> pd.DataFrame | None:
    def load():
        if offline:
            return None
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=True, actions=False)
        if hist is None or hist.empty:
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        return naive(hist[["Open", "Close"]])
    try:
        frame = cached(f"px_{ticker}", load)
    except Exception as exc:  # noqa: BLE001 – netværksfejl logges, aktien springes over
        print(f"  kursfejl {ticker}: {exc}", file=sys.stderr)
        return None
    return frame


def get_pe(ticker: str, offline: bool) -> pd.Series | None:
    def load():
        if offline:
            return None
        from stockscanner.valuation import fetch_inputs
        return fetch_inputs(ticker).pe_history
    try:
        return cached(f"pe_{ticker}", load)
    except Exception as exc:  # noqa: BLE001
        print(f"  P/E-fejl {ticker}: {exc}", file=sys.stderr)
        return None


def upto(frame, day: date):
    return frame[frame.index <= pd.Timestamp(day)]


# ---------------------------------------------------------------- navnetabel

def build_map(names: dict[str, str], offline: bool) -> dict[str, dict]:
    """names: nøgle -> eksempel på råt navn. Bevarer rettelser i eksisterende data/b15_ticker_map.csv."""
    table: dict[str, dict] = {}
    if MAP.exists():
        with MAP.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                table[row["nøgle"]] = row
    for key, raw in names.items():
        if key in table and table[key]["ticker"]:
            continue
        _, hint = cal.clean_name(raw)
        if key in SEED and SEED[key]:
            ticker, source, sure = SEED[key], "manuel", "nej" if key in GUESS else "ja"
        elif hint:
            ticker, source, sure = hint, "parentes i facit", "nej"
        else:
            ticker, source, sure = "", "ukendt", "nej"
            if not offline:
                found = search_ticker(cal.clean_name(raw)[0])
                if found:
                    ticker, source = found, "yfinance-søgning"
        table[key] = {"nøgle": key, "navn_i_facit": raw, "ticker": ticker, "kilde": source, "sikker": sure,
                      "note": "uverificeret" if source != "manuel" else ""}
    MAP.parent.mkdir(parents=True, exist_ok=True)
    with MAP.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, ["nøgle", "navn_i_facit", "ticker", "kilde", "sikker", "note"], delimiter=";")
        writer.writeheader()
        writer.writerows(sorted(table.values(), key=lambda r: r["nøgle"]))
    return table


def search_ticker(name: str) -> str:
    try:
        import yfinance as yf
        for quote in yf.Search(name, max_results=5).quotes:
            if quote.get("quoteType") == "EQUITY":
                return quote["symbol"]
    except Exception:  # noqa: BLE001
        pass
    return ""


# ---------------------------------------------------------------- vores værdier

def stockmap_at(prices, bench, day):
    rot = rotation(upto(prices, day), upto(bench, day))
    if rot.empty or np.isnan(rot["angle"].iloc[-1]):
        return None
    last = rot.iloc[-1]
    return {"quadrant": last["quadrant"], "arrow": "op" if points_up(last["angle"]) else "ned",
            "angle": float(last["angle"]), "rot": rot, "week": rot.index[-1]}


def stockmap_signal(rot, day, mode: str) -> bool:
    """'event': køb-signal i de seneste 14 dage; 'state': seneste signal er køb og højst 12 uger gammelt."""
    sig = signals(rot)
    sig = sig[sig.index <= pd.Timestamp(day)]
    active = sig[sig != ""]
    if active.empty:
        return False
    if mode == "event":
        return bool((active.index[-1] >= pd.Timestamp(day) - pd.Timedelta(days=14)) and active.iloc[-1] == "køb")
    return bool(active.iloc[-1] == "køb" and active.index[-1] >= pd.Timestamp(day) - pd.Timedelta(weeks=12))


def tpi_at(prices, day):
    states = tpi_states(upto(prices, day))
    if states.empty:
        return None
    last = states.iloc[-1]
    return {"long": "gron" if last["long_green"] else "rod", "short": {"overkøbt": "overkobt"}.get(last["state"], last["state"]),
            "pct": float(last["short_pct"])}


def sma200_at(prices, day):
    close = upto(prices, day)["Close"]
    if len(close) < 200:
        return None
    sma = close.rolling(200).mean().iloc[-1]
    return {"side": "over" if close.iloc[-1] > sma else "under", "dev": float(close.iloc[-1] / sma - 1) * 100}


def regression_at(prices, day, weekly: bool):
    close = upto(prices, day)["Close"]
    if weekly:
        close = close.resample("W-FRI").last().dropna()
        window, look = 52, 2
    else:
        window, look = 126, 5
    if len(close) < window + look:
        return None
    ch = regression_channel(close, window)
    pos = np.where(close < ch["lower"], "under", np.where(close > ch["upper"], "over", "inde"))
    last = pos[-1]
    recent = set(pos[-look:]) - {"inde"}
    return {"class": last, "recent": recent}


def pe_at(pe: pd.Series, day):
    hist = pe[pe.index <= pd.Timestamp(day)].dropna()
    return hist


# ---------------------------------------------------------------- evaluering

def lenient_or(obs: Obs, fn, expected) -> tuple[bool | None, object]:
    """(strikt hit på selve datoen, lenient hit på nogen af datoerne). fn(day) -> vores kategori eller None."""
    first, hit_any = None, False
    for i, day in enumerate(obs.candidates()):
        got = fn(day)
        if i == 0:
            first = got
        if got is not None and got == expected:
            hit_any = True
    return first, hit_any


def evaluate(observations: list[Obs], store: Store) -> list[Result]:
    out: list[Result] = []
    bench = store.prices.get(BENCH)
    index_cache: dict[str, pd.DataFrame | None] = {}

    for o in observations:
        prices = store.prices.get(o.ticker)
        if prices is None or prices.empty:
            continue
        row = o.row
        text, tool, frame, note = row["tilstand_eller_vaerdi"], row["vaerktoej"], row["tidsramme"], row["note"]
        folded_frame = cal.normalize_name(frame + " " + tool)

        if o.group == "stockmap" and bench is not None:
            quad, arrow = cal.parse_quadrant(text), cal.parse_arrow(text)
            if "aktie" in cal.normalize_name(tool) or "stockmap" == cal.normalize_name(tool):
                if quad:
                    _, len_hit = lenient_or(o, lambda d: (stockmap_at(prices, bench, d) or {}).get("quadrant"), quad)
                    mine = (stockmap_at(prices, bench, o.day) or {}).get("quadrant")
                    if mine:
                        out.append(Result("StockMap", "kvadrant", o, quad, mine, mine == quad, len_hit, text))
                if arrow:
                    _, len_hit = lenient_or(o, lambda d: (stockmap_at(prices, bench, d) or {}).get("arrow"), arrow)
                    mine = (stockmap_at(prices, bench, o.day) or {}).get("arrow")
                    if mine:
                        out.append(Result("StockMap", "pil", o, arrow, mine, mine == arrow, len_hit, text))
            if re.search(r"k(ø|oe)bs?signal|simpelt buy|i buy|k(ø|oe)bt efter", text.lower()):
                mode = "state" if re.search(r"i buy|k(ø|oe)bt efter", text.lower()) else "event"

                def has_buy(d, mode=mode):
                    at = stockmap_at(prices, bench, d)
                    return None if at is None else ("køb" if stockmap_signal(at["rot"], d, mode) else "ingen")
                mine, len_hit = lenient_or(o, has_buy, "køb")
                if mine:
                    out.append(Result("StockMap", f"købssignal ({mode})", o, "køb", mine, mine == "køb", len_hit, text))

        elif o.group == "tpi":
            if "lang" in folded_frame and (mss := cal.parse_tpi_long(text)):
                mine, len_hit = lenient_or(o, lambda d: (tpi_at(prices, d) or {}).get("long"), mss)
                if mine:
                    out.append(Result("TPI", "lang trend", o, mss, mine, mine == mss, len_hit, text))
            elif "uge" in folded_frame and "dag" not in folded_frame and (mss := cal.parse_tpi_short(text)):
                mine, len_hit = lenient_or(o, lambda d: (tpi_at(prices, d) or {}).get("short"), mss)
                if mine:
                    out.append(Result("TPI", "uge: oversolgt/overkøbt", o, mss, mine, mine == mss, len_hit, text))

        elif o.group == "mti" and (mss := cal.parse_mti(text)):
            idx_ticker = home_index(o.ticker)
            if idx_ticker not in index_cache:
                index_cache[idx_ticker] = store.prices.get(idx_ticker)
            idx = index_cache[idx_ticker]
            if idx is None:
                idx = bench
            def state(d):
                st = mti_state(upto(prices, d), upto(idx, d))
                return None if st["double_green"] is None else ("dobbelt_gron" if st["double_green"] else "ikke_dobbelt")
            mine, len_hit = lenient_or(o, state, mss)
            if mine:
                out.append(Result("MTI-lite", "dobbelt grøn", o, mss, mine, mine == mss, len_hit, f"{tool}: {text}"))

        elif o.group == "zone" and "gul" not in cal.normalize_name(text) and (mss := cal.parse_tpi_long(text)):
            mine, len_hit = lenient_or(o, lambda d: (tpi_at(prices, d) or {}).get("long"), mss)
            if mine:
                out.append(Result("Zone/trendmodel (2019-21) mod TPI-lang", "grøn/rød", o, mss, mine, mine == mss,
                                  len_hit, f"{tool}: {text}"))

        elif o.group == "sma200" and (mss := cal.parse_sma_side(text)):
            mine = (sma200_at(prices, o.day) or {}).get("side")
            if mine:
                info = sma200_at(prices, o.day)
                _, len_hit = lenient_or(o, lambda d: (sma200_at(prices, d) or {}).get("side"), mss)
                out.append(Result("200-dages gns.", "over/under", o, mss, mine, mine == mss, len_hit,
                                  f"{text}; vores afstand {info['dev']:+.1f} %"))

        elif o.group == "regression" and (mss := cal.parse_regression_class(f"{text} {note}")):
            weekly = "uge" in folded_frame
            at = regression_at(prices, o.day, weekly)
            if at:
                def cls(d):
                    got = regression_at(prices, d, weekly)
                    return None if got is None else got["class"]
                _, len_hit = lenient_or(o, cls, mss)
                recent_hit = mss in at["recent"] or (mss == "inde" and at["class"] == "inde")
                out.append(Result("Regressionskanal", "uden for/inde", o, mss, at["class"], at["class"] == mss,
                                  bool(len_hit or recent_hit), f"{text} ({'uge' if weekly else 'dag'})"))

    return out


def evaluate_value(observations: list[Obs], store: Store, quality: pd.Series | None):
    """P/E-niveauer, billig/dyr-udsagn og Quality-percentiler. Returnerer (Result-liste, P/E-par, quality-par)."""
    out: list[Result] = []
    pe_pairs: list[tuple[Obs, float, float, str]] = []
    q_pairs: list[tuple[Obs, float, float]] = []
    for o in observations:
        row = o.row
        text, tool, frame, note = row["tilstand_eller_vaerdi"], row["vaerktoej"], row["tidsramme"], row["note"]
        pe_hist = store.pe.get(o.ticker)
        past = cal.refers_to_past(text, note)
        if o.group == "pe" and pe_hist is not None and not past and (mss := cal.first_number(text)) and not frame.strip():
            hist = pe_at(pe_hist, o.day)
            if len(hist) and 3 <= mss <= 300:
                pe_pairs.append((o, mss, float(hist.iloc[-1]), "P/E nu"))
        elif o.group == "pe_gennemsnit" and pe_hist is not None and (years := cal.parse_years(frame)) \
                and (mss := cal.first_number(text)) and 3 <= mss <= 300:
            hist = pe_at(pe_hist, o.day)
            if len(hist) and hist.index.min() <= pd.Timestamp(o.day) - pd.DateOffset(years=years - 1):
                window = hist[hist.index > pd.Timestamp(o.day) - pd.DateOffset(years=years)]
                if len(window) >= 100:
                    pe_pairs.append((o, mss, float(window.median()), f"P/E-gns. {years} år"))
        elif o.group == "quality" and quality is not None and (mss := cal.parse_quality_percentile(text)) is not None \
                and o.ticker in quality.index and not np.isnan(quality[o.ticker]):
            q_pairs.append((o, mss, float(quality[o.ticker])))

        # billig/dyr
        looks_value = o.group in ("valuekanal", "pe", "valuescore") or re.search(
            r"\bpe\b|p/e|value|værdi", (tool + " " + text).lower())
        if looks_value and pe_hist is not None and not past and (mss := cal.classify_cheap_expensive(text, note)):
            hist = pe_at(pe_hist, o.day)
            # kræver mindst 3 års P/E-historik før datoen (yfinance har kun ca. 4 års regnskaber uden for USA)
            if len(hist) >= 250 and hist.index.min() <= pd.Timestamp(o.day) - pd.DateOffset(years=3):
                now = float(hist.iloc[-1])
                cands = pe_candidates(pe_hist, o.day, now)
                pos = cal.channel_position(now, cands) if len(cands) >= 3 else None
                pct = cal.percentile_of(now, hist)
                if pos is not None:
                    mine = "dyr" if pos > 0.5 else "billig"
                    out.append(Result("Værdikanal", "billig/dyr (kanalposition)", o, mss, mine, mine == mss, None,
                                      f"{text[:60]}; P/E {now:.1f}, position {pos:.2f}, egen P/E-percentil {pct:.0f}"))
                if pct is not None:
                    mine = "dyr" if pct > 50 else "billig"
                    out.append(Result("Værdikanal", "billig/dyr (P/E-percentil)", o, mss, mine, mine == mss, None,
                                      f"{text[:60]}; P/E {now:.1f}, percentil {pct:.0f}"))
    return out, pe_pairs, q_pairs


# ---------------------------------------------------------------- rapport

def table_md(frame: pd.DataFrame, row_label: str = "MSS \\ vores") -> str:
    cols = list(frame.columns)
    lines = [f"| {row_label} | " + " | ".join(map(str, cols)) + " |", "|---|" + "---|" * len(cols)]
    for idx, row in frame.iterrows():
        lines.append(f"| {idx} | " + " | ".join(str(int(v)) for v in row) + " |")
    return "\n".join(lines)


def summarize(results: list[Result], max_miss: int) -> list[str]:
    lines: list[str] = []
    groups: dict[tuple[str, str], list[Result]] = defaultdict(list)
    for r in results:
        groups[(r.tool, r.kind)].append(r)
    lines += ["## Kategoriske værktøjer", "",
              "| Værktøj | Delmåling | n | Hit | Hit-rate | Lenient* | Tilfældig** | Altid-hyppigste*** | p (mod tilfældig) |",
              "|---|---|---|---|---|---|---|---|---|"]
    details: list[str] = []
    for (tool, kind), items in groups.items():
        pairs = [(str(r.mss), str(r.ours)) for r in items]
        stats = cal.hit_rate(pairs)
        lenient = [r for r in items if r.lenient is not None]
        len_rate = f"{sum(1 for r in lenient if r.lenient) / len(lenient) * 100:.0f} %" if lenient else "–"
        chance = cal.chance_rate(pairs)
        p = cal.binomial_p(stats["hits"], stats["n"], chance / 100) if chance is not None else None
        majority = cal.majority_rate([a for a, _ in pairs])
        lines.append(f"| {tool} | {kind} | {stats['n']} | {stats['hits']} | {stats['rate']:.0f} % | {len_rate} | "
                     f"{chance:.0f} % | {majority:.0f} % | {'–' if p is None else f'{p:.3f}'} |")
        details.append(f"### {tool} – {kind} (n={stats['n']})\n")
        if len({a for a, _ in pairs} | {b for _, b in pairs}) > 1:
            details.append(table_md(cal.confusion(pairs)))
            details.append("")
        misses = [r for r in items if not r.hit][:max_miss]
        if misses:
            details.append("Misses (MSS -> vores):\n")
            for r in misses:
                prec = "" if r.obs.precision == cal.EXACT and not r.obs.uncertain else f" [dato {r.obs.precision}, usikker]"
                details.append(f"- {r.obs.name} ({r.obs.ticker}) {r.obs.day}{prec}: MSS {r.mss}, vores {r.ours}"
                               f"{' – lenient ja' if r.lenient else ''}. {r.detail}")
            details.append("")
    lines += ["", "\\* Lenient: samme kategori på nogen af datoerne ±1–3 uger (kun upræcise datoer) eller, for "
              "regressionskanal, inden for de seneste 2–5 bars.  ** Forventet hit-rate hvis vores kategori var uafhængig "
              "af MSS' med samme fordelinger.  *** Hit-rate ved altid at gætte MSS' hyppigste kategori.", ""]
    return lines + details


def numeric_section(pe_pairs, q_pairs) -> list[str]:
    lines = ["## Numeriske sammenligninger", ""]
    for label in sorted({p[3] for p in pe_pairs}):
        items = [p for p in pe_pairs if p[3] == label]
        ratios = [ours / mss for _, mss, ours, _ in items]
        rho = cal.spearman([p[1] for p in items], [p[2] for p in items])
        within = sum(1 for r in ratios if 0.75 <= r <= 1.25)
        lines.append(f"- **{label}** (n={len(items)}): median vores/MSS = {np.median(ratios):.2f}, inden for ±25 %: "
                     f"{within}/{len(items)}, rangkorrelation {'–' if rho is None else f'{rho:.2f}'}")
        for o, mss, ours, _ in sorted(items, key=lambda p: -abs(np.log(p[2] / p[1])))[:5]:
            lines.append(f"  - størst afvigelse: {o.name} {o.day}: MSS {mss:g}, vores {ours:.1f}")
    if q_pairs:
        mss = [p[1] for p in q_pairs]
        ours = [p[2] for p in q_pairs]
        rho = cal.spearman(mss, ours)
        diff = float(np.mean([abs(a - b) for a, b in zip(mss, ours)]))
        lines += ["", "### Quality-percentil (LØST: vores er dagens universe_factors, MSS' er fra videoens dato)", "",
                  f"n={len(q_pairs)}, rangkorrelation {'–' if rho is None else f'{rho:.2f}'}, gns. afvigelse {diff:.0f} point.", ""]
        for o, a, b in sorted(q_pairs, key=lambda p: -abs(p[1] - p[2]))[:8]:
            lines.append(f"- {o.name} ({o.ticker}) {o.day}: MSS {a:g}, vores {b:.0f}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingen-net", action="store_true", help="brug kun cache i data/cache_b15")
    ap.add_argument("--max-miss", type=int, default=12)
    a = ap.parse_args()
    warnings.filterwarnings("ignore")

    with OBS.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    funnel = Counter(total=len(rows))
    dated = []
    for row in rows:
        resolved = cal.resolve_date(row["dato"], row["video"])
        if resolved:
            dated.append((row, resolved))
    funnel["dato brugbar"] = len(dated)
    prec = Counter(r[1] for _, r in dated)

    companies = [(row, res) for row, res in dated if cal.is_company(row["aktie"])]
    funnel["selskab (ikke portefølje/indeks/land)"] = len(companies)
    names: dict[str, str] = {}
    for row, _ in companies:
        base, _ = cal.clean_name(row["aktie"])
        names.setdefault(cal.normalize_name(base), row["aktie"])
    table = build_map(names, a.ingen_net)

    observations: list[Obs] = []
    unmapped: Counter = Counter()
    unsure: Counter = Counter()
    for row, (day, precision, uncertain) in companies:
        base, hint = cal.clean_name(row["aktie"])
        key = cal.normalize_name(base)
        entry = table.get(key)
        if not entry or not entry["ticker"]:
            unmapped[row["aktie"]] += 1
            continue
        if entry["sikker"] != "ja":
            unsure[f"{row['aktie']} -> {entry['ticker']} ({entry['kilde']})"] += 1
            continue
        group = cal.tool_group(row["vaerktoej"])
        observations.append(Obs(row, day, precision, uncertain, row["aktie"], entry["ticker"], group))
    funnel["med sikker ticker"] = len(observations)

    # kursdata
    tickers = sorted({o.ticker for o in observations})
    extra = {BENCH} | {home_index(t) for t in tickers}
    store = Store()
    with ThreadPoolExecutor(3) as pool:
        for t, frame in zip(sorted(set(tickers) | extra), pool.map(lambda t: get_prices(t, a.ingen_net), sorted(set(tickers) | extra))):
            if frame is not None:
                store.prices[t] = frame
    missing = [t for t in tickers if t not in store.prices]
    # P/E kun for tickers der har P/E- eller billig/dyr-rækker
    pe_tickers = sorted({o.ticker for o in observations if o.group in ("pe", "pe_gennemsnit", "valuekanal", "valuescore")
                         or re.search(r"\bpe\b|p/e|value|værdi", (o.row["vaerktoej"] + " " + o.row["tilstand_eller_vaerdi"]).lower())})
    for t in pe_tickers:
        pe = get_pe(t, a.ingen_net)
        if pe is not None:
            store.pe[t] = pe

    quality = None
    try:
        from stockscanner import universe
        factors = pd.read_csv(ROOT / "data" / "universe_factors.csv", sep=";", encoding="utf-8-sig", index_col="ticker")
        quality = universe.percentiles(factors, factors, by_region=True)["quality"]
    except Exception as exc:  # noqa: BLE001
        print(f"Quality-univers mangler: {exc}", file=sys.stderr)

    results = evaluate(observations, store)
    value_results, pe_pairs, q_pairs = evaluate_value(observations, store, quality)
    results += value_results

    lines = ["# B-15 kørselsrapport (genereret af scripts/calibrate_b15.py)", "", "## Tragt", ""]
    for key, value in funnel.items():
        lines.append(f"- {key}: {value}")
    lines.append(f"- datopræcision (brugbare): {dict(prec)}")
    lines.append(f"- aktier uden kursdata: {missing or 'ingen'}")
    lines.append(f"- uden ticker ({sum(unmapped.values())} rækker): " + "; ".join(f"{k} ×{v}" for k, v in unmapped.most_common()))
    lines.append(f"- usikker ticker, udeladt ({sum(unsure.values())} rækker): " + "; ".join(f"{k} ×{v}" for k, v in unsure.most_common()))
    lines.append("")
    lines += summarize(results, a.max_miss)
    lines += numeric_section(pe_pairs, q_pairs)
    report = "\n".join(lines)
    REPORT.write_text(report, encoding="utf-8")
    with RESULTS.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["vaerktoej", "delmaaling", "aktie", "ticker", "dato", "praecision", "usikker", "mss", "vores", "hit", "lenient", "detalje", "video"])
        for r in results:
            writer.writerow([r.tool, r.kind, r.obs.name, r.obs.ticker, r.obs.day, r.obs.precision, r.obs.uncertain,
                             r.mss, r.ours, r.hit, r.lenient, r.detail, r.obs.row["video"]])
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
