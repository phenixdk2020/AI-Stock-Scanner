"""B-17b: hjælper det at vælge de højeste scorer frem for alfabetisk, og at samle sig om få aktier som Top 10?

Bygger på scripts/study_b17.py og samme cachede data. Samlet er her middel af de forenklede Kvalitet og Værdi; Moat og
værdikanalen findes ikke point-in-time. Omvendt rangering (laveste score først) er kontrol: giver den samme resultat
som rigtig rangering, måler testen tilfældighed og ikke scoren. Historisk test, IKKE en købsanbefaling.
    .venv/Scripts/python scripts/study_b17_rank.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import study_b17 as base  # noqa: E402
from study_b17 import ROOT, block_bootstrap_diff, build_gates, gated_panel, log  # noqa: E402

from stockscanner import universe  # noqa: E402
from stockscanner.simulation import buy_and_hold, simulate, weekly_panel  # noqa: E402

START, HOLDOUT = "2012-01-01", "2024-11-01"


def main() -> None:
    tickers = [t for t in universe.read_tickers() if universe.region(t) == "USA"]
    snaps = {t: s for t in tickers if (s := base.snapshot_for(t)) is not None and not s.empty}
    wanted = sorted(set(snaps) | set(tickers)) + ["RSP"]
    results = [base.prices_for(t) for t in wanted]
    raws = {t: r for t, r in zip(wanted, results) if r is not None and len(r) > 300}
    bench = base.adjusted_frame(raws.pop("RSP"))
    panel = weekly_panel({t: base.adjusted_frame(r) for t, r in raws.items()}, bench)
    weeks = pd.DatetimeIndex(sorted(set().union(*(t.index for t in panel.values()))))
    quality, value, _ = build_gates({t: s for t, s in snaps.items() if t in panel}, raws, weeks)
    log(f"Data klar: {len(panel)} aktier")

    both = (quality >= base.MIN_QUALITY) & (value >= base.MIN_VALUE)
    total = pd.concat([quality.stack(), value.stack()], axis=1).mean(axis=1, skipna=False).unstack().reindex(weeks)
    variants = {   # navn: (krav, rangering, pladser)
        "StockMap, alfabetisk, 40": (None, None, 40),
        "StockMap, Samlet, 40": (None, total, 40),
        "StockMap, Samlet, 10": (None, total, 10),
        "StockMap, omvendt, 10": (None, -total, 10),
        "Begge krav, alfabetisk, 40": (both, None, 40),
        "Begge krav, Samlet, 40": (both, total, 40),
        "Begge krav, alfabetisk, 10": (both, None, 10),
        "Begge krav, Samlet, 10": (both, total, 10),
        "Begge krav, omvendt, 10": (both, -total, 10),
    }
    periods = {"hele": (START, None), "udvikling": (START, "2024-10-31"), "urørt": (HOLDOUT, None)}
    rows, curves = [], {}
    for period, (start, end) in periods.items():
        close = bench["Close"].resample("W-FRI").last().dropna()
        curves[(period, "RSP")] = close[(close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end or "2100-01-01"))]
        cagr, fall = buy_and_hold(bench, start, end)
        rows.append({"periode": period, "variant": "RSP køb-og-hold", "cagr_pct": cagr * 100, "maxdd_pct": fall * 100})
        for name, (gate, rank, slots) in variants.items():
            result = simulate(gated_panel(panel, gate), start, end, max_positions=slots, rank=rank)
            curves[(period, name)] = result.equity
            ci = block_bootstrap_diff(result.equity, curves[(period, "RSP")])
            rows.append({"periode": period, "variant": name, "cagr_pct": result.cagr * 100,
                         "maxdd_pct": result.max_drawdown * 100, "handler": len(result.trades),
                         "vindere_pct": result.win_rate, "gns_handel_pct": result.trades["return_pct"].mean(),
                         "mod_rsp_5pct": None if ci is None else ci[0] * 100, "mod_rsp_95pct": None if ci is None else ci[1] * 100})
            log(f"[{period}] {name}: CAGR {result.cagr*100:.1f} %, fald {result.max_drawdown*100:.1f} %, handler {len(result.trades)}")
    out = ROOT / "data" / "b17b_resultater.csv"
    pd.DataFrame(rows).round(2).to_csv(out, index=False)
    log(f"FÆRDIG: {out}")


if __name__ == "__main__":
    main()
