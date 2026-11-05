"""Papirportefølje (B-14): mandagslistens køb-kandidater "købes" på papir til lukkekursen, og samme
salgsregler som for ejede aktier lukker dem. Måler fremad, uge for uge, om reglerne virker – uden
look-ahead, fordi hver handel logges den dag, den sker. `data/papir_portefolje.csv` (semikolon).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from stockscanner.portfolio import Position, exit_check

PAPER_FILE = Path(__file__).resolve().parent.parent / "data" / "papir_portefolje.csv"
COLUMNS = ["ticker", "koebsdato", "koebskurs", "salgsdato", "salgskurs", "salgsgrund"]
AMOUNT = 10000.0   # samme beløb pr. papirhandel


def load(path: Path = PAPER_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype={"salgsgrund": str})


def save(frame: pd.DataFrame, path: Path = PAPER_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame[COLUMNS].to_csv(path, sep=";", index=False, encoding="utf-8-sig")


def open_positions(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["salgsdato"].isna() | (frame["salgsdato"].astype(str).str.strip() == "")]


def _last_close(prices: pd.DataFrame) -> float | None:
    close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
    return None if close.empty else float(close.iloc[-1])


def update(frame: pd.DataFrame, rows, histories: dict, today: date) -> tuple[pd.DataFrame, list[str]]:
    """Luk åbne papirhandler hvor en salgsregel rammer, og åbn nye for dagens køb-kandidater.
    `rows`: mandagslistens WeeklyRow'er. Returnerer ny tabel og en liste med beskeder."""
    frame = frame.copy()
    messages = []
    by_ticker = {r.ticker: r for r in rows}
    for index, trade in open_positions(frame).iterrows():
        prices = histories.get(trade["ticker"])
        if prices is None or prices.empty or str(trade["koebsdato"]) >= str(today):
            continue  # aldrig salg samme dag som købet (flere kørsler samme dag)
        row = by_ticker.get(trade["ticker"])
        position = Position(trade["ticker"], 0, float(trade["koebskurs"]), pd.Timestamp(trade["koebsdato"]).date())
        reasons = exit_check(prices, position, row is not None and row.action == "pil ned")
        price = _last_close(prices)
        if reasons and price is not None:
            frame.loc[index, ["salgsdato", "salgskurs", "salgsgrund"]] = [str(today), price, "; ".join(reasons)]
            messages.append(f"PAPIR SALG {trade['ticker']} {price:.2f} ({(price / float(trade['koebskurs']) - 1) * 100:+.1f} %)")
    held = set(open_positions(frame)["ticker"])
    for row in rows:
        if row.action != "KØB-KANDIDAT" or row.ticker in held:
            continue
        price = _last_close(histories.get(row.ticker, pd.DataFrame({"Close": []})))
        if price is None:
            continue
        frame = pd.concat([frame, pd.DataFrame([{"ticker": row.ticker, "koebsdato": str(today), "koebskurs": price}])],
                          ignore_index=True)
        messages.append(f"PAPIR KØB {row.ticker} {price:.2f}")
    return frame.reindex(columns=COLUMNS), messages


SCORE_FILE = Path(__file__).resolve().parent.parent / "data" / "papir_stilling.csv"
SCORE_COLUMNS = ["dato", "antal", "gns_afkast", "gns_rsp", "forskel"]
EARLY_DAYS = 90        # under ca. 3 måneder siger tallene ikke noget
RSP_MAX_GAP_DAYS = 7   # RSP-kursen må højst ligge så mange dage før handelsdatoen (ellers mangler den)


def _day(value) -> pd.Timestamp | None:
    text = str(value).strip()
    if value is None or text in ("", "nan", "NaT", "None"):
        return None
    try:
        stamp = pd.Timestamp(text)
    except (ValueError, TypeError):
        return None
    return None if pd.isna(stamp) else stamp.tz_localize(None).normalize() if stamp.tzinfo else stamp.normalize()


def _rsp_close(close: pd.Series, day: pd.Timestamp | None) -> float | None:
    """RSP's seneste lukkekurs på eller før `day`; None hvis datoen ligger før serien eller serien er for gammel."""
    if day is None:
        return None
    earlier = close[close.index <= day]
    if earlier.empty or (day - earlier.index[-1]).days > RSP_MAX_GAP_DAYS:
        return None
    return float(earlier.iloc[-1])


def score(frame: pd.DataFrame, last_prices: dict[str, float], bench: pd.DataFrame | None,
          today: date | None = None) -> dict:
    """Papirporteføljens stilling mod RSP ud fra handlerne (lige store beløb pr. handel, afkast i aktiens egen valuta).
    Pr. handel: gevinst i % (lukkede til salgskurs, åbne til seneste kurs) og RSP fra købsdato til salgsdato eller
    RSP's seneste kursdato. Handler uden gevinst eller uden RSP-kurs udelades af sammenligningen (`udeladt`);
    intet gættes. Gennemsnit og vinderandel gælder kun de sammenlignede handler."""
    today = today or date.today()
    close = pd.Series(dtype=float)
    if bench is not None and not bench.empty and "Close" in bench.columns:
        close = pd.to_numeric(bench["Close"], errors="coerce").dropna()
        close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
        close = close[~close.index.duplicated(keep="last")].sort_index()
    gains, rsp_gains = [], []
    starts = []
    for _, trade in frame.iterrows():
        start = _day(trade["koebsdato"])
        if start is not None:
            starts.append(start)
        sold = pd.notna(trade["salgskurs"]) and str(trade["salgskurs"]).strip() != ""
        end = float(trade["salgskurs"]) if sold else last_prices.get(trade["ticker"])
        buy = float(trade["koebskurs"]) if pd.notna(trade["koebskurs"]) else None
        if end is None or not buy or buy <= 0 or close.empty:
            continue
        rsp_start = _rsp_close(close, start)
        rsp_end = _rsp_close(close, _day(trade["salgsdato"])) if sold else float(close.iloc[-1])
        if not rsp_start or rsp_end is None:
            continue
        gains.append((float(end) / buy - 1) * 100)
        rsp_gains.append((rsp_end / rsp_start - 1) * 100)
    first = min(starts) if starts else None
    days = None if first is None else (today - first.date()).days
    result = {"antal": len(frame), "sammenlignet": len(gains), "udeladt": len(frame) - len(gains),
              "afkast_pct": None, "rsp_pct": None, "forskel_pp": None, "vinderandel_pct": None, "slaar_rsp_pct": None,
              "start": None if first is None else str(first.date()), "dage": days,
              "for_tidligt": days is None or days < EARLY_DAYS}
    if gains:
        n = len(gains)
        result.update(afkast_pct=sum(gains) / n, rsp_pct=sum(rsp_gains) / n,
                      forskel_pp=sum(gains) / n - sum(rsp_gains) / n,
                      vinderandel_pct=100 * sum(g > 0 for g in gains) / n,
                      slaar_rsp_pct=100 * sum(g > r for g, r in zip(gains, rsp_gains)) / n)
    return result


def log_score(result: dict, today: date, path: Path = SCORE_FILE) -> None:
    """Én linje pr. dato i `data/papir_stilling.csv` (semikolon): dato, antal, gns. afkast, gns. RSP, forskel.
    En kørsel nummer to samme dag erstatter linjen; uden sammenlignede handler står tallene tomme."""
    def cell(value) -> str:
        return "" if value is None else str(round(float(value), 2))

    line = ";".join([str(today), str(int(result.get("antal") or 0)), cell(result.get("afkast_pct")),
                     cell(result.get("rsp_pct")), cell(result.get("forskel_pp"))])
    lines = {}
    if path.exists():
        for old in path.read_text(encoding="utf-8-sig").splitlines()[1:]:
            if old.strip():
                lines[old.split(";")[0]] = old
    lines[str(today)] = line
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([";".join(SCORE_COLUMNS)] + [lines[k] for k in sorted(lines)]) + "\n",
                    encoding="utf-8-sig")


def summary(frame: pd.DataFrame, last_prices: dict[str, float]) -> dict:
    """Afkast pr. handel (lukkede til salgskurs, åbne til seneste kurs) og samlet med samme beløb pr. handel."""
    if frame.empty:
        return {"handler": 0, "aabne": 0, "afkast_pct": None, "gevinst": 0.0, "vundne_pct": None}
    returns = []
    for _, trade in frame.iterrows():
        sold = pd.notna(trade["salgskurs"]) and str(trade["salgskurs"]).strip() != ""
        end = float(trade["salgskurs"]) if sold else last_prices.get(trade["ticker"])
        if end is not None:
            returns.append(end / float(trade["koebskurs"]) - 1)
    if not returns:
        return {"handler": len(frame), "aabne": len(open_positions(frame)), "afkast_pct": None, "gevinst": 0.0,
                "vundne_pct": None}
    mean = sum(returns) / len(returns)
    return {"handler": len(frame), "aabne": len(open_positions(frame)), "afkast_pct": mean * 100,
            "gevinst": sum(returns) * AMOUNT, "vundne_pct": 100 * sum(r > 0 for r in returns) / len(returns)}
