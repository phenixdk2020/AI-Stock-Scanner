"""Hjælpere til B-15 "Kalibrér mod facitlisten" (data/mss_video_observations.csv).

Facitlisten er MSS' egne værdier set i videoer. Mange datoer er "ukendt" og aktierne står med
selskabsnavne. Her ligger de små, rene funktioner: dato-udledning, navnerensning, oversættelse af MSS'
danske tilstandstekster til kategorier, datovinduer og hit-rate/forvekslingstabel/rangkorrelation.
Alt er offline og uden look-ahead; selve kørslen ligger i scripts/calibrate_b15.py.
Screening og historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, timedelta
from math import comb

import pandas as pd

# Præcision: "præcis" = fuld dato i rækken, "maaned" = kun år-måned (den 15. bruges),
# "video" = optagelsesdato udledt af videoens titel (fx "13-6-24").
EXACT, MONTH, VIDEO = "præcis", "maaned", "video"

_FULL = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?!\d)")
_MONTH = re.compile(r"^(\d{4})-(\d{2})(?![\d-])")
_TITLE = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})-(\d{2}|\d{4})(?!\d)")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def video_date(title: str) -> date | None:
    """Dato i videoens titel: '13-6-24', '21-01-2026', '4-3-26' (dag-måned-år)."""
    match = _TITLE.search(title or "")
    if not match:
        return None
    day, month, year = int(match[1]), int(match[2]), int(match[3])
    return _safe_date(year + (2000 if year < 100 else 0), month, day)


def resolve_date(raw: str, title: str = "") -> tuple[date, str, bool] | None:
    """(dato, præcision, usikker) ud fra feltet `dato` og videoens titel – eller None.

    Fuld dato bruges som den er (usikker hvis teksten siger 'usikkert'); 'YYYY-MM' bliver den 15. i måneden;
    'optagelsesdato' og 'ukendt' bruger videoens dato fra titlen hvis den findes. Alt andet ('2024
    (usikkert)', '2019-2026 (backtest)', 'ukendt (i dag)', '31. maj (år ukendt)') kasseres.
    """
    text = (raw or "").strip().lower()
    uncertain = "usikkert" in text
    if match := _FULL.match(text):
        got = _safe_date(int(match[1]), int(match[2]), int(match[3]))
        return (got, EXACT, uncertain) if got else None
    if match := _MONTH.match(text):
        got = _safe_date(int(match[1]), int(match[2]), 15)
        return (got, MONTH, uncertain) if got else None
    if text.startswith("optagelsesdato") or text in ("ukendt", "ukendt (usikkert)"):
        got = video_date(title)
        return (got, VIDEO, True) if got else None
    return None


def candidate_dates(day: date, precision: str, uncertain: bool = False) -> list[date]:
    """Datoer der prøves for en observation: selve dagen først, så ±1–3 uger når datoen er upræcis."""
    if precision == EXACT and not uncertain:
        return [day]
    return [day] + [day + timedelta(weeks=k) for k in (-1, 1, -2, 2, -3, 3)]


def normalize_name(name: str) -> str:
    """Små bogstaver uden accenter/tegnsætning – nøgle til navnetabellen."""
    text = (name or "").lower().replace("ø", "o").replace("æ", "ae").replace("å", "a")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9& ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _folded(text: str) -> str:
    """Normaliseret og med 'oe'->'o', 'aa'->'a', så 'grøn' og 'groen' er ens ('gron')."""
    return normalize_name(text).replace("oe", "o").replace("aa", "a")


NOT_A_STOCK = re.compile(
    r"strategi|portef|\(land\)|indeks|index|benchmark|screener|^s&p|^rsp$|^spy|nasdaq|markedet|makro|hedge|"
    r"playbook|mix|algo|fire|ingen aktie|ikke navngivet|^samlet|^alle |^c25|aristocrats|analytikeranbefalinger|"
    r"industrials|etf|^tpi plus|^quality|^value|^stock of the day|^csp|^markeds|^japan|^guld|^metals|^overordnet|"
    r"^skandinav|us educational|^svensk|^land", re.I)


def clean_name(name: str) -> tuple[str, str]:
    """(rent navn, ticker-hint): fjerner parenteser; en parentes med 2–5 store bogstaver
    ('Micron (MU)', 'Quanta Services (PWR)') er et ticker-hint."""
    hint = ""
    for inner in re.findall(r"\(([^)]*)\)", name or ""):
        if re.fullmatch(r"[A-Z]{2,5}", inner.strip()):
            hint = inner.strip()
    base = re.sub(r"\([^)]*\)", "", name or "").strip()
    return base, hint


def is_company(name: str) -> bool:
    """False for porteføljer, strategier, lande, indekser og lignende – ting uden ticker."""
    return bool(name) and not NOT_A_STOCK.search(name)


def tool_group(tool: str) -> str:
    """Samler MSS' mange værktøjsnavne til de grupper vi modellerer."""
    t = _folded(tool)
    if "stockmap" in t:
        return "stockmap"
    if "tpi" in t and not any(w in t for w in ("plus", "screener", "statistik", "setup", "portefolje", "quality")):
        return "tpi"
    if t.startswith("mti") or t in ("timing", "timingzone"):
        return "mti"
    if "regressionskanal" in t and not any(w in t for w in ("stochastics", "stoette", "pejlemaerke", "bund")):
        return "regression"
    if "glidende" in t and "200" in t:
        return "sma200"
    if t in ("p e", "price earning", "pe"):
        return "pe"
    if t == "price earning gennemsnit":
        return "pe_gennemsnit"
    if "value graf" in t or "valuegraf" in t or "value graph" in t or "vaerdikanal" in t:
        return "valuekanal"
    if t in ("quality score", "kvalitet", "kvalitetsscore", "q score"):
        return "quality"
    if t in ("value score", "value"):
        return "valuescore"
    if t in ("trendmodel", "zone", "ugegraf zone", "trend"):
        return "zone"
    return "andet"


def parse_number(text: str) -> float | None:
    """Dansk tal ('78,5', '12.3', '+4,75 %') -> float; None hvis ikke et rent tal."""
    cleaned = (text or "").replace("%", "").replace("pct", "").replace("+", "").strip().replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def first_number(text: str) -> float | None:
    """Første tal i teksten ('100 (top 1 pct. i Danmark)' -> 100); et interval '31-33' / '29 til 42' giver midten."""
    t = (text or "").replace(",", ".")
    rng = re.match(r"^\D*?(\d+(?:\.\d+)?)\s*(?:-|til)\s*(\d+(?:\.\d+)?)", t)
    if rng:
        return (float(rng[1]) + float(rng[2])) / 2
    one = re.search(r"\d+(?:\.\d+)?", t)
    return float(one[0]) if one else None


def parse_years(text: str) -> int | None:
    """'3 aar' / '5 år' / '10 aar' -> 3 / 5 / 10."""
    match = re.match(r"^\s*(\d{1,2})\s*(?:aar|år)\b", (text or "").lower())
    return int(match[1]) if match else None


def parse_quadrant(text: str) -> str | None:
    """MSS' kvadrantfarve -> vores navn (grøn=leading, gul=weakening, rød=lagging, blå=improving)."""
    t = _folded(text)
    for word, quad in (("gron", "leading"), ("gul", "weakening"), ("rod", "lagging"), ("bla", "improving")):
        if re.search(rf"\b{word}\b", t):
            return quad
    return None


def parse_arrow(text: str) -> str | None:
    """'op' / 'ned' ud fra tilstandsteksten ('pil peger nedad', 'begyndt at tippe op')."""
    t = _folded(text)
    if re.search(r"nedad|\bned\b|falder|faldende", t):
        return "ned"
    if re.search(r"tippe op|tipper op|opad|\bop\b|stiger", t):
        return "op"
    return None


def parse_tpi_long(text: str) -> str | None:
    """Lang trend: 'gron'/'rod' (None hvis uklart eller begge dele nævnes)."""
    t = _folded(text)
    green = bool(re.search(r"\bgron|opadgande|opadgaende|optrend", t))
    red = bool(re.search(r"\brod|nedadgande|nedadgaende|nedtrend", t))
    if green == red:
        return None
    return "gron" if green else "rod"


def parse_tpi_short(text: str) -> str | None:
    """Kort tilstand: 'oversolgt' (gul/lysrød akkumulering) eller 'overkobt' (grå); None ellers."""
    t = _folded(text)
    bought = "overkobt" in t
    sold = "oversolgt" in t or "oversolt" in t
    if sold == bought:
        return None
    return "oversolgt" if sold else "overkobt"


def parse_mti(text: str) -> str | None:
    """'dobbelt_gron' (grøn på dag og uge) eller 'ikke_dobbelt' (dobbelt rød / rød); None hvis uklart."""
    t = _folded(text)
    if re.search(r"dobbelt gron|gron pa dag og uge|tredobbelt", t):
        return "dobbelt_gron"
    if re.search(r"dobbelt rod|^rod\b|advarsel", t):
        return "ikke_dobbelt"
    return None


def parse_sma_side(text: str) -> str | None:
    """'over' / 'under' i forhold til glidende gennemsnit; None ved 'brudt' eller uklart."""
    t = _folded(text)
    over = bool(re.search(r"\bover\b", t))
    under = bool(re.search(r"\bunder\b", t))
    if over == under:
        return None
    return "over" if over else "under"


def parse_regression_class(text: str) -> str | None:
    """'under' (brud ned/skudt ud af nederste), 'over' (brud/skud op) eller 'inde' (bounce, tilbage i kanal)."""
    t = _folded(text)
    if re.search(r"ud af nederste|brud ned|nedbrud|ned under", t):
        return "under"
    if re.search(r"skud op|brud op|uden for", t):
        return "over"
    if re.search(r"tilbage i kanal|bounce|ligger godt i kanalen|smal kanal|holdes", t):
        return "inde"
    return None


_CHEAP = re.compile(r"\bbillig|nederste halvdel|nederst i pe|pe bund|\bbla zone")
_EXPENSIVE = re.compile(r"\bdyr|overpriset|priced for perfection|hojt pe|\bhoj\b|\bp e over|p e hojt")


def classify_cheap_expensive(text: str, note: str = "") -> str | None:
    """'billig' eller 'dyr' ud fra MSS' ord om værdiansættelsen; None ved ingen eller modstridende ord."""
    t = _folded(f"{text} {note}")
    cheap, expensive = bool(_CHEAP.search(t)), bool(_EXPENSIVE.search(t))
    if cheap == expensive:
        return None
    return "billig" if cheap else "dyr"


def percentile_of(value: float, series: pd.Series) -> float | None:
    """Placering 0–100 af `value` i `series` (andel under + halvdelen af lige)."""
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return float(((clean < value).sum() + 0.5 * (clean == value).sum()) / len(clean) * 100)


def channel_position(pe_now: float, candidates: list[float]) -> float | None:
    """Position i P/E-kanalen: 0 = bear (billigst), 1 = bull (dyrest); kanalen er min/max af kandidaterne
    (som valuation.value_channel med band_rule='minmax'). None uden spredning."""
    if len(candidates) < 2 or max(candidates) <= min(candidates):
        return None
    low, high = min(candidates), max(candidates)
    return (pe_now - low) / (high - low)


def hit_rate(pairs: list[tuple[str, str]]) -> dict[str, float | int | None]:
    """{'n', 'hits', 'rate'} for (MSS, vores)-par af kategorier."""
    n = len(pairs)
    hits = sum(1 for a, b in pairs if a == b)
    return {"n": n, "hits": hits, "rate": hits / n * 100 if n else None}


def confusion(pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """Forvekslingstabel: række = MSS, kolonne = vores."""
    counts = Counter(pairs)
    rows = sorted({a for a, _ in pairs})
    cols = sorted({b for _, b in pairs})
    return pd.DataFrame([[counts[(a, b)] for b in cols] for a in rows], index=rows, columns=cols)


def majority_rate(labels: list[str]) -> float | None:
    """Træfsikkerhed ved altid at gætte den hyppigste kategori (baseline, 0–100)."""
    return max(Counter(labels).values()) / len(labels) * 100 if labels else None


def spearman(x: list[float | None], y: list[float | None]) -> float | None:
    """Rangkorrelation; None ved færre end 3 par eller konstant række."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    a, b = zip(*pairs)
    if len(set(a)) < 2 or len(set(b)) < 2:
        return None
    value = pd.Series(a).rank().corr(pd.Series(b).rank())
    return None if pd.isna(value) else float(value)


def binomial_p(hits: int, n: int, p0: float) -> float | None:
    """Ensidig p-værdi for mindst `hits` rigtige af `n`, hvis tilfældig træfsikkerhed er `p0` (uden scipy)."""
    if n <= 0:
        return None
    return float(sum(comb(n, k) * p0 ** k * (1 - p0) ** (n - k) for k in range(hits, n + 1)))


def parse_quality_percentile(text: str) -> float | None:
    """MSS' Quality som tal 0–100: '99', '100 (top 1 pct. i Danmark)', 'top femtedel (top 20 procent)' -> 80.
    Små decimaltal som '7,6' (anden skala) og tekst uden tal giver None."""
    t = (text or "").lower().strip()
    if match := re.match(r"^(\d+(?:[.,]\d+)?)(?!\d)", t):
        raw = match[1]
        value = float(raw.replace(",", "."))
        return None if ("," in raw or "." in raw) and value <= 10 else min(value, 100.0)
    if match := re.search(r"top[^0-9]*(\d+)\s*(?:procent|pct)", t):
        return 100.0 - float(match[1])
    return None


def chance_rate(pairs: list[tuple[str, str]]) -> float | None:
    """Forventet træfsikkerhed (0–100) hvis vores kategori var uafhængig af MSS' med samme fordelinger."""
    if not pairs:
        return None
    n = len(pairs)
    a, b = Counter(p[0] for p in pairs), Counter(p[1] for p in pairs)
    return sum(a[c] * b[c] for c in a) / (n * n) * 100


_PAST = re.compile(r"\bsolgt|ved salg|sidste ar|trimmet|\bkobt|tidligere|ved toppen|\bfor \d|siden \d")


def refers_to_past(text: str, note: str = "") -> bool:
    """True hvis udsagnet handler om en tidligere begivenhed ('solgt', 'ved salg', 'sidste år') – så er
    videoens dato ikke datoen for værdien, og rækken kan ikke bruges point-in-time."""
    return bool(_PAST.search(_folded(f"{text} {note}")))
