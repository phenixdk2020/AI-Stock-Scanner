"""Hvorfor er aktien billig, og er det en mulig værdifælde? Kort forklaring skrevet af lokal Ollama.

Modellen får kun faktiske tal (yfinance), listens egne tal og nyhedsoverskrifter, må ikke give kursmål eller
købsråd og skal skrive "ved ikke" hvor data mangler. Tal i svaret, som ikke står i input, fjernes. Samme mønster
som news.py (Ollama lokalt, GPU-kø, cache pr. aktie i 7 dage). Ikke investeringsrådgivning.
"""
from __future__ import annotations

import dataclasses
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from . import news

ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / "data" / "why_cheap_cache.json"
CACHE_DAYS = 7
MAX_PER_RUN = 25
MODEL = news.MODEL
LEVELS = ("lav", "middel", "hoej", "ukendt")
MAX_WHY, MAX_RISK, MAX_RISKS, MAX_BASIS = 300, 100, 3, 160


# ---------------------------------------------------------------- fakta

def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number  # NaN


def _series(frame, labels, limit):
    """Første række i `frame` med et af `labels` → [(dato, værdi)] nyeste først; manglende værdier udelades."""
    for label in labels:
        if label in frame.index:
            out = []
            for column, value in frame.loc[label].items():
                number = _num(value)
                if number is not None:
                    out.append((str(getattr(column, "date", lambda: column)())[:10], number))
            return sorted(out, reverse=True)[:limit]
    return []


def facts_for(ticker: str) -> dict:
    """Gratis tal fra yfinance (mio. i regnskabsvalutaen): omsætning, resultat, bruttomargin, gæld/egenkapital.
    Manglende tal udelades; enhver fejl giver tom dict."""
    try:
        import yfinance as yf

        handle = yf.Ticker(ticker)
        facts = {}
        for key, frame, limit in (("kvartaler", handle.quarterly_income_stmt, 8), ("aar", handle.income_stmt, 4)):
            if frame is None or getattr(frame, "empty", True):
                continue
            revenue = _series(frame, ("Total Revenue", "Operating Revenue"), limit)
            profit = _series(frame, ("Net Income", "Net Income Common Stockholders"), limit)
            gross = dict(_series(frame, ("Gross Profit",), limit))
            if revenue:
                facts[f"omsaetning_{key}_mio"] = [(d, round(v / 1e6)) for d, v in revenue]
            if profit:
                facts[f"resultat_{key}_mio"] = [(d, round(v / 1e6)) for d, v in profit]
            margins = [(d, round(100 * gross[d] / v, 1)) for d, v in revenue if d in gross and v]
            if margins:
                facts[f"bruttomargin_{key}_pct"] = margins
        balance = handle.balance_sheet
        if balance is not None and not getattr(balance, "empty", True):
            debt, equity = _series(balance, ("Total Debt",), 1), _series(balance, ("Stockholders Equity",), 1)
            if debt and equity and equity[0][1] > 0:
                facts["gaeld_til_egenkapital"] = round(debt[0][1] / equity[0][1], 2)
        return facts
    except Exception:
        return {}


# ---------------------------------------------------------------- prompt

def _row_items(row) -> dict:
    if row is None:
        return {}
    if dataclasses.is_dataclass(row) and not isinstance(row, type):
        row = dataclasses.asdict(row)
    elif not isinstance(row, dict):
        row = getattr(row, "__dict__", {})
    return {k: v for k, v in row.items() if isinstance(v, (int, float, str)) and not isinstance(v, bool)
            and v == v and v != ""}


def _data_block(ticker, name, facts, row, analyst, news_items) -> str:
    lines = [f"Aktie: {name} ({ticker})"]
    for key, value in (facts or {}).items():
        shown = " ; ".join(f"{d}: {v}" for d, v in value) if isinstance(value, list) else value
        lines.append(f"{key}: {shown}")
    for key, value in _row_items(row).items():
        lines.append(f"liste.{key}: {value}")
    if analyst is not None:
        for key in ("earnings_date", "revisions", "trap"):
            value = getattr(analyst, key, None)
            if value:
                lines.append(f"analytiker.{key}: {value}")
    for item in news_items or []:
        lines.append(f"overskrift [{item.published}] {item.title} ({item.sentiment})")
    return "\n".join(lines)


def build_prompt(ticker, name, facts, row, analyst, news_items) -> str:
    return (
        f"Du forklarer kort på dansk, hvorfor aktien {name} ({ticker}) er billig, og om det kan være en værdifælde "
        "(billig fordi forretningen forværres).\n"
        "REGLER: Brug KUN tallene og overskrifterne under DATA. Opfind intet. Hvor data mangler, skriv \"ved ikke\". "
        "Giv ALDRIG kursmål, prognose eller købs-/salgsråd. Nævn ingen tal, der ikke står i DATA.\n"
        'Svar KUN med JSON: {"hvorfor_billig": "højst 2 sætninger", "risici": ["højst 3 korte punkter"], '
        '"vaerdifaelde": "lav|middel|hoej|ukendt", "datagrundlag": "kort: hvilke data forklaringen bygger på"}\n\n'
        "DATA:\n" + _data_block(ticker, name, facts, row, analyst, news_items)
    )


# ---------------------------------------------------------------- svar

def parse_answer(text) -> dict | None:
    """Robust JSON-læsning (kodeblok og think-tags fjernes); længder begrænses; ukendt niveau → "ukendt"."""
    if not isinstance(text, str):
        return None
    text = re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.S | re.I).strip()
    text = re.sub(r"```(?:json)?", "", text, flags=re.I)
    data = None
    match = re.search(r"\{.*\}", text, re.S)
    for candidate in (text, match.group(0) if match else None):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            break
        except ValueError:
            continue
    if not isinstance(data, dict):
        return None
    why = " ".join(str(data.get("hvorfor_billig") or "").split())
    if not why:
        return None
    risks = data.get("risici")
    risks = [" ".join(str(r).split())[:MAX_RISK] for r in (risks if isinstance(risks, list) else []) if str(r).strip()]
    level = str(data.get("vaerdifaelde") or "").strip().lower().replace("høj", "hoej")
    return {"hvorfor_billig": why[:MAX_WHY], "risici": risks[:MAX_RISKS],
            "vaerdifaelde": level if level in LEVELS else "ukendt",
            "datagrundlag": " ".join(str(data.get("datagrundlag") or "").split())[:MAX_BASIS]}


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[str]:
    return {m.replace(",", ".") for m in _NUMBER.findall(text)}


def _grounded(text: str, allowed: set[str]) -> bool:
    return _numbers(text) <= allowed


def _strip_invented(answer: dict, data_text: str) -> dict:
    """Fjern sætninger/punkter med tal, der ikke står i input."""
    allowed = _numbers(data_text)
    sentences = re.split(r"(?<=[.!?])\s+", answer["hvorfor_billig"])
    kept = " ".join(s for s in sentences if _grounded(s, allowed))
    removed = kept != answer["hvorfor_billig"] or any(not _grounded(r, allowed) for r in answer["risici"])
    answer = dict(answer, hvorfor_billig=kept or "ved ikke",
                  risici=[r for r in answer["risici"] if _grounded(r, allowed)])
    if not _grounded(answer["datagrundlag"], allowed):
        answer["datagrundlag"] = ""
    if removed:
        answer["datagrundlag"] = (answer["datagrundlag"] + " (tal uden grundlag fjernet)").strip()
    return answer


def explain(ticker, name, row=None, analyst=None, news_items=None, facts=None, model: str = MODEL) -> dict | None:
    """Ét Ollama-kald for én aktie. Kaster aldrig; None når Ollama svigter eller svaret er ugyldigt."""
    try:
        facts = facts_for(ticker) if facts is None else facts
        prompt = build_prompt(ticker, name, facts, row, analyst, news_items)
        response = requests.post(news.OLLAMA + "/api/generate", timeout=300, json={
            "model": model, "prompt": prompt, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0}})
        response.raise_for_status()
        answer = parse_answer(str(response.json().get("response") or ""))
        if answer is None:
            return None
        return _strip_invented(answer, _data_block(ticker, name, facts, row, analyst, news_items))
    except Exception:
        return None


def _fresh(entry, today) -> bool:
    try:
        return today - date.fromisoformat(entry["dato"]) < timedelta(days=CACHE_DAYS)
    except (KeyError, TypeError, ValueError):
        return False


def build(tickers, rows_by_ticker=None, analyst=None, news_items=None, today=None, names=None,
          model: str = MODEL) -> dict:
    """{ticker: {hvorfor_billig, risici, vaerdifaelde, datagrundlag, dato}}. Cache 7 dage pr. ticker; højst
    MAX_PER_RUN nye pr. kørsel (listens rækkefølge). Kaster aldrig; uden Ollama gives det, der ligger i cachen."""
    today = today or datetime.now().date()
    rows_by_ticker, analyst, news_items, names = rows_by_ticker or {}, analyst or {}, news_items or {}, names or {}
    cache = news._load(CACHE_FILE)
    todo = [t for t in tickers if not (isinstance(cache.get(t), dict) and _fresh(cache[t], today))][:MAX_PER_RUN]
    try:
        if todo and news.ensure_ollama():
            with news.gpu_turn(f"Hvorfor billig: {len(todo)} aktier") as ok:
                for ticker in (todo if ok else []):
                    name = names.get(ticker) or _safe_name(ticker)
                    answer = explain(ticker, name, rows_by_ticker.get(ticker), analyst.get(ticker),
                                     news_items.get(ticker), model=model)
                    if answer:
                        cache[ticker] = {**answer, "dato": today.isoformat()}
                try:
                    requests.post(news.OLLAMA + "/api/generate", json={"model": model, "keep_alive": 0}, timeout=30)
                except requests.RequestException:
                    pass
            news._save(CACHE_FILE, cache)
    except Exception:
        pass
    return {t: cache[t] for t in tickers if isinstance(cache.get(t), dict)}


def _safe_name(ticker: str) -> str:
    try:
        return news.company_name(ticker)
    except Exception:
        return ticker
