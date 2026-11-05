"""B-17: ærlig backtest af Entry-kæden for amerikanske aktier med point-in-time fundamentaldata fra SEC.

Spørgsmål: giver "kvalitet + værdi + StockMap-køb" mere end "StockMap-køb alene" og mere end RSP?
Samme simulate() som scripts/simulate_portfolio.py (40 lige store positioner, salg ved Supertrend x3-vending eller
StockMap-salg, 0,1 % pr. handel, køb næste åbning). Filtrene lægges kun på KØB-signalet (salgsreglerne er uændrede).
Fundamentale tal tæller først dagen efter deres `filed`-dato. Kørsel (genoptagelig, cache i data/sec og data/cache_b17):
    .venv/Scripts/python scripts/study_b17.py [--start 2012-01-01] [--urort 2024-11-01] [--max N]
Historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import argparse
import json
import pickle
import shutil
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from stockscanner import pit_fundamentals as pit  # noqa: E402
from stockscanner import sec_edgar, universe  # noqa: E402
from stockscanner.simulation import buy_and_hold, simulate, weekly_panel  # noqa: E402

CACHE = ROOT / "data" / "cache_b17"
MIN_FREE_GB = 20
MAX_POSITIONS = 40
MIN_QUALITY, MIN_VALUE = 60.0, 50.0
PRICE_START = "2007-01-01"


def log(message: str) -> None:
    print(time.strftime("%H:%M:%S"), message, flush=True)


def check_disk() -> None:
    free = shutil.disk_usage("C:/").free / 1e9
    log(f"Ledig plads på C: {free:.1f} GB")
    if free < MIN_FREE_GB:
        sys.exit(f"STOP: under {MIN_FREE_GB} GB fri på C: ({free:.1f} GB).")


# --- 1. SEC-facts -------------------------------------------------------------------------------------------------
def snapshot_for(ticker: str) -> pd.DataFrame | None:
    """Nøgletals-snapshots (pr. filed-dato) for én ticker; cachet. None hvis selskabet ikke findes i SEC/us-gaap."""
    CACHE.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace("/", "_")
    snap_file, none_file = CACHE / f"snap_{safe}.pkl", CACHE / f"snap_{safe}.none"
    if snap_file.exists():
        return pickle.loads(snap_file.read_bytes())
    if none_file.exists():
        return None
    try:
        cik = sec_edgar.cik_for(ticker)
        if cik is None:
            none_file.write_text("ingen CIK")
            return None
        facts = sec_edgar._cached(f"facts_{cik:010d}.json", lambda: sec_edgar._get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"), max_age_days=60)
    except Exception as error:  # 404 for selskaber uden companyfacts mv.; prøves igen ved næste kørsel hvis netværksfejl
        if "404" in str(error):
            none_file.write_text(str(error))
        log(f"  {ticker}: facts fejlede ({str(error)[:80]})")
        return None
    table = pit.facts_table(facts)
    if table.empty:
        none_file.write_text("ingen us-gaap-tal")
        return None
    snap = pit.snapshots(table, since="2008-01-01")
    snap_file.write_bytes(pickle.dumps(snap))
    return snap


# --- 2. Kurser ----------------------------------------------------------------------------------------------------
def prices_for(ticker: str) -> pd.DataFrame | None:
    """Dagskurser med rå Close (kun splitjusteret), Adj Close og splits; cachet pr. ticker."""
    import yfinance as yf

    CACHE.mkdir(parents=True, exist_ok=True)
    file = CACHE / f"px_{ticker.replace('^', '_')}.pkl"
    if file.exists():
        return pickle.loads(file.read_bytes())
    for wait in (5, 20, None):
        try:
            frame = yf.Ticker(ticker).history(start=PRICE_START, auto_adjust=False, actions=True)
        except Exception:
            frame = None
        if frame is not None and not frame.empty:
            break
        if wait is None:
            return None
        time.sleep(wait)
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize() if frame.index.tz is not None \
        else pd.DatetimeIndex(frame.index).normalize()
    file.write_bytes(pickle.dumps(frame))
    return frame


def adjusted_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """O/H/L/C justeret for split og udbytte (som auto_adjust=True)."""
    factor = (raw["Adj Close"] / raw["Close"]).replace([np.inf, -np.inf], np.nan).ffill().bfill()
    frame = raw[["Open", "High", "Low", "Close"]].mul(factor, axis=0)
    return frame.dropna()


# --- 3. Gates -----------------------------------------------------------------------------------------------------
def eps_split_adjusted(m: pd.DataFrame, splits: pd.Series) -> pd.Series:
    """TTM-EPS i dagens aktieenheder: del med splits, der skete efter snapshot'ets filed-dato (ren enhedsomregning)."""
    splits = splits[(splits > 0) & (splits != 1)]
    if splits.empty:
        return m["eps_ttm"]
    ratio_after = pd.Series(1.0, index=m.index)
    for when, ratio in splits.items():
        ratio_after = ratio_after.where(~(m["snap_date"] < when), ratio_after * ratio)
    return m["eps_ttm"] / ratio_after


def build_gates(snaps: dict[str, pd.DataFrame], raws: dict[str, pd.DataFrame], weeks: pd.DatetimeIndex):
    metric_tables = {key: {} for key in pit.METRICS}
    value = {}
    for ticker, snap in snaps.items():
        raw = raws.get(ticker)
        if raw is None:
            continue
        m = pit.at_dates(snap, weeks)
        for key in pit.METRICS:
            metric_tables[key][ticker] = pd.to_numeric(m[key], errors="coerce")
        price = raw["Close"][~raw.index.duplicated(keep="last")].reindex(weeks, method="ffill", tolerance=pd.Timedelta(days=6))
        splits = raw["Stock Splits"] if "Stock Splits" in raw else pd.Series(dtype=float)
        eps = eps_split_adjusted(m.assign(eps_ttm=pd.to_numeric(m["eps_ttm"], errors="coerce")), splits[splits != 0])
        value[ticker] = pit.value_score(price, eps)
    tables = {k: pd.DataFrame(v).reindex(weeks) for k, v in metric_tables.items()}
    quality = pit.quality_percentile(tables)
    return quality, pd.DataFrame(value).reindex(weeks), tables


def gated_panel(panel: dict[str, pd.DataFrame], gate: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    if gate is None:
        return panel
    out = {}
    for ticker, table in panel.items():
        table = table.copy()
        if ticker in gate.columns:
            table["buy"] = table["buy"] & gate[ticker].reindex(table.index).fillna(False).to_numpy(dtype=bool)
        else:
            table["buy"] = False
        out[ticker] = table
    return out


# --- 4. Måltal ----------------------------------------------------------------------------------------------------
def avg_exposure(equity: pd.Series, trades: pd.DataFrame) -> float | None:
    """Gns. andel af de 40 pladser, der var fyldt (kun lukkede handler; åbne ved slutningen tælles ikke)."""
    if trades.empty:
        return None
    buys, sells = trades["buy_week"].to_numpy(), trades["sell_week"].to_numpy()
    counts = [int(((buys <= w) & (sells > w)).sum()) for w in equity.index.to_numpy()]
    return float(np.mean(counts)) / MAX_POSITIONS


def block_bootstrap_diff(a: pd.Series, b: pd.Series, block: int = 13, reps: int = 2000, seed: int = 17):
    """90 %-interval for forskel i årlig vækst (a − b) ved blok-bootstrap af ugentlige afkast; None hvis for få uger."""
    ra = a.pct_change().dropna()
    rb = b.reindex(a.index).ffill().pct_change().dropna()
    both = pd.concat([ra, rb], axis=1).dropna().to_numpy()
    n = len(both)
    if n < 3 * block:
        return None
    rng = np.random.default_rng(seed)
    starts_max = n - block
    diffs = []
    for _ in range(reps):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.integers(0, starts_max + 1, size=int(np.ceil(n / block)))])[:n]
        sample = both[idx]
        years = n / 52
        diffs.append(np.prod(1 + sample[:, 0]) ** (1 / years) - np.prod(1 + sample[:, 1]) ** (1 / years))
    return float(np.percentile(diffs, 5)), float(np.percentile(diffs, 95))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--urort", default="2024-11-01")
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()
    check_disk()
    tickers = [t for t in universe.read_tickers() if universe.region(t) == "USA"]
    if args.max:
        tickers = tickers[:args.max]
    log(f"Amerikanske tickers i universet: {len(tickers)}")

    # 1. facts (sekventielt, højst 5 kald/sek via sec_edgar.MIN_INTERVAL)
    snaps = {}
    for i, ticker in enumerate(tickers, 1):
        snap = snapshot_for(ticker)
        if snap is not None and not snap.empty:
            snaps[ticker] = snap
        if i % 50 == 0:
            log(f"SEC-facts {i}/{len(tickers)}; med tal: {len(snaps)}")
        if i % 200 == 0:
            check_disk()
    log(f"SEC-facts færdige: {len(snaps)} af {len(tickers)} tickers har US-GAAP-tal")

    # 2. kurser
    wanted = sorted(set(snaps) | set(tickers)) + ["RSP"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(prices_for, wanted))
    raws = {t: r for t, r in zip(wanted, results) if r is not None and len(r) > 300}
    log(f"Kurser hentet for {len(raws)} af {len(wanted)}")
    bench_raw = raws.pop("RSP")
    bench = adjusted_frame(bench_raw)
    histories = {t: adjusted_frame(r) for t, r in raws.items()}
    panel = weekly_panel(histories, bench)
    log(f"Ugepanel: {len(panel)} aktier")

    # 3. gates
    weeks = pd.DatetimeIndex(sorted(set().union(*(t.index for t in panel.values()))))
    quality, value, tables = build_gates({t: s for t, s in snaps.items() if t in panel}, raws, weeks)
    q_ok, v_ok = quality >= MIN_QUALITY, value >= MIN_VALUE
    variants = {
        "StockMap alene": None,
        "+ Kvalitet >= 60": q_ok,
        "+ Værdi >= 50": v_ok,
        "+ begge": q_ok & v_ok,
    }
    coverage = pd.DataFrame({"med Quality": quality.notna().sum(axis=1), "med Value": value.notna().sum(axis=1),
                             "Quality >= 60": q_ok.sum(axis=1), "Value >= 50": v_ok.sum(axis=1)})
    cov_year = coverage.groupby(coverage.index.year).median().astype(int)

    periods = {"hele": (args.start, None), "udvikling": (args.start, str(pd.Timestamp(args.urort) - pd.Timedelta(days=1))[:10]),
               "urørt": (args.urort, None)}
    rows, equities = [], {}
    for pname, (start, end) in periods.items():
        rsp = buy_and_hold(bench, start, end)
        close = bench_close = adjusted_frame(bench_raw)["Close"].resample("W-FRI").last().dropna()
        close = close[(close.index >= pd.Timestamp(start)) & ((close.index <= pd.Timestamp(end)) if end else True)]
        equities[(pname, "RSP køb-og-hold")] = close
        rows.append({"periode": pname, "variant": "RSP køb-og-hold", "cagr_pct": rsp[0] * 100, "maxdd_pct": rsp[1] * 100,
                     "handler": None, "vindere_pct": None, "gns_handel_pct": None, "signaler": None, "fyldte_pladser_pct": None})
        for vname, gate in variants.items():
            gp = gated_panel(panel, gate)
            result = simulate(gp, start, end, max_positions=MAX_POSITIONS)
            in_period = lambda t: (t.index >= pd.Timestamp(start)) & ((t.index <= pd.Timestamp(end)) if end else True)
            signals = int(sum(t["buy"][in_period(t)].sum() for t in gp.values()))
            exposure = avg_exposure(result.equity, result.trades)
            equities[(pname, vname)] = result.equity
            rows.append({"periode": pname, "variant": vname, "cagr_pct": result.cagr * 100, "maxdd_pct": result.max_drawdown * 100,
                         "handler": len(result.trades), "vindere_pct": result.win_rate,
                         "gns_handel_pct": float(result.trades["return_pct"].mean()) if len(result.trades) else None,
                         "signaler": signals, "fyldte_pladser_pct": None if exposure is None else exposure * 100})
            log(f"[{pname}] {vname}: CAGR {result.cagr*100:.1f} %, fald {result.max_drawdown*100:.1f} %, handler {len(result.trades)}")
    frame = pd.DataFrame(rows)
    out_csv = ROOT / "data" / "b17_resultater.csv"
    frame.round(2).to_csv(out_csv, index=False)
    log(f"Skrev {out_csv}")

    # usikkerhed: blok-bootstrap af ugentlige afkast
    boots = []
    for pname in ("hele", "urørt"):
        for vname in list(variants)[1:]:
            base = equities[(pname, "StockMap alene")]
            boots.append((pname, vname, "mod StockMap alene", block_bootstrap_diff(equities[(pname, vname)], base)))
        for vname in list(variants):
            boots.append((pname, vname, "mod RSP", block_bootstrap_diff(equities[(pname, vname)], equities[(pname, "RSP køb-og-hold")])))

    write_report(args, frame, boots, cov_year, len(tickers), len(snaps), len(panel), weeks)
    log("FÆRDIG")


def fmt(value, digits=1, suffix=""):
    return "–" if value is None or (isinstance(value, float) and np.isnan(value)) else f"{value:.{digits}f}{suffix}"


def write_report(args, frame, boots, cov_year, n_universe, n_facts, n_panel, weeks) -> None:
    labels = {"hele": f"Hele perioden {args.start[:4]} → i dag", "udvikling": f"Udvikling {args.start[:4]} → {args.urort[:7]}",
              "urørt": f"Urørt {args.urort[:7]} → i dag"}
    lines = ["# B-17: Entry-kæden med point-in-time fundamentaldata (USA)", "",
             f"Genereret af `scripts/study_b17.py` {time.strftime('%Y-%m-%d %H:%M')}. Rå tal: `data/b17_resultater.csv`. "
             "Historisk test, IKKE en købsanbefaling.", "",
             "**Spørgsmål:** Giver StockMap-køb + Kvalitet + Værdi mere end StockMap-køb alene, og mere end RSP (køb og hold)?", "",
             "## Opsætning", "",
             f"- Univers: de amerikanske tickers i `data/universe.txt` (uden børssuffiks): {n_universe}; {n_facts} har US-GAAP-tal hos SEC; "
             f"{n_panel} har nok kurshistorik til ugepanelet. Kun aktier, der findes i dag.",
             "- Samme `simulate()` som `scripts/simulate_portfolio.py`: højst 40 lige store positioner, køb ugen efter KØB-signalet "
             "(næste åbning), salg ved Supertrend x3-vending eller StockMap-salg, 0,1 % pr. handel. Filtrene lægges kun på købet; "
             "salgsreglerne er uændrede. Ledig kontant står stille (ingen rente).",
             "- Fundamentale tal: SEC companyfacts, hver værdi med `filed`-dato (`stockscanner/pit_fundamentals.py`). På en given uge "
             "bruges kun tal indleveret senest dagen før ugens lukning, og for hver periode den senest indleverede version "
             "(omarbejdede tal tæller først fra deres egen `filed`-dato).",
             "- Kvalitet (forenklet): percentil i tværsnittet pr. uge af ROE, ROA, bruttomargin, rentedækning, omsætningsvækst og "
             "(omvendt) gæld/egenkapital; middelværdien rangeres igen; kræver mindst halvdelen af nøgletallene og mindst 50 aktier "
             "på datoen. Krav: >= 60.",
             "- Værdi (forenklet): aktiens P/E (kurs / TTM-EPS, EPS splitomregnet) mod aktiens egen P/E-historik til og med ugen "
             "(højst 10 år, mindst 3 år): andel af tidligere uger med højere P/E. Krav: >= 50 (P/E på eller under egen median).",
             "- **Begge scorer er tilnærmelser af de rigtige (`quality_rank.py`, værdikanalen i `valuation.py`), ikke samme formel.** "
             "Værdikanalens PEG-, asymmetri-, regnskabs- og estimatkrav fra mandagslisten indgår ikke.", "",
             "## Resultater", ""]
    for pname in ("hele", "udvikling", "urørt"):
        lines += [f"### {labels[pname]}", "",
                  "| Variant | CAGR % | Største fald % | Handler | Vindere % | Gns. handel % | Købssignaler | Fyldte pladser % |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for _, r in frame[frame["periode"] == pname].iterrows():
            lines.append(f"| {r['variant']} | {fmt(r['cagr_pct'])} | {fmt(r['maxdd_pct'])} | {fmt(r['handler'], 0)} | "
                         f"{fmt(r['vindere_pct'], 0)} | {fmt(r['gns_handel_pct'], 2)} | {fmt(r['signaler'], 0)} | {fmt(r['fyldte_pladser_pct'], 0)} |")
        lines.append("")
    lines += ["`Fyldte pladser` er gennemsnittet af de 40 pladser, der var optaget (kun lukkede handler); lav værdi betyder, at "
              "kontanter stod ubrugt, fordi filtrene lader få signaler igennem. Det trækker CAGR ned uden at sige noget om "
              "signalernes kvalitet; `Gns. handel %` (afkast pr. handel efter omkostning) er derfor et renere mål for signalkvaliteten.", "",
              "## Usikkerhed", "",
              "90 %-interval for forskel i årlig vækst (procentpoint) ved blok-bootstrap (13 uger) af ugentlige afkast. "
              "Et interval, der indeholder 0, betyder, at forskellen ikke kan skilles fra tilfældighed. Intervallerne antager, "
              "at ugeafkast kan genbruges i blokke, og undervurderer sandsynligvis usikkerheden, fordi variantene deler signaler og er "
              "koncentreret i få markedsfaser.", "",
              "| Periode | Variant | Sammenlignet med | 5 % | 95 % |", "|---|---|---|---:|---:|"]
    for pname, vname, versus, ci in boots:
        lines.append(f"| {pname} | {vname} | {versus} | {fmt(None if ci is None else ci[0] * 100)} | {fmt(None if ci is None else ci[1] * 100)} |")
    lines += ["", "## Dækning (median antal aktier pr. uge, pr. år)", "",
              "| År | med Quality | med Value | Quality >= 60 | Value >= 50 |", "|---|---:|---:|---:|---:|"]
    for year, r in cov_year.iterrows():
        if year >= 2009:
            lines.append(f"| {year} | {r['med Quality']} | {r['med Value']} | {r['Quality >= 60']} | {r['Value >= 50']} |")
    lines += ["", "Værdiscoren kræver 3 års P/E-historik, så den dækker først fra ca. 2012-2013, og tidligt kun få aktier.", "",
              "## Konklusion", "", "KONKLUSION_PLADS", "",
              "## Svagheder", "",
              "- **Overlevelsesbias:** universet er aktier, der findes i dag. Konkurser og udgåede aktier mangler, og indekstilføjelser "
              "kendes bagud. Det favoriserer alle varianter, især dem uden kvalitetskrav.",
              "- **Forenklede scorer:** ikke MSS' formler; ROIC, FCF, Piotroski m.fl. indgår ikke. Tag-valg i XBRL er forenklet "
              "(ét tag pr. begreb), og selskaber med usædvanlig kontoplan får manglende nøgletal.",
              "- **Kun USA, kun US-GAAP** (10-K/10-Q); udenlandske selskaber uden companyfacts er udeladt. Ingen analytikerestimater "
              "(PEG, value trap, regnskabsblokering mangler).",
              "- **EPS og splits:** EPS er i enheder ved indleveringen og omregnes med splits bagefter; et split mellem to indleveringer "
              "kan give et fejlbehæftet TTM-tal i enkelte uger (P/E over 500 og EPS <= 0 udelades).",
              "- **Få uafhængige beslutninger:** få handler pr. variant i urørt periode og tydelige markedsfaser (2012-2021 bull, 2022 bear). "
              "Resultaterne er ikke statistisk sikre.",
              "- Kvalitetskravet er en percentil i et univers på ca. 900 aktier (ikke hele markedet). Kurser er fra Yahoo (uofficiel) "
              "og kan have huller. Ingen skat, spread eller slippage ud over 0,1 %.",
              "- Tærsklerne 60 og 50 er mandagslistens værdier og blev ikke tunet på disse data."]
    (ROOT / "docs" / "B17-ENTRY-BACKTEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log("Skrev docs/B17-ENTRY-BACKTEST.md")


if __name__ == "__main__":
    main()
