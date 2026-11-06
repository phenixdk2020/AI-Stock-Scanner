"""Kør scanneren uden GUI, fx via Windows Opgavestyring."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import sys
import warnings

import pandas as pd

from stockscanner.candles import PATTERNS, backtest, eligible_signals, trade_backtest
from stockscanner.core import DEFAULT_TICKERS, analyze_prices, parse_tickers
from stockscanner.exits import (
    ALL_RULES as EXIT_RULES, exit_signals, simulate, stockmap_entries, stockmap_exit_days, summarize, trend_entries,
)
from stockscanner.market_data import fetch_history
from stockscanner.mss_compare import compare, load_observations, summary
from stockscanner.quality import score_quality
from stockscanner.quality_rank import quality_percentiles
from stockscanner.regimes import REGIMES, regime_backtest
from stockscanner.scores import momentum_scores, value_scores
from stockscanner.sector_rs import load_sector_map
from stockscanner.weekly_list import apply_news, build_rows
from stockscanner.valuation import fetch_inputs as fetch_value_inputs, value_channel
from stockscanner.storage import load_or_fetch_fundamentals, load_watchlist, save_scans


def print_quality(tickers: list[str]) -> int:
    """Udskriv kvalitetsscore pr. symbol. Screening, ikke en købsanbefaling."""
    shown = 0
    for ticker in tickers:
        try:
            result = score_quality(load_or_fetch_fundamentals(ticker))
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
            continue
        shown += 1
        total = "–" if result.total is None else f"{result.total:.1f}"
        pillars = ", ".join(
            f"{name} {'–' if score is None else f'{score:.0f}'}" for name, score in result.pillars.items()
        )
        print(f"{result.ticker}: kvalitet {total}/100 ({result.label}) | dækning {result.coverage * 100:.0f} % | "
              f"{pillars} | {result.model_note} | år: {', '.join(result.data_years)}")
        if result.missing:
            print(f"    mangler: {', '.join(result.missing)}")
    print("Screening ud fra uofficielle regnskabsdata – ikke en købsanbefaling.")
    return 0 if shown else 1


def print_candles(tickers: list[str], period: str, cost_pct: float, require_pullback: bool,
                  target_r: float | None = None) -> int:
    """Seneste candle-signaler pr. symbol og backtest mod en tilfældig dag."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
    histories = {}
    for ticker in tickers:
        try:
            histories[ticker] = fetch_history(ticker, period=period)[0]
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
    if not histories:
        return 1
    print(f"Seneste signaler (kun i optrend{' efter tilbagerekyl' if require_pullback else ''}, sidste 5 dage):")
    for ticker, frame in histories.items():
        recent = eligible_signals(frame, require_pullback=require_pullback).tail(5)
        hits = [f"{day.date()} {PATTERNS[name]}" for day, row in recent.iterrows() for name in PATTERNS if row[name]]
        print(f"  {ticker}: {'; '.join(hits) or '–'}")
    print(f"\nBacktest {period}, {len(histories)} aktier, kurtage {cost_pct} % pr. handel "
          "(signal ved lukning, køb næste åbning, salg ved lukning efter N dage):")
    print("  Basis = alle dage; Kontekst = kun dage i samme optrend/rekyl. Edge = mønster minus basis.")
    print(f"  {'Mønster':<44}{'N':>6}{'Snit %':>9}{'Median %':>10}{'Hit %':>8}"
          f"{'Basis %':>9}{'Edge %':>9}{'Kontekst %':>12}{'K-edge %':>10}")
    fmt = lambda x: "–" if x is None else f"{x:.2f}"
    for row in backtest(histories, cost_pct=cost_pct, require_pullback=require_pullback):
        print(f"  {PATTERNS[row.pattern] + ' ' + row.horizon:<44}{row.signals:>6}{fmt(row.mean_pct):>9}"
              f"{fmt(row.median_pct):>10}{fmt(row.hit_rate_pct):>8}{fmt(row.baseline_mean_pct):>9}"
              f"{fmt(row.edge_pct):>9}{fmt(row.context_baseline_pct):>12}{fmt(row.context_edge_pct):>10}")
    print(f"\nHandler som i Daytrader.dk-guiden, på dagsdata: købsstop over trigger inden for 5 dage, stop-loss "
          f"under mønsteret{f', mål {target_r} R' if target_r else ''}, ellers salg ved lukning efter N holdedage.")
    print("  Basis = køb ved åbning en tilfældig dag, samme holdetid.")
    print(f"  {'Mønster':<44}{'Handler':>8}{'Snit %':>9}{'Hit %':>8}{'Snit R':>8}{'Stoppet %':>11}"
          f"{'Basis %':>9}{'Edge %':>9}")
    for row in trade_backtest(histories, hold_days=(1, 5, 20, 60), target_r=target_r,
                              cost_pct=cost_pct, require_pullback=require_pullback):
        print(f"  {PATTERNS[row.pattern] + f' {row.hold_days}d':<44}{row.trades:>8}{fmt(row.mean_pct):>9}"
              f"{fmt(row.hit_rate_pct):>8}{fmt(row.mean_r):>8}{fmt(row.stopped_pct):>11}"
              f"{fmt(row.baseline_pct):>9}{fmt(row.edge_pct):>9}")
    print("Historisk test på få aktier (overlevelsesbias, ingen out-of-sample) – ikke en købsanbefaling.")
    return 0


def print_regimes(tickers: list[str], period: str, cost_pct: float, benchmark: str, holdout_start: str) -> int:
    """Fase 5 A–C: trend, relativ styrke og tilbagerekyl mod en tilfældig dag."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
    histories = {}
    for ticker in tickers:
        try:
            histories[ticker] = fetch_history(ticker, period=period)[0]
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
    if not histories:
        return 1
    try:
        bench = fetch_history(benchmark, period=period)[0]
    except Exception as error:
        print(f"Benchmark {benchmark}: FEJL – {error}; B springes over", file=sys.stderr)
        bench = None
    print(f"Fase 5 A–C: {len(histories)} aktier, {period}, benchmark {benchmark} (dagen før), kurtage {cost_pct} % "
          f"pr. handel. Køb næste åbning, salg ved lukning efter N dage. Urørt periode fra {holdout_start}.")
    print("Dagene overlapper, så N er ikke uafhængige observationer. Edge = regime minus alle dage i perioden.")
    fmt = lambda x: "–" if x is None else f"{x:.2f}"
    last = None
    for row in regime_backtest(histories, bench, holdout_start=holdout_start, cost_pct=cost_pct):
        if (row.period, row.horizon) != last:
            last = (row.period, row.horizon)
            print(f"\n  [{row.period}, {row.horizon}]  {'Regime':<32}{'Dage':>8}{'Snit %':>9}{'Median %':>10}"
                  f"{'Hit %':>8}{'Edge %':>9}{'Værste 5 %':>12}")
        print(f"  {'':<{len(row.period) + len(row.horizon) + 4}}  {REGIMES[row.regime]:<32}{row.days:>8}"
              f"{fmt(row.mean_pct):>9}{fmt(row.median_pct):>10}{fmt(row.hit_rate_pct):>8}{fmt(row.edge_pct):>9}"
              f"{fmt(row.worst5_pct):>12}")
    print("\nHistorisk test (overlevelsesbias: kun aktier der findes i dag) – ikke en købsanbefaling.")
    return 0


def print_mss_comparison(benchmark: str) -> int:
    """Vores tal mod observerede MSS-tal i data/mss_observations.csv (fase 7)."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
    try:
        observations = load_observations()
    except FileNotFoundError:
        print("Mangler data/mss_observations.csv", file=sys.stderr)
        return 1
    bench = fetch_history(benchmark, period="2y")[0]
    prices = lambda ticker: fetch_history(ticker, period="2y")[0]
    quality = lambda ticker: score_quality(load_or_fetch_fundamentals(ticker)).total
    rows = compare(observations, prices, quality, bench)
    fmt = lambda x: "–" if x is None else f"{x:.0f}"
    print(f"{'Dato':<11}{'Aktie':<11}{'MSS Q':>6}{'Vores Q':>8}  {'MSS timingzone':<28}{'Vores trend':<17}"
          f"{'MSS °':>6}{'Vores °':>8}{'Forskel':>8}")
    for row in rows:
        print(f"{row.date:<11}{row.ticker:<11}{fmt(row.mss_quality):>6}{fmt(row.our_quality):>8}  "
              f"{row.mss_zone:<28}{row.our_trend:<17}{fmt(row.mss_angle):>6}{fmt(row.our_angle):>8}"
              f"{fmt(row.angle_diff):>8}")
    result = summary(rows)
    two = lambda x: "–" if x is None else f"{x:.2f}"
    print(f"\nKvalitet: rangkorrelation {two(result['quality_spearman'])}, gns. afvigelse "
          f"{two(result['quality_mean_abs_diff'])} point.  StockMap ({benchmark}): median vinkelforskel "
          f"{two(result['angle_median_diff'])}°, {two(result['angle_within_45'])} % inden for 45°.")
    print("Få observationer – kun en første pejling.")
    return 0


def print_value_channels(tickers: list[str], horizon: float) -> int:
    """Værdikanal (EPS × P/E bear/base/bull) og værdiansættelsesscore pr. symbol."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
    fmt = lambda x, d=0: "–" if x is None else f"{x:.{d}f}"
    print(f"Værdikanal, horisont {horizon:g} år: base-P/E = historisk gennemsnit, bear/bull = ±20 %. "
          "Score 100 = bear-linjen, 0 = bull-linjen (ikke afkortet).")
    print(f"{'Aktie':<11}{'Kurs':>9}{'P/E bear/base/bull':>21}{'Bear %':>8}{'Base %':>8}{'Bull %':>8}"
          f"{'Score':>7}{'I dag':>7}{'Asym.':>7}{'PEG':>6}{'Impl. P/E':>10}  Noter")
    shown = 0
    for ticker in tickers:
        try:
            channel = value_channel(fetch_value_inputs(ticker), horizon=horizon)
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
            continue
        shown += 1
        pes = "/".join(fmt(x, 1) for x in (channel.pe_bear, channel.pe_base, channel.pe_bull))
        up = channel.upside_pct
        print(f"{ticker:<11}{channel.price:>9.1f}{pes:>21}{fmt(up.get('bear')):>8}{fmt(up.get('base')):>8}"
              f"{fmt(up.get('bull')):>8}{fmt(channel.score):>7}{fmt(channel.score_today):>7}"
              f"{fmt(channel.asymmetry, 1):>7}{fmt(channel.peg, 2):>6}{fmt(channel.implied_pe, 1):>10}  "
              f"{'; '.join(channel.notes)}")
    print("Analytikertal fra yfinance (uofficiel) – screening, ikke en købsanbefaling.")
    return 0 if shown else 1


def print_exit_study(tickers: list[str], period: str, benchmark: str, holdout_start: str, cost_pct: float) -> int:
    """Punkt 9: salgsregler på samme køb (StockMap-køb og trendkøb), udvikling mod urørt periode."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
    bench = fetch_history(benchmark, period=period)[0]
    results: dict[tuple[str, str, str], list] = {}
    for ticker in tickers:
        try:
            prices = fetch_history(ticker, period=period)[0]
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
            continue
        daily_exits = exit_signals(prices)
        sells = stockmap_exit_days(prices, bench)
        entry_sets = {"StockMap-køb": stockmap_entries(prices, bench), "Trendkøb": trend_entries(prices)}
        for entry_name, entries in entry_sets.items():
            for rule in EXIT_RULES:
                for trade in simulate(prices, entries, rule, daily_exits, sells, cost_pct):
                    part = "urørt" if trade.entry_day >= pd.Timestamp(holdout_start) else "udvikling"
                    results.setdefault((entry_name, part, rule), []).append(trade)
    fmt = lambda x, d=1: "–" if x is None else f"{x:.{d}f}"
    print(f"Salgsregler, {len(tickers)} aktier, {period}, kurtage {cost_pct} %/handel, salg næste åbning. "
          f"Urørt periode fra {holdout_start}.")
    print("Værste = gns. dybeste fald under handlen; Fanget = median andel af bedste gevinst undervejs, der blev hjemtaget.")
    for entry_name in ("StockMap-køb", "Trendkøb"):
        for part in ("udvikling", "urørt"):
            print(f"\n  [{entry_name}, {part}]  {'Regel':<15}{'Handler':>8}{'Snit %':>8}{'Median':>8}{'Win %':>7}"
                  f"{'PF':>6}{'Dage':>6}{'%/100d':>8}{'Værste':>8}{'Værste5%':>9}{'Fanget %':>9}")
            for rule in EXIT_RULES:
                s = summarize(results.get((entry_name, part, rule), []))
                if not s["trades"]:
                    continue
                print(f"  {'':<{len(entry_name) + len(part) + 4}}  {rule:<15}{s['trades']:>8}{fmt(s['mean_pct']):>8}"
                      f"{fmt(s['median_pct']):>8}{fmt(s['win_rate'], 0):>7}{fmt(s['profit_factor'], 2):>6}"
                      f"{fmt(s['days'], 0):>6}{fmt(s['pct_per_100d'], 2):>8}{fmt(s['worst_mean']):>8}"
                      f"{fmt(s['worst_p5']):>9}{fmt(s['capture'], 0):>9}")
    print("\nOverlappende handler tælles hver for sig; kun aktier der findes i dag – ikke en købsanbefaling.")
    return 0


def print_screener(name: str, by_region: bool) -> int:
    """B-04–B-06: kør en eller alle screenere over det cachede univers (byg det med scripts/build_universe.py)."""
    from stockscanner import universe
    from stockscanner.screeners import SCREENERS, screen

    factors = universe.load()
    if factors is None or "t_long_green" not in factors.columns:
        print("Universet mangler, er for gammelt eller er uden trend-kolonner – kør: "
              "scripts/build_universe.py --force", file=sys.stderr)
        return 2
    scores = universe.percentiles(factors, None, by_region=by_region)
    names = list(SCREENERS) if name == "alle" else [name]
    fmt = lambda x: "–" if x is None or x != x else f"{x:.0f}"
    for current in names:
        hits = screen(current, factors, scores)
        print(f"\n{SCREENERS[current]} – {len(hits)} hits af {len(factors)}")
        for ticker, r in hits.head(20).iterrows():
            peg = r.get("x_peg")
            peg = "–" if peg is None or peg != peg else f"{peg:.1f}"
            print(f"  {ticker:<13}{r.get('region', ''):<8}score {fmt(r.get('stock_score')):>3}  Q {fmt(r.get('quality')):>3}"
                  f"  V {fmt(r.get('value')):>3}  Mom {fmt(r.get('momentum')):>3}  upside {fmt(r.get('x_upside')):>4} %"
                  f"  PEG {peg:>4}  {fmt(r.get('mcap_mia_usd'))} mia. USD")
    print("\nScreening efter egne regler inspireret af MSS – ikke købsanbefalinger.")
    return 0


def print_news(tickers: list[str] | None) -> int:
    """B-20: nyheder for research-listen og ejede aktier (eller --tickers), vurderet af lokal Ollama."""
    from stockscanner import news
    from stockscanner.portfolio import load_portfolio

    if tickers is None:
        research = Path(__file__).resolve().parent / "data" / "research_watchlist.txt"
        listed = [line.strip() for line in research.read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.startswith("#")] if research.exists() else []
        tickers = list(dict.fromkeys(listed + list(load_portfolio())))
    for ticker, items in news.scan(tickers).items():
        print(f"\n{ticker} ({news.company_name(ticker)}): {news.summary(items) or 'ingen nyheder de seneste 7 dage'}")
        for item in items:
            mark = {"positiv": "+", "negativ": "−", "neutral": "·"}.get(item.sentiment, "?")
            print(f"  {mark}{item.impact or ''} {item.published} {item.title[:90]} ({item.source})"
                  + (f" – {item.reason}" if item.reason else ""))
    print("\nOverskrifter fra Google News; vurderet af lokal AI og kan tage fejl – ikke investeringsrådgivning.")
    return 0


def why_cheap_input(rows, channels) -> tuple[list[str], dict]:
    """Aktier der skal forklares (Entry først, så billige gode aktier) og tallene til den lokale AI."""
    picked = [r for r in rows if r.action == "KØB-KANDIDAT"]
    picked += [r for r in rows if r.action != "KØB-KANDIDAT" and (r.channel_score or 0) >= 50 and (r.quality or 0) >= 60]
    facts = {}
    for r in picked:
        keep = {k: getattr(r, k) for k in ("quality", "moat", "value_pct", "channel_score", "peg", "asymmetry")}
        channel = channels.get(r.ticker)
        if channel is not None:
            keep["pe_base"] = channel.pe_base
            if channel.eps_today and channel.eps_today > 0:
                keep["pe_nu"] = round(channel.price / channel.eps_today, 1)
        facts[r.ticker] = keep
    return [r.ticker for r in picked], facts


def print_weekly_list(tickers: list[str], benchmark: str, out_dir: Path | None, by_region: bool = False,
                      upload: bool = True, with_news: bool = True) -> int:
    """Mandagsliste: StockMap-signal + Quality/Value/Momentum-percentiler + værdikanal og PEG."""
    import dataclasses

    import yfinance as yf

    from stockscanner import earnings_risk, insiders, news, paper, playbook, site_sync, universe_scenarios, why_cheap
    from stockscanner.sizing import atr, fx_rate, load_settings, position_size

    from stockscanner import universe
    from stockscanner.analyst import fetch_analyst
    from stockscanner.mti_lite import home_index, mti_state
    from stockscanner.portfolio import load_portfolio

    warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
    positions = load_portfolio()
    research = list(tickers)
    site = site_sync.credentials() if upload else None
    if site:
        try:
            tickers = list(tickers) + site_sync.fetch_tickers(*site)  # også det, brugerne på hjemmesiden følger
        except Exception as error:
            print(f"Hjemmesiden: kunne ikke hente tickere – {error}", file=sys.stderr)
    reference = universe.load()
    candidates = universe.buy_funnel(reference, None if reference is None else universe.percentiles(reference, None))
    if candidates:
        print(f"Tragt: {len(candidates)} aktier i universet med StockMap-køb og Quality ≥ 60 – analyseres fuldt: "
              + ", ".join(candidates))
    paper_trades = paper.load()
    held = list(positions) + list(paper.open_positions(paper_trades)["ticker"])
    # ejede aktier, åbne papirhandler og tragtens kandidater kommer altid med
    tickers = list(dict.fromkeys(list(tickers) + held + candidates))
    bench = fetch_history(benchmark, period="3y")[0]
    histories, channels, factor_rows, mti, index_cache, analyst = {}, {}, [], {}, {}, {}
    for ticker in tickers:
        try:
            histories[ticker] = fetch_history(ticker, period="3y")[0]
        except Exception as error:
            print(f"{ticker}: FEJL – {error}", file=sys.stderr)
            continue
        factor_rows.append(universe.factor_row(ticker, load_or_fetch_fundamentals,
                                               lambda t: yf.Ticker(t).info or {}, lambda t: histories[t]))
        try:
            channels[ticker] = value_channel(fetch_value_inputs(ticker))
        except Exception:
            pass
        try:
            analyst[ticker] = fetch_analyst(ticker)
        except Exception:
            pass
        index_symbol = home_index(ticker)
        try:
            if index_symbol not in index_cache:
                index_cache[index_symbol] = fetch_history(index_symbol, period="3y")[0]
            mti[ticker] = mti_state(histories[ticker], index_cache[index_symbol])
        except Exception:
            pass
    targets = pd.DataFrame(factor_rows).set_index("ticker")
    scores = universe.percentiles(targets, reference, by_region=by_region)
    sizes, liquidity = {}, {}    # fra egen kurshistorik, så reglen også gælder aktier uden volumen i universet
    for ticker in histories:
        info = targets.loc[ticker] if ticker in targets.index else {}
        cap, mcap = info.get("x_mcap_usd"), info.get("x_mcap")
        rate = cap / mcap if cap == cap and mcap == mcap and cap and mcap else universe.FX_TO_USD.get(info.get("x_currency"))
        facts = universe.liquidity_facts(histories[ticker], rate)
        sizes[ticker] = universe.size_class(cap)
        liquidity[ticker] = universe.liquidity_class(facts.get("x_adv_usd"), facts.get("x_idle_days"))
    rows = build_rows(list(histories), histories, bench, scores["quality"].dropna().to_dict(),
                      scores["value"].dropna().to_dict(), scores["momentum"].dropna().to_dict(), channels,
                      positions=positions, moat_pct=scores["moat"].dropna().to_dict(), mti_states=mti,
                      analyst=analyst, sizes=sizes, liquidity=liquidity)
    settings = load_settings()
    currencies = targets["x_currency"].to_dict() if "x_currency" in targets.columns else {}
    for i, r in enumerate(rows):
        if r.action != "KØB-KANDIDAT":
            continue
        prices = histories[r.ticker]
        fx = fx_rate(currencies.get(r.ticker), settings["valuta"])
        size = None if fx is None else position_size(float(pd.to_numeric(prices["Close"]).dropna().iloc[-1]),
                                                     atr(prices), settings, fx)
        if size is not None:
            text = (f"køb {size.shares} stk., stop {size.stop:.2f}, risiko {size.risk:,.0f} {settings['valuta']}"
                    if size.shares else f"1 aktie er over loftet på {settings['max_pct']:g} % af kapitalen")
            rows[i] = dataclasses.replace(r, shares=size.shares, stop=size.stop, reasons=f"{r.reasons}; {text}")
    news_items = {}
    if with_news:
        news_items = news.scan(list(histories))
        rows = apply_news(rows, {t: news.summary(items) for t, items in news_items.items()})
    risks = earnings_risk.build_risks(rows, analyst, news_items, histories, date.today())  # kun en advarsel
    fmt = lambda x: "–" if x is None or (isinstance(x, float) and x != x) else f"{x:.0f}"
    basis = f"mod {len(reference)} aktier i universet" if reference is not None else "kun inden for listen (byg universet)"
    market = universe.breadth(reference)
    print(f"Mandagsliste {date.today()} – {len(rows)} aktier, StockMap mod {benchmark}. Percentiler {basis}.")
    if market:
        trend = "bull" if market.get(50, 0) > 50 else "svagt"
        print("Markedsindeks (andel over SMA20/50/200): " + " / ".join(f"{market[d]:.0f} %" for d in sorted(market))
              + f" → marked {trend}")
    print(f"{'Aktie':<11}{'Handling':<15}{'StockMap':<18}{'TPI-lite':<17}{'MTI':<13}{'Q':>4}{'Moat':>5}{'MSS':>5}"
          f"{'V%':>5}{'Mom':>5}{'Kanal':>7}{'PEG':>6}{'Asym':>6}{'Regnskab':>12}{'Str.':>7}{'Likv.':>8}  Begrundelse")
    for r in rows:
        peg = "–" if r.peg is None else f"{r.peg:.1f}"
        asym = "–" if r.asymmetry is None else ("∞" if r.asymmetry == float("inf") else f"{r.asymmetry:.1f}")
        print(f"{r.ticker:<11}{r.action:<15}{r.stockmap:<18}{(r.tpi or '–'):<17}{(r.mti or '–'):<13}{fmt(r.quality):>4}"
              f"{fmt(r.moat):>5}{fmt(r.mss_score):>5}{fmt(r.value_pct):>5}{fmt(r.momentum):>5}{fmt(r.channel_score):>7}"
              f"{peg:>6}{asym:>6}{(r.earnings or '–'):>12}{(r.size or '–'):>7}{(r.liquidity or '–'):>8}  {r.reasons}")
    for r in rows:
        if r.news:
            print(f"  {r.ticker}: {r.news}")
    for ticker, risk in risks.items():
        print(f"  {ticker}: {earnings_risk.describe(risk)}")
    if out_dir is not None:
        changes_seen = []
        out_dir.mkdir(parents=True, exist_ok=True)
        log_path = out_dir / "regnskabsrisiko_log.csv"
        earnings_risk.log_assessments(risks, date.today(), log_path)
        filled = earnings_risk.fill_outcomes(histories, date.today(), log_path)
        if filled:
            print(f"Regnskabsrisiko-log: {filled} udfald udfyldt.")
        frame = pd.DataFrame([r.__dict__ for r in rows]).assign(dato=str(date.today()))
        path = out_dir / f"mandagsliste_{date.today()}.csv"
        frame.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
        history_path = out_dir / "mandagsliste_historik.csv"
        if history_path.exists():
            history = pd.read_csv(history_path, sep=";", encoding="utf-8-sig")
            previous = history[history["dato"] < str(date.today())].sort_values("dato").groupby("ticker").last()
            for r in rows:
                if r.ticker in previous.index:
                    old = previous.loc[r.ticker]
                    changes = [f"{name}: {old[col]} → {new}" for name, col, new in
                               (("handling", "action", r.action), ("StockMap", "stockmap", r.stockmap), ("TPI", "tpi", r.tpi))
                               if str(old[col]) != str(new)]
                    if changes:
                        print(f"  ÆNDRING {r.ticker}: " + "; ".join(changes))
                        changes_seen.append(f"{r.ticker}: " + "; ".join(changes))
            history = pd.concat([history[history["dato"] != str(date.today())], frame])
        else:
            history = frame
        history.to_csv(history_path, sep=";", index=False, encoding="utf-8-sig")
        print(f"Gemt: {path} og historik i {history_path}")
        paper_trades, messages = paper.update(paper_trades, rows, histories, date.today())
        paper.save(paper_trades)
        for message in messages:
            print("  " + message)
        changes_seen += messages
        last = {t: float(pd.to_numeric(h["Close"]).dropna().iloc[-1]) for t, h in histories.items() if not h.empty}
        result = paper.summary(paper_trades, last)
        if result["afkast_pct"] is not None:
            print(f"Papirportefølje: {result['handler']} handler, {result['aabne']} åbne, gennemsnit "
                  f"{result['afkast_pct']:+.1f} % pr. handel, vundne {result['vundne_pct']:.0f} %")
        # Papirporteføljens stilling mod RSP: én linje pr. kørsel i data/papir_stilling.csv (dublet samme dato overskrives)
        stilling = paper.score(paper_trades, last, bench, date.today())
        paper.log_score(stilling, date.today())
        if stilling["forskel_pp"] is not None:
            print(f"Papir mod RSP: {stilling['sammenlignet']} af {stilling['antal']} handler sammenlignet, "
                  f"{stilling['afkast_pct']:+.1f} % mod RSP {stilling['rsp_pct']:+.1f} % ({stilling['forskel_pp']:+.1f} %-point)"
                  + (" – under 3 måneder siger tallene ikke noget" if stilling["for_tidligt"] else ""))
        maaling = measure_lists(history_path, histories, bench)
        # B-13: scripts/notify.ps1 viser linjerne som Windows-besked
        (out_dir / "aendringer.txt").write_text("\n".join(changes_seen), encoding="utf-8")
        if site:
            try:
                insider_facts = insiders.build(list(histories), date.today())
                print(f"Insiderkøb: {sum(f['buyers'] > 0 for f in insider_facts.values())} af "
                      f"{len(insider_facts)} amerikanske aktier har køb de seneste 90 dage.")
                explained = {}
                if with_news:
                    explained = why_cheap.build(*why_cheap_input(rows, channels), analyst=analyst,
                                                news_items=news_items, today=date.today())
                    print(f"Hvorfor billig: {len(explained)} forklaringer klar.")
                everyone = reference if reference is not None else targets
                payload = playbook.build_payload(
                    rows=rows, histories=histories, currencies=currencies,
                    regions={t: universe.region(t) for t in histories}, atrs={t: atr(h) for t, h in histories.items()},
                    research=research, breadth=market, benchmark=benchmark, factors=everyone,
                    scores=universe.percentiles(everyone, None), regional=universe.percentiles(everyone, None, by_region=True),
                    trades=paper_trades, last_prices=last, changes=changes_seen, news=news_items,
                    candidates=candidates, earnings_risk=risks, universe_scenarios=universe_scenarios.load(), channels=channels,
                    sector_map=load_sector_map(Path(__file__).resolve().parent / "data" / "sector_map.json"),
                    paper_score=stilling, measurement=maaling, analyst=analyst, insiders=insider_facts,
                    why_cheap=explained)
                site_sync.save_payload(payload)     # så en afbrudt upload kan sendes igen uden en ny kørsel
                receipt = site_sync.send_playbook(payload, *site)
                print(f"Hjemmesiden opdateret: {receipt.get('stocks', len(payload['stocks']))} aktier sendt.")
            except Exception as error:
                print(f"Hjemmesiden blev IKKE opdateret: {error}", file=sys.stderr)
            try:    # Overblik og Analyse får deres tal ad en anden vej end Playbook
                dates = {t: h.index[-1].date() for t, h in histories.items() if len(h)}
                site_sync.send_snapshot(site_sync.snapshot_from_rows(rows, dates), *site)
                print("Scanner-snapshot opdateret.")
            except Exception as error:
                print(f"Scanner-snapshot blev IKKE opdateret: {error}", file=sys.stderr)
        else:
            print("Hjemmesiden: ikke sat op (ASC_WP_SITE_URL, ASC_WP_USER, ASC_WP_APP_PASSWORD mangler) – springer over.")
    print("Screening efter egne regler inspireret af MSS – ikke en købsanbefaling.")
    return 0


def measure_lists(history_path: Path, histories: dict, bench: pd.DataFrame) -> dict | None:
    """Fremadrettet måling af listerne. En fejl her må aldrig stoppe mandagslisten."""
    from stockscanner import forward

    try:
        result = forward.run(history_path, histories, bench, lambda ticker: fetch_history(ticker, period="3y")[0])
    except Exception as error:
        print(f"Måling sprunget over – {error}", file=sys.stderr)
        return None
    print("\n".join(forward.report(result)))
    return result


def print_measurement(upload: bool = True) -> int:
    """Mål listerne nu og læg tallene på siden. Rører hverken købsregler, papirportefølje eller kurser på listen."""
    from stockscanner import site_sync

    history_path = Path(__file__).resolve().parent / "data" / "mandagsliste_historik.csv"
    if not history_path.exists():
        print("Måling: ingen mandagsliste endnu.", file=sys.stderr)
        return 1
    bench = fetch_history("RSP", period="3y")[0]
    result = measure_lists(history_path, {"RSP": bench}, bench)
    if result is None:
        return 1
    if not upload or not site_sync.PAYLOAD_FILE.exists():
        return 0
    stamp = site_sync.PAYLOAD_FILE.stat().st_mtime
    payload = site_sync.load_payload()
    payload["measurement"] = result
    if site_sync.PAYLOAD_FILE.stat().st_mtime != stamp:
        print("Måling: en anden kørsel har skrevet imens, så den får lov at stå.")
        return 0
    site_sync.save_payload(payload)
    site = site_sync.credentials()
    if site:
        print(f"Hjemmesiden opdateret: {site_sync.send_playbook(payload, *site).get('stocks')} aktier sendt.")
    return 0


def print_entry_check(upload: bool = True) -> int:
    """Opdatér Entry for de fulgte aktier i seneste playbook. Bruger ikke GPU, nyheder eller papirporteføljen."""
    from datetime import datetime, timezone

    from stockscanner import entry_check, site_sync
    from stockscanner.analyst import fetch_analyst
    from stockscanner.portfolio import load_portfolio

    data_dir = Path(__file__).resolve().parent / "data"
    history_path = data_dir / "mandagsliste_historik.csv"
    if not site_sync.PAYLOAD_FILE.exists() or not history_path.exists():
        print("Entry-tjek: ingen mandagsliste endnu. Kør --mandagsliste først.", file=sys.stderr)
        return 1
    stamp = site_sync.PAYLOAD_FILE.stat().st_mtime
    payload = site_sync.load_payload()
    site = site_sync.credentials()
    wanted = site_sync.fetch_tickers(*site) if site else list(payload["stocks"])
    owned = set(load_portfolio())
    factors = entry_check.latest_factors(history_path)
    tickers = [t for t in entry_check.followed(payload, wanted) if t not in owned and t in factors.index]
    bench = fetch_history(payload.get("benchmark") or "RSP", period="3y")[0]
    histories, channels, analyst = {}, {}, {}
    for ticker in tickers:
        try:    # en aktie uden friske tal beholder sin vurdering, så et datahul aldrig ligner et Entry
            prices = fetch_history(ticker, period="3y")[0]
            channel = value_channel(fetch_value_inputs(ticker))
            info = fetch_analyst(ticker)
        except Exception as error:
            print(f"{ticker}: sprunget over – {error}", file=sys.stderr)
            continue
        histories[ticker], channels[ticker], analyst[ticker] = prices, channel, info
    column = lambda name: factors[name].dropna().to_dict() if name in factors else {}
    rows = build_rows(list(histories), histories, bench, column("quality"), column("value_pct"), column("momentum"),
                      channels, moat_pct=column("moat"), analyst=analyst, sizes=column("size"),
                      liquidity=column("liquidity"))
    rows = apply_news(rows, {t: payload["stocks"][t].get("news_summary") for t in histories})
    changes = entry_check.apply(payload, rows, histories, datetime.now(timezone.utc))
    print(f"Entry-tjek {date.today()}: {len(rows)} af {len(tickers)} fulgte aktier tjekket, "
          f"{sum(r.action == 'KØB-KANDIDAT' for r in rows)} med Entry. StockMap er fra sidste afsluttede uge.")
    for change in changes:
        print("  " + change)
    if not upload:
        return 0
    if site_sync.PAYLOAD_FILE.stat().st_mtime != stamp:
        print("Entry-tjek: mandagslisten er kørt imens, så den nye playbook får lov at stå.")
        return 0
    site_sync.save_payload(payload)
    (data_dir / "aendringer.txt").write_text("\n".join(changes), encoding="utf-8")
    if site:
        print(f"Hjemmesiden opdateret: {site_sync.send_playbook(payload, *site).get('stocks')} aktier sendt.")
    return 0


def main() -> int:
    # Dansk tekst skal være læsbar, også når output sendes gennem en pipe på Windows (cp1252).
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="AI-Stock-Scanner – daglig batchscanning")
    parser.add_argument("--tickers", help="Komma-separerede symboler; ellers gemt watchlist")
    parser.add_argument("--csv", type=Path, help="Skriv seneste resultater til CSV")
    parser.add_argument("--no-save", action="store_true", help="Undlad at gemme i SQLite")
    parser.add_argument(
        "--kvalitet", action="store_true",
        help="Vis kvalitetsscore (regnskabstal, cachet i 7 dage) i stedet for teknisk scanning",
    )
    parser.add_argument("--candles", action="store_true", help="Vis candle-signaler og backtest mod tilfældig dag")
    parser.add_argument("--periode", default="10y", help="Kurshistorik til --candles (yfinance-periode, fx 5y)")
    parser.add_argument("--kurtage", type=float, default=0.1, help="Kurtage i %% pr. handel til --candles")
    parser.add_argument("--uden-rekyl", action="store_true", help="--candles: kræv kun optrend, ikke tilbagerekyl")
    parser.add_argument("--maal", type=float, help="--candles: kursmål i R (fx 2 = to gange risikoen)")
    parser.add_argument("--regimer", action="store_true", help="Fase 5 A–C: trend, relativ styrke, tilbagerekyl")
    parser.add_argument("--salg", action="store_true", help="Punkt 9: test af salgsregler på samme køb")
    parser.add_argument("--mandagsliste", action="store_true",
                        help="Ugentlig liste: køb-kandidater/salg ud fra StockMap, Quality, Value og PEG")
    parser.add_argument("--screener", choices=["triple-green", "tpi-trend", "stock-of-the-day", "alle"],
                        help="B-04–B-06: screener over det cachede univers")
    parser.add_argument("--entry-tjek", action="store_true",
                        help="Opdatér Entry for de fulgte aktier i seneste playbook (uden nyheder og GPU)")
    parser.add_argument("--maaling", action="store_true",
                        help="Mål mandagslisterne fremad mod RSP og læg tallene på hjemmesiden.")
    parser.add_argument("--ingen-upload", action="store_true",
                        help="--mandagsliste: send ikke resultatet til hjemmesiden")
    parser.add_argument("--nyheder", action="store_true",
                        help="B-20: nyheder for research-listen og porteføljen, vurderet af lokal Ollama")
    parser.add_argument("--uden-nyheder", action="store_true", help="--mandagsliste: spring nyhederne over")
    parser.add_argument("--send-igen", action="store_true", help="send seneste playbook til hjemmesiden uden ny kørsel")
    parser.add_argument("--region", action="store_true",
                        help="Percentiler kun mod samme region (USA/Norden/Europa), som MSS")
    parser.add_argument("--vaerdi", action="store_true", help="Værdikanal og værdiansættelsesscore")
    parser.add_argument("--horisont", type=float, default=2.0, help="--vaerdi: år frem (MSS' standard er 2)")
    parser.add_argument("--sammenlign-mss", action="store_true",
                        help="Sammenlign vores tal med data/mss_observations.csv")
    parser.add_argument("--benchmark", default="RSP", help="--regimer: benchmark til relativ styrke")
    parser.add_argument("--urort", default="2024-11-01", help="--regimer: start på urørt slutperiode (ÅÅÅÅ-MM-DD)")
    arguments = parser.parse_args()

    if arguments.screener:
        return print_screener(arguments.screener, arguments.region)
    if arguments.send_igen:
        from stockscanner import site_sync

        site = site_sync.credentials()
        if not site:
            print("Hjemmesiden: ikke sat op.", file=sys.stderr)
            return 1
        print(f"Hjemmesiden opdateret: {site_sync.send_playbook(site_sync.load_payload(), *site).get('stocks')} aktier sendt.")
        return 0
    if arguments.nyheder:
        return print_news(parse_tickers(arguments.tickers) if arguments.tickers else None)
    if arguments.sammenlign_mss:
        return print_mss_comparison(arguments.benchmark)

    try:
        selected = parse_tickers(arguments.tickers) if arguments.tickers else load_watchlist()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if arguments.kvalitet:
        return print_quality(selected)
    if arguments.vaerdi:
        return print_value_channels(selected, arguments.horisont)
    if arguments.maaling:
        return print_measurement(not arguments.ingen_upload)
    if arguments.entry_tjek:
        return print_entry_check(not arguments.ingen_upload)
    if arguments.mandagsliste:
        research = Path(__file__).resolve().parent / "data" / "research_watchlist.txt"
        if not arguments.tickers and research.exists():
            selected = [line.strip() for line in research.read_text(encoding="utf-8").splitlines()
                        if line.strip() and not line.startswith("#")]
        return print_weekly_list(selected, arguments.benchmark, Path(__file__).resolve().parent / "data",
                                 arguments.region, not arguments.ingen_upload, not arguments.uden_nyheder)
    if arguments.salg:
        return print_exit_study(selected, arguments.periode, arguments.benchmark, arguments.urort, arguments.kurtage)
    if arguments.regimer:
        return print_regimes(selected, arguments.periode, arguments.kurtage, arguments.benchmark, arguments.urort)
    if arguments.candles:
        return print_candles(selected, arguments.periode, arguments.kurtage, not arguments.uden_rekyl, arguments.maal)

    results = []
    failed = []
    for ticker in selected:
        try:
            frame, currency = fetch_history(ticker)
            results.append(analyze_prices(frame, ticker, currency))
        except Exception as error:
            failed.append({"ticker": ticker, "error": str(error)})

    if results and not arguments.no_save:
        save_scans(results)
    if arguments.csv is not None and results:
        arguments.csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([asdict(item) for item in results]).drop(columns=["checks"]).to_csv(
            arguments.csv, sep=";", index=False, encoding="utf-8-sig"
        )
    print(json.dumps(
        {"count": len(results), "results": [asdict(item) for item in results], "errors": failed},
        ensure_ascii=False, indent=2,
    ))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
