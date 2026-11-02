"""Kør porteføljesimuleringen på universet (data/universe.txt), 2019 → i dag, med urørt periode fra 2024-11."""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import yfinance as yf

from stockscanner import universe
from stockscanner.simulation import buy_and_hold, simulate, weekly_panel

tickers = universe.read_tickers()
data = yf.download(tickers, start="2017-06-01", auto_adjust=True, group_by="ticker", progress=False, threads=True)
histories = {t: data[t].dropna() for t in tickers if t in data.columns.get_level_values(0) and len(data[t].dropna()) > 300}
bench = yf.Ticker("RSP").history(start="2017-06-01", auto_adjust=True)
panel = weekly_panel(histories, bench)
print(f"Aktier med nok historik: {len(panel)} af {len(tickers)}")
variants = {"StockMap alene": {}, "+ MTI-lite": {"require_mti": True}, "+ markedsindeks": {"require_breadth": True},
            "+ MTI + markedsindeks": {"require_mti": True, "require_breadth": True}}
for period, (start, end) in {"hele 2019–2026": ("2019-01-01", None), "udvikling 2019–24": ("2019-01-01", "2024-10-31"),
                             "urørt 2024-11 →": ("2024-11-01", None)}.items():
    rsp = buy_and_hold(bench, start, end)
    print(f"\n[{period}]  RSP køb-og-hold: CAGR {rsp[0]*100:.1f} %, største fald {rsp[1]*100:.1f} %")
    for name, kw in variants.items():
        r = simulate(panel, start, end, max_positions=40, **kw)
        print(f"  {name:<24} CAGR {r.cagr*100:6.1f} %  største fald {r.max_drawdown*100:6.1f} %  handler {len(r.trades):>4}"
              f"  vindere {r.win_rate or 0:4.0f} %")
print("\nMSS oplyser selv (egenrapporteret): ca. 34 % i 2025, største fald ca. 7 %. Kun kursregler – ikke en købsanbefaling.")
