"""Streamlit-dashboard for AI-Stock-Scanner V1."""
from __future__ import annotations

from dataclasses import asdict
import os

import pandas as pd
import streamlit as st

from stockscanner.core import analyze_prices, parse_tickers
from stockscanner.markets import SAMPLES, market_of, example_tickers
from stockscanner.updater import authorized, check_update, install_update
from stockscanner.market_data import fetch_history
from stockscanner.ollama import explain
from stockscanner.storage import load_watchlist, recent_scans, save_scans, save_watchlist


st.set_page_config(page_title="AI-Stock-Scanner", page_icon="📈", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def cached_history(symbol: str):
    return fetch_history(symbol)


st.title("📈 AI-Stock-Scanner")
st.caption(
    "Privat aktiescanner • daglige, justerede historiske kurser • "
    "tekniske signaler, ikke handelsanbefalinger"
)

with st.sidebar:
    st.header("Overvågningsliste")
    markets = st.multiselect("Aktiemarkeder", list(SAMPLES), default=list(SAMPLES))
    if st.button("Indsæt eksempelaktier fra de valgte markeder", use_container_width=True):
        st.session_state["watchlist_editor"] = "\n".join(example_tickers(markets))
    raw_symbols = st.text_area(
        "Aktiesymboler (komma, mellemrum eller ny linje)",
        value="\n".join(load_watchlist()),
        key="watchlist_editor",
        height=180,
        help="Eksempler: NOVO-B.CO, DSV.CO, VWS.CO, MSFT, NVDA",
    )
    do_scan = st.button("Scan nu", type="primary", use_container_width=True)
    if st.button("Ryd kurscache", use_container_width=True):
        cached_history.clear()
        st.success("Kurscache er ryddet. Scan igen for at hente nye data.")
    st.caption("Maks. 25 aktier pr. scanning for at skåne den gratis datakilde.")

    with st.expander("Update – GitHub"):
        st.caption("Opdaterer den lokale Python-scanner, ikke WordPress på hangar18.dk.")
        if not os.environ.get("STOCKSCANNER_ADMIN_TOKEN"):
            st.warning("Update er deaktiveret. Angiv STOCKSCANNER_ADMIN_TOKEN (mindst 20 tegn).")
        else:
            admin_token = st.text_input("Administratortoken", type="password", key="admin_update_token")
            if not authorized(admin_token):
                st.caption("Indtast administratortoken for at kontrollere opdateringer.")
            else:
                if st.button("Tjek GitHub-opdatering", use_container_width=True):
                    try:
                        st.session_state["github_update_status"] = check_update()
                    except Exception as error:
                        st.session_state.pop("github_update_status", None)
                        st.error(f"Update-kontrol fejlede: {error}")
                status = st.session_state.get("github_update_status")
                if status is not None:
                    st.write(f"Antal nye commits: {status.behind}")
                    st.caption(f"Lokal {status.current[:12]} · GitHub {status.remote[:12]}")
                    if status.behind > 0 and st.button("Backup og opdater nu", type="primary", use_container_width=True):
                        try:
                            backup_file = install_update(status.remote, admin_token)
                            st.session_state.pop("github_update_status", None)
                            st.success(f"Opdatering gennemført. Backup: {backup_file.name}")
                            st.info("Genstart Streamlit-processen for at indlæse den nye version.")
                        except Exception as error:
                            st.error(f"Update fejlede: {error}")

if do_scan:
    try:
        tickers = parse_tickers(raw_symbols)
    except ValueError as error:
        st.error(str(error))
    else:
        save_watchlist(tickers)
        scanned = []
        errors = []
        progress = st.progress(0.0, text="Scanner aktier")
        for index, symbol in enumerate(tickers, start=1):
            try:
                prices, currency = cached_history(symbol)
                scanned.append(analyze_prices(prices, symbol, currency))
            except Exception as error:
                errors.append(f"{symbol}: {error}")
            progress.progress(index / len(tickers), text=f"Scannet {index}/{len(tickers)}")
        progress.empty()
        st.session_state["results"] = scanned
        st.session_state["errors"] = errors
        if scanned:
            save_scans(scanned)

results = st.session_state.get("results", [])
errors = st.session_state.get("errors", [])

if errors:
    with st.expander(f"Fejl / manglende kursdata ({len(errors)})", expanded=not results):
        for error in errors:
            st.warning(error)

if results:
    sorted_results = sorted(results, key=lambda item: item.score, reverse=True)
    a, b, c = st.columns(3)
    a.metric("Analyserede aktier", len(sorted_results))
    b.metric("Score ≥ 80", sum(item.score >= 80 for item in sorted_results))
    c.metric("Gennemsnitlig score", round(sum(item.score for item in sorted_results) / len(sorted_results), 1))

    display = pd.DataFrame([
        {
            "Aktie": item.ticker,
            "Marked": market_of(item.ticker),
            "Dato": item.market_date,
            "Kurs": round(item.price, 2),
            "Valuta": item.currency,
            "21 dage %": round(item.change_21d_pct, 2),
            "RSI14": round(item.rsi14, 1),
            "Relativ volumen": round(item.relative_volume, 2) if item.relative_volume is not None else None,
            "Score / 100": item.score,
            "Signal": item.signal,
        }
        for item in sorted_results
    ])
    st.subheader("Resultater")
    st.caption("Kun valgte aktier fra overvågningslisten; ikke alle aktier på børserne.")
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.download_button(
        "Eksportér scanning (CSV)",
        display.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="AI-Stock-Scanner-resultater.csv",
        mime="text/csv",
    )

    symbol = st.selectbox("Detaljer for aktie", [item.ticker for item in sorted_results])
    selected = next(item for item in sorted_results if item.ticker == symbol)
    left, right = st.columns([2, 1])
    with left:
        st.subheader(f"{symbol} – kurs, SMA50 og SMA200")
        try:
            prices, _ = cached_history(symbol)
            close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
            series = pd.DataFrame({
                "Kurs": close,
                "SMA50": close.rolling(50).mean(),
                "SMA200": close.rolling(200).mean(),
            })
            st.line_chart(series.tail(260), use_container_width=True)
        except Exception as error:
            st.warning(f"Kunne ikke vise graf: {error}")
    with right:
        st.subheader("Hvorfor denne score?")
        st.metric("Teknisk score", f"{selected.score}/100")
        for criterion, passes in selected.checks.items():
            st.write(("✅ " if passes else "➖ ") + criterion)
        st.caption("Scoren er en regelbaseret screening, ikke en sandsynlighed for kursstigning.")

    with st.expander("Lokal Ollama-analyse (valgfri)"):
        model = st.text_input("Installeret Ollama-model", value="qwen3.5:9b")
        if st.button("Forklar scanningen med lokal AI"):
            try:
                with st.spinner("Ollama analyserer målingerne lokalt"):
                    st.write(explain(selected, model=model))
            except Exception as error:
                st.error(
                    "Ollama kunne ikke gennemføre analysen. Kontrollér at Ollama kører "
                    f"og modellen findes. Fejl: {error}"
                )
else:
    st.info("Vælg aktier i venstre side og klik på 'Scan nu'. Data hentes først ved scanning.")

with st.expander("Gemte scanninger (SQLite)"):
    history = recent_scans()
    if history.empty:
        st.caption("Ingen gemte scanninger endnu.")
    else:
        st.dataframe(history, hide_index=True, use_container_width=True)

with st.expander("Scoreregler og forbehold"):
    st.markdown(
        """
        | Kontrol | Point |
        |---|---:|
        | Kurs over SMA50 | 20 |
        | SMA50 over SMA200 | 20 |
        | RSI14 mellem 45 og 70 | 20 |
        | MACD over signallinjen | 20 |
        | Positivt 21-dages afkast | 10 |
        | Volumen mindst 20-dages gennemsnit | 10 |

        **80–100:** Interessant · **60–79:** Hold øje · **0–59:** Afvent.

        Kursdata leveres af en uofficiel Yahoo Finance-integration via yfinance.
        Data kan være forsinkede, mangelfulde eller midlertidigt utilgængelige.
        Justeringer af kurser kan påvirke historiske indikatorer.
        Ingen fundamental analyse, backtest eller automatisk handel indgår i V1.
        """
    )
