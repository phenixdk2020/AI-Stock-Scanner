"""Byg/opdatér universets faktorer (data/universe_factors.csv). Springer over hvis cachen er under 7 dage
gammel (brug --force for at bygge alligevel). Køres af scripts/mandagsliste.cmd før mandagslisten."""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import yfinance as yf

from stockscanner import universe
from stockscanner.market_data import fetch_history
from stockscanner.storage import load_or_fetch_fundamentals

if "--force" not in sys.argv and universe.load(max_age_days=7) is not None:
    print("Universet er under 7 dage gammelt – springer over.")
    sys.exit(0)
tickers = universe.read_tickers()
frame = universe.build(tickers, load_or_fetch_fundamentals, lambda t: yf.Ticker(t).info or {},
                       lambda t: fetch_history(t, period="2y")[0])
print(f"Univers: {len(frame)} aktier → {universe.FACTORS_FILE}")
