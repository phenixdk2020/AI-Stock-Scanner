"""Sikker, eksplicit eksport af scannerens *egne scores* til WordPress.

Bemærk datalicens: kør kun rigtige uploads, hvis brugeren har verificeret
retten til at vise afledte markedsdata på den ønskede hjemmeside.
Ingen direkte adgang til Ollama eller lokale filer fra WordPress.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit

import requests

from stockscanner.markets import market_of, instrument_type_of, SUPPORTED_MARKETS
from stockscanner.storage import DB_PATH

ENDPOINT = "/wp-json/ai-stock-scanner/v1/snapshot"
MAX_ROWS = 50


def build_snapshot(db_path: Path = DB_PATH, demo: bool = False) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if demo:
        # Eksempel på udformning, ikke investeringsdata eller aktuelle markedsværdier.
        return {
            "schema_version": 1,
            "generated_at": timestamp,
            "mode": "demo",
            "rows": [
                {"ticker": "NOVO-B.CO", "market": "Danmark", "market_date": "2026-01-15",
                 "score": 70, "signal": "Hold øje"},
                {"ticker": "SAP.DE", "market": "Tyskland", "market_date": "2026-01-15",
                 "score": 60, "signal": "Hold øje"},
            ],
        }
    if not Path(db_path).exists():
        raise ValueError("Ingen scanninger fundet. Kør scan_cli.py først.")
    with closing(sqlite3.connect(db_path)) as conn:  # lukkes eksplicit (Windows holder ellers filen låst)
        rows = conn.execute(
            """SELECT ticker, market_date, score, signal, scanned_at_utc
               FROM scans ORDER BY scanned_at_utc DESC, id DESC"""
        ).fetchall()
    if not rows:
        raise ValueError("Ingen scanninger fundet. Kør scan_cli.py først.")
    latest = []
    seen: set[str] = set()
    # Seneste resultat pr. aktie, dog ikke flere end 50 på WordPress-dashboardet.
    for ticker, market_date, score, signal, scanned_at in rows:
        if ticker in seen:
            continue
        seen.add(ticker)
        market = market_of(str(ticker))
        if market not in SUPPORTED_MARKETS:
            continue
        latest.append({
            "ticker": str(ticker),
            "market": market,
            "instrument_type": instrument_type_of(str(ticker)),
            "market_date": str(market_date),
            "score": int(score),
            "signal": str(signal),
        })
        if len(latest) == MAX_ROWS:
            break
    if not latest:
        raise ValueError("Ingen gyldige aktier fra de ni markeder i lokal SQLite.")
    return {"schema_version": 1, "generated_at": timestamp, "mode": "research", "rows": latest}


SIGNALS = {"KØB-KANDIDAT": "Interessant", "hold øje": "Hold øje"}    # alt andet = Afvent


def snapshot_from_rows(rows, market_dates: dict) -> dict:
    """Aktiescanner-siden fra mandagslisten: købskandidater først, så højeste MSS-score, højst 50.
    Aktier uden score eller uden for de ni markeder udelades (der gættes ikke på en score)."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    latest = []
    for row in sorted(rows, key=lambda r: (r.action != "KØB-KANDIDAT", -(r.mss_score or 0))):
        market = market_of(row.ticker)
        if market not in SUPPORTED_MARKETS or row.mss_score is None or row.ticker not in market_dates:
            continue
        latest.append({
            "ticker": row.ticker,
            "market": market,
            "instrument_type": instrument_type_of(row.ticker),
            "market_date": str(market_dates[row.ticker]),
            "score": max(0, min(100, round(row.mss_score))),
            "signal": SIGNALS.get(row.action, "Afvent"),
        })
    if not latest:
        raise ValueError("Mandagslisten har ingen aktier med score på de ni markeder.")
    return {"schema_version": 1, "generated_at": timestamp, "mode": "research", "rows": latest[:MAX_ROWS]}


def make_endpoint(site_url: str) -> str:
    site_url = site_url.rstrip("/")
    parsed = urlsplit(site_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("WordPress-adressen skal bruge HTTPS og må ikke indeholde login.")
    if parsed.query or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError("Uventet query, fragment eller port i WordPress-adressen.")
    return site_url + ENDPOINT


RETRY_WAITS = (5, 15, 45)   # sekunder; webhotellet afbrød tilfældigt ca. hver 3. forbindelse (03-11-2026)


def _retrying(method):
    """Prøv igen ved afbrudt forbindelse (ikke ved et svar fra WordPress – det afgør kalderen)."""
    def call(*args, **kwargs):
        for wait in (*RETRY_WAITS, None):
            try:
                return method(*args, **kwargs)
            except (requests.ConnectionError, requests.Timeout):
                if wait is None:
                    raise
                time.sleep(wait)
    return call


def _post_or_get_with_auth(
    url: str, username: str, app_password: str, *, payload: dict | None = None
) -> requests.Response:
    """Try standard Basic first; retry a 401 via plugin-scoped custom header.

    The fallback solves webhosts stripping the normal Authorization header.
    Both attempts are HTTPS-only and never follow redirects; no credentials
    are placed in URLs, query parameters, or payloads.
    """
    if not username.strip() or not app_password.strip():
        raise ValueError("WordPress-brugernavn og Application Password mangler.")
    if urlsplit(url).scheme != "https":
        raise ValueError("WordPress kræver HTTPS.")

    common = {
        "timeout": (30, 120),  # playbook-snapshottet kan være flere hundrede KB
        "allow_redirects": False,
        "headers": {"User-Agent": "AI-Stock-Scanner/1.3"},
    }
    method = _retrying(requests.post if payload is not None else requests.get)
    args = {"json": payload} if payload is not None else {}
    response = method(url, auth=(username, app_password), **common, **args)
    if response.status_code == 401:
        # WordPress validates the same Application Password with its own core
        # function. Only the AI Stock Scanner endpoint accepts this header.
        credentials = base64.b64encode(
            (username + ":" + app_password).encode("utf-8")
        ).decode("ascii")
        response = method(
            url,
            headers={**common["headers"], "X-ASC-Authorization": "Basic " + credentials},
            timeout=common["timeout"],
            allow_redirects=False,
            **args,
        )
    return response


def _wordpress_error(response: requests.Response) -> str:
    try:
        error = response.json()
    except ValueError:
        error = None
    if isinstance(error, dict):
        code = str(error.get("code") or "")
        message = str(error.get("message") or "")
        if code:
            return f"HTTP {response.status_code}: {code} – {message[:220]}"
    return f"HTTP {response.status_code} (ingen WordPress-fejlkode)"


def send_snapshot(payload: dict, site_url: str, username: str, app_password: str) -> dict:
    endpoint = make_endpoint(site_url)
    response = _post_or_get_with_auth(
        endpoint, username, app_password, payload=payload
    )
    if response.status_code != 200:
        raise RuntimeError("WordPress afviste overførslen: " + _wordpress_error(response))
    data = response.json()
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError("WordPress returnerede ikke en gyldig kvittering.")
    return data


def _api(site_url: str, route: str) -> str:
    return make_endpoint(site_url).removesuffix("/snapshot") + route


def credentials() -> tuple[str, str, str] | None:
    """(adresse, bruger, Application Password) fra miljøvariablerne, eller None hvis noget mangler."""
    values = tuple(os.environ.get(name, "").strip() for name in ("ASC_WP_SITE_URL", "ASC_WP_USER", "ASC_WP_APP_PASSWORD"))
    return values if all(values) else None


def fetch_tickers(site_url: str, username: str, app_password: str) -> list[str]:
    """Tickere som brugerne på hjemmesiden følger eller ejer (plugin ≥ 0.6.0)."""
    response = _post_or_get_with_auth(_api(site_url, "/tickers"), username, app_password)
    if response.status_code != 200:
        raise RuntimeError("Kunne ikke hente hjemmesidens tickere: " + _wordpress_error(response))
    data = response.json()
    tickers = data.get("tickers") if isinstance(data, dict) else None
    if not isinstance(tickers, list):
        raise RuntimeError("WordPress returnerede en uventet tickerliste.")
    return [str(t) for t in tickers if isinstance(t, str) and t.strip()]


def send_playbook(payload: dict, site_url: str, username: str, app_password: str) -> dict:
    """Send playbook-snapshot (schema 2, docs/PLAYBOOK-SNAPSHOT.md) til hjemmesiden."""
    response = _post_or_get_with_auth(_api(site_url, "/playbook"), username, app_password, payload=payload)
    if response.status_code != 200:
        raise RuntimeError("WordPress afviste playbook-snapshottet: " + _wordpress_error(response))
    data = response.json()
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError("WordPress returnerede ikke en gyldig kvittering.")
    return data


def check_auth(site_url: str, username: str, app_password: str) -> dict:
    """Authenticate against the scanner endpoint without sending stock data."""
    url = make_endpoint(site_url).removesuffix("/snapshot") + "/auth-check"
    response = _post_or_get_with_auth(url, username, app_password)
    if response.status_code != 200:
        raise RuntimeError("Godkendelsestesten mislykkedes: " + _wordpress_error(response))
    data = response.json()
    if not isinstance(data, dict) or data.get("authenticated") is not True:
        raise RuntimeError("WordPress returnerede en uventet godkendelseskvittering.")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Eksport af researchresultater til WordPress")
    parser.add_argument("--demo", action="store_true", help="Send kun tydeligt mærkede eksempelresultater")
    parser.add_argument("--check-auth", action="store_true",
                        help="Kontroller API-godkendelse uden at sende aktiedata")
    parser.add_argument("--preview", action="store_true", help="Vis JSON lokalt uden at sende")
    parser.add_argument("--confirm-data-rights", action="store_true",
                        help="Bekræft at du har ret til at publicere de afledte markedsdata")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    if not args.demo and not args.preview and not args.check_auth and not args.confirm_data_rights:
        parser.error("Rigtige uploads kræver --confirm-data-rights efter gennemgang af datalicens.")
    try:
        if args.check_auth:
            info = check_auth(
                os.environ.get("ASC_WP_SITE_URL", ""),
                os.environ.get("ASC_WP_USER", ""),
                os.environ.get("ASC_WP_APP_PASSWORD", ""),
            )
            print(json.dumps(info, ensure_ascii=False))
            return 0
        payload = build_snapshot(args.db, demo=args.demo)
        if args.preview:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            receipt = send_snapshot(
                payload,
                os.environ.get("ASC_WP_SITE_URL", ""),
                os.environ.get("ASC_WP_USER", ""),
                os.environ.get("ASC_WP_APP_PASSWORD", ""),
            )
            print(json.dumps(receipt, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, requests.RequestException, sqlite3.Error) as exc:
        print("Fejl: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
