"""Streamlit-side: mandagslisten (StockMap, TPI-lite, MTI-lite, Quality/Moat/MSS, værdikanal) og portefølje."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESEARCH = DATA / "research_watchlist.txt"
PORTFOLIO = DATA / "portfolio.csv"
HISTORY = DATA / "mandagsliste_historik.csv"

st.set_page_config(page_title="Mandagsliste", page_icon="🗓️", layout="wide")
st.title("🗓️ Mandagsliste")
st.caption("Egne regler inspireret af MSS' 3-Point Playbook: kvalitet → værdi → timing. "
           "Screening, ikke købs- eller salgsanbefalinger.")


def latest_list() -> tuple[pd.DataFrame | None, str | None]:
    files = sorted(DATA.glob("mandagsliste_20*.csv"))
    if not files:
        return None, None
    return pd.read_csv(files[-1], sep=";", encoding="utf-8-sig"), files[-1].stem.replace("mandagsliste_", "")


col_run, col_info = st.columns([1, 3])
with col_run:
    if st.button("Kør mandagslisten nu", type="primary", width="stretch"):
        with st.spinner("Henter kurser og regnskaber … (et par minutter)"):
            result = subprocess.run([sys.executable, "-W", "ignore", str(ROOT / "scan_cli.py"), "--mandagsliste"],
                                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        st.session_state["weekly_output"] = result.stdout[-6000:] + result.stderr[-2000:]
with col_info:
    st.info("Kører også automatisk hver mandag kl. 8 (Windows-opgaven \"AI-Stock-Scanner mandagsliste\").")

if st.session_state.get("weekly_output"):
    with st.expander("Seneste kørsel (tekst)"):
        st.code(st.session_state["weekly_output"])

frame, day = latest_list()
if frame is None:
    st.warning("Ingen mandagsliste endnu – tryk \"Kør mandagslisten nu\".")
else:
    st.subheader(f"Liste fra {day}")
    actions = sorted(frame["action"].dropna().unique())
    chosen = st.multiselect("Vis handlinger", actions, default=actions)
    columns = [c for c in ("ticker", "action", "stockmap", "tpi", "mti", "quality", "moat", "mss_score", "value_pct",
                           "momentum", "channel_score", "peg", "asymmetry", "earnings", "eps_trend", "shares", "stop", "reasons") if c in frame.columns]
    shown = frame[frame["action"].isin(chosen)][columns]
    st.dataframe(shown, width="stretch", hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="%.0f") for c in
                                ("quality", "moat", "mss_score", "value_pct", "momentum", "channel_score")})
    st.caption("Handling: KØB-KANDIDAT = StockMap-køb + Quality ≥ 60 + nederste halvdel af værdikanalen + PEG < 2 "
               "+ asymmetri ≥ 3 + intet regnskab inden for 7 dage + ingen value trap. shares/stop = foreslået antal og stop. "
               "SÆLG/BEHOLD (ejet) gælder kun aktier i porteføljen. \"pil ned\" = StockMap-salg på en aktie du ikke ejer.")

if HISTORY.exists():
    with st.expander("Historik – ændringer fra uge til uge"):
        history = pd.read_csv(HISTORY, sep=";", encoding="utf-8-sig")
        pivot = history.pivot_table(index="ticker", columns="dato", values="action", aggfunc="last")
        st.dataframe(pivot, width="stretch")

left, right = st.columns(2)
with left:
    st.subheader("Research-liste")
    text = RESEARCH.read_text(encoding="utf-8") if RESEARCH.exists() else ""
    edited = st.text_area("Én ticker pr. linje (yfinance-format, fx NOVO-B.CO)", text, height=220)
    if st.button("Gem research-liste"):
        RESEARCH.write_text(edited if edited.endswith("\n") else edited + "\n", encoding="utf-8")
        st.success("Gemt.")
with right:
    st.subheader("Min portefølje")
    portfolio = (pd.read_csv(PORTFOLIO, sep=";", encoding="utf-8-sig", comment="#") if PORTFOLIO.exists()
                 else pd.DataFrame(columns=["ticker", "antal", "koebskurs", "koebsdato"]))
    edited_portfolio = st.data_editor(portfolio, num_rows="dynamic", width="stretch", key="portfolio_editor")
    if st.button("Gem portefølje"):
        DATA.mkdir(parents=True, exist_ok=True)
        PORTFOLIO.write_text("# ticker;antal;koebskurs;koebsdato (ÅÅÅÅ-MM-DD)\n" +
                             edited_portfolio.dropna(subset=["ticker"]).to_csv(sep=";", index=False), encoding="utf-8")
        st.success("Gemt – salgsreglerne gælder fra næste kørsel.")

    from stockscanner.portfolio import fetch_quotes, load_portfolio, valuation

    @st.cache_data(ttl=900, show_spinner="Henter kurser …")
    def cached_quotes(tickers: tuple[str, ...]):
        return fetch_quotes(tickers)

    positions = load_portfolio(PORTFOLIO)
    if positions:
        if st.button("Opdatér kurser"):
            cached_quotes.clear()
        table = valuation(positions, cached_quotes(tuple(sorted(positions))))
        st.dataframe(table.style.format({"kurs": "{:.2f}", "vaerdi": "{:,.0f}", "gevinst": "{:+,.0f}",
                                         "gevinst_pct": "{:+.1f} %", "koebskurs": "{:.2f}", "dag": "{:+,.0f}",
                                         "dag_pct": "{:+.1f} %"}, na_rep="–"),
                     width="stretch", hide_index=True)
        for currency, part in table.dropna(subset=["vaerdi"]).groupby("valuta"):
            cost = (part["koebskurs"] * part["antal"]).sum()
            day = part["dag"].sum()
            yesterday = part["vaerdi"].sum() - day
            st.caption(f"{currency}: værdi {part['vaerdi'].sum():,.0f}, gevinst {part['gevinst'].sum():+,.0f} "
                       f"({(part['vaerdi'].sum() / cost - 1) * 100:+.1f} %), siden i går {day:+,.0f}"
                       f" ({(day / yesterday * 100 if yesterday else 0):+.1f} %)")
        st.caption("Kurser fra yfinance, op til 15 min. gamle (gemmes i 15 min.).")
    else:
        st.caption("Ingen aktier i porteføljen endnu – tilføj dem ovenfor og tryk Gem.")


st.divider()
st.subheader("Positionsstørrelse")
from stockscanner.sizing import load_settings, save_settings

settings = load_settings()
c1, c2, c3, c4 = st.columns(4)
capital = c1.number_input("Kapital", min_value=0.0, value=float(settings["kapital"]), step=10000.0,
                          help="Hele porteføljens størrelse; bruges til antal aktier pr. køb-kandidat.")
currency = c2.selectbox("Valuta", ["DKK", "SEK", "NOK", "EUR", "USD"],
                        index=["DKK", "SEK", "NOK", "EUR", "USD"].index(settings["valuta"])
                        if settings["valuta"] in ["DKK", "SEK", "NOK", "EUR", "USD"] else 0)
risk = c3.number_input("Risiko pr. handel (%)", min_value=0.1, max_value=5.0, value=float(settings["risiko_pct"]),
                       step=0.25, help="MSS/MarketTimer: 0,5–1 % af kapitalen tabes, hvis stoppet rammes.")
cap_pct = c4.number_input("Maks. pr. aktie (%)", min_value=0.5, max_value=100.0, value=float(settings["max_pct"]),
                          step=0.5, help="Loft over hvor stor en del af kapitalen der må ligge i én aktie (ca. 3 %).")
if st.button("Gem indstillinger"):
    save_settings(dict(settings, kapital=capital, valuta=currency, risiko_pct=risk, max_pct=cap_pct))
    st.success("Gemt – gælder fra næste kørsel af mandagslisten.")
st.caption("Stop = kurs − 3 × ATR(14). Antal = det mindste af risikogrænsen og loftet. Valutakurser er omtrentlige.")

st.divider()
st.subheader("Screenere over universet")
from stockscanner import universe as universe_module
from stockscanner.screeners import SCREENERS, screen

factors = universe_module.load()
if factors is None or "t_long_green" not in factors.columns:
    st.info("Universet skal bygges med de nye kolonner: scripts/build_universe.py --force (sker også mandag).")
else:
    choice = st.selectbox("Screener", list(SCREENERS), format_func=lambda k: SCREENERS[k])
    regional = st.checkbox("Percentiler pr. region (som MSS)", value=True)
    hits = screen(choice, factors, universe_module.percentiles(factors, None, by_region=regional))
    st.dataframe(hits, width="stretch", column_config={c: st.column_config.NumberColumn(format="%.0f") for c in
                                                       ("stock_score", "quality", "value", "momentum", "moat",
                                                        "x_upside", "mcap_mia_usd")})
    st.caption(f"{len(hits)} hits af {len(factors)} aktier. \"Grøn\" uge/dag er vores tilnærmelse af MSS' TPI.")

st.divider()
st.subheader("Papirportefølje")
from stockscanner import paper

trades = paper.load()
if trades.empty:
    st.caption("Ingen papirhandler endnu. Mandagslistens køb-kandidater købes automatisk på papir og sælges "
               "med samme salgsregler som dine egne aktier.")
else:
    st.dataframe(trades, width="stretch", hide_index=True)
    st.caption(f"{len(paper.open_positions(trades))} åbne af {len(trades)} handler; "
               f"{paper.AMOUNT:,.0f} pr. handel. Afkast vises i mandagslistens tekst.")
