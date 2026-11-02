"""Byg/opdatér universets faktorer (data/universe_factors.csv). Springer over hvis cachen er under 7 dage
gammel (brug --force for at bygge alligevel). Køres af scripts/mandagsliste.cmd før mandagslisten."""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")  # slutbeskedens pil fejlede i den omdirigerede log (cp1252)

import yfinance as yf

from stockscanner import universe
from stockscanner.market_data import fetch_history
from stockscanner.storage import load_or_fetch_fundamentals

if "--force" not in sys.argv and universe.load(max_age_days=7) is not None:
    print("Universet er under 7 dage gammelt – springer over.")
    sys.exit(0)
tickers = universe.read_tickers()
fx_cache: dict = {}


def fx_to_usd(currency):
    """Live-kurs til USD (cachet pr. kørsel); ellers de omtrentlige kurser i universe.FX_TO_USD."""
    if currency not in fx_cache:
        try:
            pence = currency == "GBp"
            symbol = f"{'GBP' if pence else currency}USD=X"
            rate = 1.0 if currency == "USD" else float(yf.Ticker(symbol).fast_info["last_price"])
            fx_cache[currency] = rate / 100 if pence else rate
        except Exception:
            fx_cache[currency] = universe.FX_TO_USD.get(currency)
    return fx_cache[currency]


# 5 års historik: TPI-lite skal bruge ca. 2,5 år til sin uge-tilstand
frame = universe.build(tickers, load_or_fetch_fundamentals, lambda t: yf.Ticker(t).info or {},
                       lambda t: fetch_history(t, period="5y")[0], fx_to_usd=fx_to_usd)
print(f"Univers: {len(frame)} aktier → {universe.FACTORS_FILE}")
