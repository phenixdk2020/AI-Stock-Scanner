"""Fremadrettet måling af mandagslisterne: hvad skete der med aktierne, efter de kom på listen?

Tallene er dem, listen faktisk viste den dag, så målingen har ingen bagklogskab. En aktie tæller, når den skifter gruppe,
ikke hver uge den bliver stående. Køb regnes til åbningen dagen efter listen, og RSP regnes fra samme dag. Afkast er i
aktiens egen valuta og uden handelsomkostninger. Købsreglerne ændres ikke af målingen.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

HORIZONS = (4, 13, 26)      # uger efter signalet
GROUPS = {"KØB-KANDIDAT": "Entry", "hold øje": "Hold øje", "pil ned": "Pil ned"}
MIN_SIGNALS = 30            # færre afsluttede Entry-signaler end det siger tallene ikke noget
MAX_STALE_DAYS = 7          # en slutkurs må højst være så gammel; helligdage må ikke tælle som manglende data
DETAIL_FILE = Path(__file__).resolve().parent.parent / "data" / "maaling.csv"


def signals(history: pd.DataFrame) -> pd.DataFrame:
    """Første liste pr. aktie pr. uge, og kun de uger hvor aktien skifter gruppe. Ejede aktier er ikke en gruppe."""
    frame = history[["ticker", "dato", "action"]].sort_values("dato", kind="stable").copy()
    frame["uge"] = pd.to_datetime(frame["dato"]).dt.to_period("W-SUN")
    frame = frame.drop_duplicates(["ticker", "uge"], keep="first")
    frame["gruppe"] = frame["action"].map(GROUPS)
    changed = frame["gruppe"].ne(frame.groupby("ticker")["gruppe"].shift())
    return frame[changed & frame["gruppe"].notna()][["ticker", "dato", "gruppe"]].reset_index(drop=True)


def _days(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.dropna(subset=["Open", "Close"]).copy()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    return frame[(frame["Open"] > 0) & (frame["Close"] > 0)].sort_index()


def _last_before(frame: pd.DataFrame, target: pd.Timestamp) -> float | None:
    known = frame[frame.index <= target]
    if known.empty or known.index[-1] < target - pd.Timedelta(days=MAX_STALE_DAYS):
        return None
    return float(known["Close"].iloc[-1])


def outcome(prices: pd.DataFrame, bench: pd.DataFrame, day: str, weeks: int | None = None) -> tuple[float, float] | None:
    """(afkast, RSP) i procent fra åbningen dagen efter `day`; None hvis perioden ikke er slut eller en kurs mangler."""
    stock, market = _days(prices), _days(bench)
    later = stock[stock.index > pd.Timestamp(day)]
    if later.empty or market.empty:
        return None
    start = later.index[0]
    market_later = market[market.index >= start]
    gap = pd.Timedelta(days=MAX_STALE_DAYS)
    if market_later.empty or start - pd.Timestamp(day) > gap or market_later.index[0] - start > gap:
        return None
    target = min(stock.index[-1], market.index[-1]) if weeks is None else start + pd.Timedelta(weeks=weeks)
    if market.index[-1] < target:
        return None
    stock_end, market_end = _last_before(stock, target), _last_before(market, target)
    if stock_end is None or market_end is None or target < start:
        return None
    return (stock_end / float(later["Open"].iloc[0]) - 1) * 100, (market_end / float(market_later["Open"].iloc[0]) - 1) * 100


def details(found: pd.DataFrame, histories: dict, bench: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(målte rækker, signaler hvor perioden er forbi, men en kurs mangler). `horisont` 0 betyder indtil nu."""
    market_last = _days(bench).index[-1]
    rows, missing = [], []
    for signal in found.itertuples(index=False):
        prices = histories.get(signal.ticker)
        for weeks in (None, *HORIZONS):
            result = outcome(prices, bench, signal.dato, weeks) if prices is not None and not prices.empty else None
            label = weeks or 0
            base = {"ticker": signal.ticker, "dato": signal.dato, "gruppe": signal.gruppe, "horisont": label}
            if result is not None:
                rows.append({**base, "afkast": result[0], "rsp": result[1], "forskel": result[0] - result[1]})
            elif pd.Timestamp(signal.dato) + pd.Timedelta(weeks=label, days=MAX_STALE_DAYS) <= market_last:
                missing.append(base)
    columns = ["ticker", "dato", "gruppe", "horisont"]
    return (pd.DataFrame(rows, columns=columns + ["afkast", "rsp", "forskel"]), pd.DataFrame(missing, columns=columns))


def _cell(rows: pd.DataFrame, weeks: int, missing: int) -> dict:
    empty = rows.empty
    return {"uger": weeks, "antal": int(len(rows)), "mangler": int(missing),
            "afkast_pct": None if empty else round(float(rows["afkast"].mean()), 2),
            "rsp_pct": None if empty else round(float(rows["rsp"].mean()), 2),
            "forskel_pp": None if empty else round(float(rows["forskel"].mean()), 2),
            "median_pp": None if empty else round(float(rows["forskel"].median()), 2),
            "slaar_rsp_pct": None if empty else round(float((rows["forskel"] > 0).mean() * 100), 1)}


def summarize(found: pd.DataFrame, measured: pd.DataFrame, missing: pd.DataFrame, history: pd.DataFrame) -> dict:
    groups = []
    for name in GROUPS.values():
        cells = [_cell(measured[(measured["gruppe"] == name) & (measured["horisont"] == weeks)], weeks,
                       int(((missing["gruppe"] == name) & (missing["horisont"] == weeks)).sum()))
                 for weeks in (0, *HORIZONS)]
        groups.append({"gruppe": name, "signaler": int((found["gruppe"] == name).sum()), "perioder": cells})
    first_finished = groups[0]["perioder"][1]["antal"]
    return {"start": str(history["dato"].min()), "lister": int(pd.to_datetime(history["dato"]).dt.to_period("W-SUN").nunique()),
            "grupper": groups, "afsluttede_entry": first_finished, "for_tidligt": first_finished < MIN_SIGNALS}


def measure(history: pd.DataFrame, histories: dict, bench: pd.DataFrame, path: Path = DETAIL_FILE) -> dict:
    """Mål alle signaler, gem rækkerne i `path` (lokalt, kan kontrolleres) og returnér oversigten til siden."""
    found = signals(history)
    measured, missing = details(found, histories, bench)
    measured.round(4).to_csv(path, sep=";", index=False, encoding="utf-8-sig")
    return summarize(found, measured, missing, history)


def run(history_path: Path, histories: dict, bench: pd.DataFrame, fetch, path: Path = DETAIL_FILE) -> dict:
    """Som `measure`, men henter kurser på aktier, der ikke længere er på listen. Et datahul gættes aldrig."""
    history = pd.read_csv(history_path, sep=";", encoding="utf-8-sig")
    prices = dict(histories)
    for ticker in sorted(set(history["ticker"]) - set(prices)):
        try:
            prices[ticker] = fetch(ticker)
        except Exception as error:
            print(f"{ticker}: ingen kurser til målingen – {error}")
    return measure(history, prices, bench, path)


def report(result: dict) -> list[str]:
    """Linjer til konsollen."""
    def text(cell: dict) -> str:
        return f"{cell['forskel_pp']:+.1f} pp (n={cell['antal']})" if cell["antal"] else "– (n=0)"
    lines = [f"Måling siden {result['start']}: {result['lister']} ugelister, forskel mod RSP."]
    for group in result["grupper"]:
        cells = ", ".join(("nu" if c["uger"] == 0 else f"{c['uger']} uger") + " " + text(c) for c in group["perioder"])
        lines.append(f"  {group['gruppe']} ({group['signaler']} signaler): {cells}")
    if result["for_tidligt"]:
        lines.append(f"  Under {MIN_SIGNALS} afsluttede Entry-signaler siger tallene ikke noget endnu.")
    return lines
