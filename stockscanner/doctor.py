"""Lokal diagnose af AI-Stock-Scanner, markeder og Ollama.

Ingen netværkskald medmindre --live eller --ollama er angivet.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from urllib.error import URLError
from urllib.request import urlopen

from stockscanner.markets import SAMPLES, market_of


def inspect_installation(live: bool = False, ollama: bool = False, model: str = "qwen3.5:9b") -> dict:
    deps = ("pandas", "numpy", "requests", "yfinance", "streamlit")
    result: dict = {
        "dependencies": {name: importlib.util.find_spec(name) is not None for name in deps},
        "markets": {},
        "ollama": {"status": "ikke testet"},
    }
    for market, symbols in SAMPLES.items():
        ticker = symbols[0]
        record = {"ticker": ticker, "mapped_market": market_of(ticker), "status": "klar til test"}
        if live:
            try:
                from stockscanner.market_data import fetch_history
                from stockscanner.core import analyze_prices
                prices, currency = fetch_history(ticker)
                scan = analyze_prices(prices, ticker, currency)
                record.update(status="ok", market_date=scan.market_date, currency=scan.currency)
            except Exception as exc:
                record.update(status="fejl", error=str(exc)[:250])
        result["markets"][market] = record
    if ollama:
        try:
            with urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as response:
                payload = json.load(response)
            names = [str(item.get("name", "")) for item in payload.get("models", [])
                     if isinstance(item, dict)]
            result["ollama"] = {
                "status": "ok",
                "models": names,
                "requested_model_installed": model in names,
                "requested_model": model,
            }
        except (OSError, URLError, ValueError, KeyError) as exc:
            result["ollama"] = {"status": "fejl", "error": str(exc)[:250]}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Kontrollér lokalt setup; valgfrit live-data og Ollama")
    parser.add_argument("--live", action="store_true", help="Hent testkurser fra de fem markeder")
    parser.add_argument("--ollama", action="store_true", help="Tjek lokalt Ollama API")
    parser.add_argument("--model", default="qwen3.5:9b")
    args = parser.parse_args()
    data = inspect_installation(args.live, args.ollama, args.model)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    dependencies_ok = all(data["dependencies"].values())
    markets_ok = all(r["status"] == "ok" for r in data["markets"].values()) if args.live else True
    ollama_ok = data["ollama"].get("status") == "ok" if args.ollama else True
    return 0 if dependencies_ok and markets_ok and ollama_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
