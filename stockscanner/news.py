"""Nyhedsscanner (B-20): overskrifter pr. aktie, vurderet positiv/negativ/neutral af lokal Ollama.

Kilde: Google News RSS (gratis, ingen nøgle; yfinance' nyhedsfeed var tomt 02-11-2026). Google tillader kun
personlig, ikke-kommerciel brug af feedet – derfor kun overskrift, kilde og link, kun for indloggede.
Vurderingen laves lokalt (qwen3.5-9b-gpu); intet sendes til en betalt tjeneste. Vurderingerne caches pr. link
i `data/news_cache.json`, så samme overskrift kun vurderes én gang. Ikke investeringsrådgivning.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / "data" / "news_cache.json"
NAMES_FILE = ROOT / "data" / "news_names.json"
OLLAMA = "http://127.0.0.1:11434"
OLLAMA_EXE = Path(r"C:\LokalAI\Ollama\ollama.exe")
MODEL = "qwen3.5-9b-gpu"
DAYS = 7
MAX_ITEMS = 8
SENTIMENTS = ("positiv", "negativ", "neutral")


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    url: str
    published: str                  # ÅÅÅÅ-MM-DD
    sentiment: str = "uvurderet"    # positiv/negativ/neutral/uvurderet
    impact: int = 0                 # 1 lille, 2 mærkbar, 3 stor betydning for kursen
    reason: str = ""


LOCAL_FEEDS = {".CO": ("da", "DK"), ".ST": ("sv", "SE"), ".OL": ("no", "NO"), ".HE": ("fi", "FI")}
ENGLISH = {"hl": "en-US", "gl": "US", "ceid": "US:en"}


def feed_params(ticker: str) -> dict:
    """Feed på hjemmemarkedets sprog for nordiske aktier, ellers engelsk."""
    for suffix, (language, country) in LOCAL_FEEDS.items():
        if ticker.upper().endswith(suffix):
            return {"hl": language, "gl": country, "ceid": f"{country}:{language}"}
    return ENGLISH


def company_name(ticker: str) -> str:
    """Firmanavn til søgningen (yfinance shortName, cachet); falder tilbage til tickeren."""
    names = _load(NAMES_FILE)
    if ticker in names:
        return clean_name(names[ticker], ticker)
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        name = info.get("shortName") or info.get("longName") or ticker
    except Exception:
        name = ticker
    names[ticker] = str(name)
    _save(NAMES_FILE, names)
    return clean_name(str(name), ticker)


def clean_name(name: str, ticker: str) -> str:
    """Fjern selskabsform og aktieklasse ("Novo Nordisk A/S B" → "Novo Nordisk"), så søgningen rammer."""
    name = re.sub(r"\b(A/S|AB|ASA|Oyj|Inc\.?|Corporation|Corp\.?|N\.V\.|SE|plc|Ltd\.?|Class [A-C])(?=\s|$|,)", "",
                  name)
    name = re.sub(r"\s+[A-Z]$", "", re.sub(r"\s+", " ", name).strip(" ,.-"))  # aktieklasse/GDR-bogstav
    return name.strip(" ,.-") or ticker


def parse_feed(xml_text: str, days: int = DAYS, now: datetime | None = None) -> list[NewsItem]:
    """Overskrifter fra et Google News RSS-feed, nyeste først, kun de seneste `days` dage, uden dubletter."""
    now = now or datetime.now(timezone.utc)
    items, seen = [], set()
    for item in ET.fromstring(xml_text).iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "").strip()
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if not title or not link or published < now - timedelta(days=days):
            continue
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append((published, NewsItem(title, source, link, str(published.date()))))
    return [item for _, item in sorted(items, key=lambda pair: pair[0], reverse=True)]


def fetch_headlines(ticker: str, days: int = DAYS) -> list[NewsItem]:
    query = f'"{company_name(ticker)}" when:{days}d'
    feeds = [feed_params(ticker)] + ([ENGLISH] if feed_params(ticker) != ENGLISH else [])
    for params in feeds:  # lokalt sprog først, engelsk hvis der intet er
        response = requests.get("https://news.google.com/rss/search", params={"q": query, **params},
                                headers={"User-Agent": "Mozilla/5.0 AI-Stock-Scanner"}, timeout=20)
        response.raise_for_status()
        items = parse_feed(response.text, days)[:MAX_ITEMS]
        if items:
            return items
    return []


def ensure_ollama(timeout: int = 20) -> bool:
    """Start Ollama-serveren, hvis den ikke kører (lokalt, gratis). True når den svarer."""
    def alive():
        try:
            return requests.get(OLLAMA + "/api/version", timeout=2).ok
        except requests.RequestException:
            return False

    if alive():
        return True
    if not OLLAMA_EXE.exists():
        return False
    subprocess.Popen([str(OLLAMA_EXE), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(timeout):
        time.sleep(1)
        if alive():
            return True
    return False


def build_prompt(company: str, ticker: str, items: list[NewsItem]) -> str:
    lines = "\n".join(f"{i}. [{item.published}] {item.title} ({item.source})" for i, item in enumerate(items))
    return (
        f"Du vurderer nyhedsoverskrifter for aktien {company} ({ticker}).\n"
        "For hver overskrift: er nyheden sandsynligvis positiv, negativ eller neutral for aktiekursen, "
        "og hvor stor betydning har den (1 = lille, 2 = mærkbar, 3 = stor, fx resultat, opjustering, "
        "nedjustering, opkøb, retssag, myndighedsgodkendelse eller -afslag)? Hvis overskriften ikke handler om "
        "selskabet, så sæt neutral og 1. Opfind intet ud over overskriften. Begrundelse på dansk, højst 15 ord.\n"
        'Svar KUN med JSON: {"vurderinger": [{"nr": 0, "retning": "positiv|negativ|neutral", '
        '"betydning": 1, "begrundelse": "..."}]}\n\n' + lines
    )


def parse_ratings(text: str, count: int) -> dict[int, tuple[str, int, str]]:
    """Ollamas JSON-svar → {nr: (retning, betydning, begrundelse)}; ugyldige rækker springes over."""
    try:
        data = json.loads(text)
    except ValueError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except ValueError:
            return {}
    ratings = {}
    for row in (data.get("vurderinger") if isinstance(data, dict) else None) or []:
        if not isinstance(row, dict):
            continue
        try:
            number, impact = int(row.get("nr")), int(row.get("betydning", 1))
        except (TypeError, ValueError):
            continue
        sentiment = str(row.get("retning", "")).strip().lower()
        if 0 <= number < count and sentiment in SENTIMENTS:
            ratings[number] = (sentiment, min(max(impact, 1), 3), str(row.get("begrundelse", ""))[:160])
    return ratings


def rate(company: str, ticker: str, items: list[NewsItem], model: str = MODEL) -> list[NewsItem]:
    """Vurder overskrifterne; cachede vurderinger genbruges, resten sendes samlet til Ollama."""
    cache = _load(CACHE_FILE)
    rated = [NewsItem(**{**asdict(item), **cache[item.url]}) if item.url in cache else item for item in items]
    todo = [i for i, item in enumerate(rated) if item.sentiment == "uvurderet"]
    if todo and ensure_ollama():
        batch = [rated[i] for i in todo]
        try:
            response = requests.post(OLLAMA + "/api/generate", timeout=300, json={
                "model": model, "prompt": build_prompt(company, ticker, batch), "stream": False,
                "format": "json", "think": False, "options": {"temperature": 0}})
            response.raise_for_status()
            ratings = parse_ratings(str(response.json().get("response") or ""), len(batch))
        except (requests.RequestException, ValueError):
            ratings = {}
        for local, index in enumerate(todo):
            if local in ratings:
                sentiment, impact, reason = ratings[local]
                rated[index] = NewsItem(**{**asdict(rated[index]), "sentiment": sentiment, "impact": impact,
                                           "reason": reason})
                cache[rated[index].url] = {"sentiment": sentiment, "impact": impact, "reason": reason}
        _save(CACHE_FILE, cache)
    return rated


def summary(items: list[NewsItem], today=None, recent_days: int = 3) -> str | None:
    """Kort tekst til mandagslisten, fx "nyheder: 2+ 1−". STOR NEGATIV NYHED (blokerer køb) kun når en stor negativ
    nyhed er ny OG de negative overskrifter er flest – én enkelt negativ vurdering blandt gode nyheder er for usikker
    (testkørsel 02-11-2026: 6 af 10 aktier fik ellers alarm)."""
    if not items:
        return None
    today = today or datetime.now(timezone.utc).date()
    plus = sum(i.sentiment == "positiv" for i in items)
    minus = sum(i.sentiment == "negativ" for i in items)
    text = f"nyheder: {plus}+ {minus}−"
    cutoff = str(today - timedelta(days=recent_days))
    alarm = [i for i in items if i.sentiment == "negativ" and i.impact >= 3 and i.published >= cutoff]
    boost = [i for i in items if i.sentiment == "positiv" and i.impact >= 3 and i.published >= cutoff]
    if alarm and minus > plus:
        text += f"; STOR NEGATIV NYHED: {alarm[0].title[:80]}"
    elif alarm:
        text += f"; stor negativ nyhed (opvejet): {alarm[0].title[:80]}"
    elif boost:
        text += f"; stor positiv nyhed: {boost[0].title[:80]}"
    return text


GPU_QUEUE = Path(r"C:\AI-Movie-Studio\Tools\Studio\gpu_queue.py")


@contextlib.contextmanager
def gpu_turn(label: str):
    """Vent på tur i AI-Movie-Studios fælles GPU-kø (én tung GPU-opgave ad gangen), hvis den findes."""
    if not GPU_QUEUE.exists():
        yield True
        return
    spec = importlib.util.spec_from_file_location("ams_gpu_queue", GPU_QUEUE)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        yield True
        return
    with module.gpu_turn(label, owner="aktie-nyheder") as ok:
        yield ok


def scan(tickers, model: str = MODEL) -> dict[str, list[NewsItem]]:
    """Hent og vurder nyheder for alle tickere; fejl for én aktie stopper ikke de andre."""
    headlines = {}
    for ticker in tickers:
        try:
            headlines[ticker] = fetch_headlines(ticker)
        except Exception:
            headlines[ticker] = []
    result = {}
    with gpu_turn(f"Aktie-nyheder: {len(tickers)} aktier") as ok:
        for ticker, items in headlines.items():
            try:
                result[ticker] = rate(company_name(ticker), ticker, items, model) if items and ok else items
            except Exception:
                result[ticker] = items
        try:  # frigiv grafikkortet, før køen giver turen videre
            requests.post(OLLAMA + "/api/generate", json={"model": model, "keep_alive": 0}, timeout=30)
        except requests.RequestException:
            pass
    return result


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
