"""Insiderkøb for amerikanske aktier.

`fetch` bruger Yahoos oversigt over Form 4 via yfinance. SEC afviser hentning af selve dokumenterne uden en
User-Agent med kontaktoplysninger, så `fetch_sec` bruges kun, hvis Allan sætter SEC_USER_AGENT og kobler den på.
Kun køb på det åbne marked på mindst MIN_BUY_USD tæller som køb, og salg tæller som salg; tildeling, optioner,
skat og gaver ignoreres. Yahoo har ingen tal for europæiske aktier.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests

from . import sec_edgar
from .sec_edgar import _cached, _get, cik_for

FOREVER = 36500
MIN_BUY_USD = 10000.0       # småkøb på få hundrede dollars siger intet om ledelsens tro på aktien


def _get_text(url: str) -> str:
    """Som sec_edgar._get, men returnerer rå tekst; deler kaldtælleren (højst 5/sek)."""
    wait = sec_edgar.MIN_INTERVAL - (time.monotonic() - sec_edgar._last_call)
    if wait > 0:
        time.sleep(wait)
    sec_edgar._last_call = time.monotonic()
    response = requests.get(url, headers={"User-Agent": sec_edgar.USER_AGENT, "Accept-Encoding": "gzip"}, timeout=30)
    response.raise_for_status()
    return response.text


def _strip_ns(root: ET.Element) -> None:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _text(el: ET.Element | None, path: str) -> str:
    if el is None:
        return ""
    found = el.find(path)
    return (found.text or "").strip() if found is not None and found.text else ""


def _flag(el: ET.Element | None, path: str) -> bool:
    return _text(el, path).lower() in ("1", "true")


def _num(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def parse_form4(xml_text: str) -> list[dict]:
    """Ikke-derivative transaktioner i et Form 4-dokument.

    Hver: {"owners": [navne], "roles": [...], "code", "date", "shares", "price", "value", "ad"}.
    Samme ejer nævnt flere gange (fælles indlevering) tæller én gang.
    """
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError:
        return []
    _strip_ns(root)
    owners: list[str] = []
    roles: list[str] = []
    for owner in root.findall("reportingOwner"):
        name = _text(owner, "reportingOwnerId/rptOwnerName")
        if name and name.lower() not in [o.lower() for o in owners]:
            owners.append(name)
        rel = owner.find("reportingOwnerRelationship")
        for tag, label in (("isOfficer", "officer"), ("isDirector", "director"), ("isTenPercentOwner", "10%-ejer")):
            if _flag(rel, tag) and label not in roles:
                roles.append(label)
    result = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(tx, "transactionCoding/transactionCode").upper()
        shares = _num(_text(tx, "transactionAmounts/transactionShares/value"))
        price = _num(_text(tx, "transactionAmounts/transactionPricePerShare/value"))
        value = round(shares * price, 2) if shares is not None and price is not None else 0.0
        result.append({
            "owners": list(owners), "roles": list(roles), "code": code,
            "date": _text(tx, "transactionDate/value")[:10],
            "shares": shares, "price": price, "value": value,
            "ad": _text(tx, "transactionAmounts/transactionAcquiredDisposedCode/value").upper(),
        })
    return result


def summarize(transactions: list[dict], today: date, days: int = 90) -> dict:
    """Opsummér køb (P) og salg (S) inden for de seneste `days` dage op til og med today."""
    start = today - timedelta(days=days)
    buyers: set[str] = set()
    buys = sells = 0
    value = 0.0
    last_buy = None
    for tx in transactions:
        try:
            when = date.fromisoformat(str(tx.get("date", ""))[:10])
        except ValueError:
            continue
        if not start <= when <= today:
            continue
        code = tx.get("code")
        if code == "P":
            buys += 1
            value += float(tx.get("value") or 0)
            for name in tx.get("owners") or [tx.get("owner", "?")]:
                buyers.add(str(name).lower())
            if last_buy is None or when.isoformat() > last_buy:
                last_buy = when.isoformat()
        elif code == "S":
            sells += 1
    return {"buyers": len(buyers), "buys": buys, "value_usd": round(value, 2),
            "sells": sells, "last_buy": last_buy, "days": days}


def recent_form4(cik: int, today: date, days: int = 90) -> list[dict]:
    """Form 4-indleveringer de seneste `days` dage: [{accession, filed, doc}]."""
    data = _cached(f"submissions_{cik:010d}.json", lambda: _get(
        f"https://data.sec.gov/submissions/CIK{cik:010d}.json"), max_age_days=1)
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    start = (today - timedelta(days=days)).isoformat()
    out = []
    for i, form in enumerate(forms):
        if form not in ("4", "4/A"):
            continue
        filed = recent["filingDate"][i]
        if filed < start or filed > today.isoformat():
            continue
        out.append({"accession": recent["accessionNumber"][i], "filed": filed,
                    "doc": recent["primaryDocument"][i]})
    return out


def _raw_doc(name: str) -> str:
    """Filnavn uden xsl-visningsmappen (xslF345X05/form4.xml -> form4.xml)."""
    return re.sub(r"^xsl[^/]*/", "", name)


def _accession_transactions(cik: int, filing: dict) -> list[dict]:
    acc = filing["accession"]
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{_raw_doc(filing['doc'])}"
    return _cached(f"form4_{acc}.json", lambda: parse_form4(_get_text(url)), max_age_days=FOREVER)


def _is_foreign(symbol: str) -> bool:
    # børssuffiks (.CO, .L, .DE ...); .A/.B er amerikanske aktieklasser (BRK.B)
    return not symbol or bool(re.search(r"\.[A-Z]{1,3}$", symbol) and not re.search(r"\.[AB]$", symbol))


def from_frame(frame, today: date, days: int = 90) -> dict:
    """Opsummering af yfinance' `insider_transactions`. Købet skal være et køb på markedet (Text "Purchase ...")."""
    transactions = []
    for _, row in frame.iterrows():
        text, value = str(row.get("Text") or ""), row.get("Value")
        value = 0.0 if value is None or value != value else float(value)
        if text.startswith("Purchase") and value >= MIN_BUY_USD:
            code = "P"
        elif text.startswith("Sale"):
            code = "S"
        else:
            continue
        transactions.append({"date": str(row.get("Start Date"))[:10], "code": code, "value": value,
                             "owners": [str(row.get("Insider") or "?")]})
    return summarize(transactions, today, days)


def fetch(ticker: str, today: date, days: int = 90) -> dict | None:
    """Insideropsummering fra Yahoo; None for ikke-USA eller uden data. Fejl må slå igennem til `build`."""
    symbol = ticker.strip().upper()
    if _is_foreign(symbol):
        return None
    import yfinance as yf

    frame = yf.Ticker(symbol).insider_transactions
    if frame is None or getattr(frame, "empty", True):
        return None
    return from_frame(frame, today, days)


def fetch_sec(ticker: str, today: date, days: int = 90) -> dict | None:
    """Som `fetch`, men direkte fra SEC. Kræver SEC_USER_AGENT med kontaktoplysninger."""
    symbol = ticker.strip().upper()
    if _is_foreign(symbol):
        return None
    cik = cik_for(symbol)
    if cik is None:
        return None
    transactions: list[dict] = []
    filings = recent_form4(cik, today, days)
    failed = 0
    for filing in filings:
        try:
            transactions.extend(_accession_transactions(cik, filing))
        except (requests.RequestException, ValueError, KeyError, OSError):
            failed += 1
    if filings and failed == len(filings):
        return None  # alle dokumenter kunne ikke hentes: hellere ingen data end falske nuller
    return summarize(transactions, today, days)


def build(tickers, today: date) -> dict[str, dict]:
    """{ticker: resultat} for dem med resultat; kaster aldrig."""
    out: dict[str, dict] = {}
    try:
        for ticker in tickers:
            try:
                result = fetch(ticker, today)
            except Exception:
                continue
            if result is not None:
                out[ticker] = result
    except Exception:
        pass
    return out
