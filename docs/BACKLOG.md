# Backlog – AI-Stock-Scanner

Samlet liste over funktioner: hvad der er bygget, hvad der mangler, og hvorfor. Opdateret 02-11-2026.
Kilder: MSS-videoerne (`docs/MYSTOCKSCANNER-VAERKTOEJER-2026-11-02.md`, `docs/MYSTOCKSCANNER-BULL-ENTRY-2026-11-02.md`),
egne backtests og MSS' mandagsmail 02-11-2026. [MSS] = MyStockScanner, [MT] = MarketTimer.dk.

Prioritet: **P1** høj værdi / lav indsats, **P2** middel, **P3** lav eller svær. Indsats: S (timer), M (1–2 dage), L (flere dage).

---

## 1. Næste (åbne)

| ID | Funktion | Prio | Indsats | Kilde | Færdig når |
|---|---|---|---|---|---|
| B-04 | **Screener: Triple Green** (lang + uge + dag grøn, markedsværdi ≥ 2 mia.) | P2 | M | [MSS] H1 | `scan_cli.py --screener triple-green` over universet |
| B-05 | **Screener: TPI-trend** (lang grøn + uge oversolgt, ≥ 25 mia., DK/NO/SE) | P2 | M | [MSS] H1 | Som B-04 |
| B-06 | **Screener: Stock of the Day** (lang grøn + uge oversolgt + analytiker-upside ≥ 10 % + ≥ 10 mia.) | P2 | M | [MSS] H8 | Som B-04 |
| B-07 | **StockMap-bekræftelse fra branche/sektor** (sektor-ETF eller -indeks tipper også op) | P2 | M | [MSS] G5, Playbook-siden | Vinkel for sektor i listen; backtest med/uden krav |
| B-08 | **Regressionskanal som salgsregel** (±2σ, R ≥ 0,9, brud nedad) | P2 | M | [MSS]/[MT] G8, H9, H10 | Med i `exits.py`-studiet; sammenlign med Supertrend |
| B-09 | **Positionsstørrelse**: 0,5–1 % risiko pr. handel, stop = ATR(14) × 3, maks. 2,5–3,3 % pr. aktie | P2 | S | [MSS]/[MT] "Styr din risiko", H13 | Antal aktier pr. køb-kandidat i listen, ud fra porteføljens størrelse |
| B-10 | **De fire algostrategier** (Quality Momentum, TPI Plus, Value Momentum, Value Quality; top 15, månedlig) | P2 | L | [MSS] "Profitable strategier", strategy mixer, månedsopdatering (lydspor 505255aa…) | Momentum-varianter backtestet ærligt med 1,5 %/år i handelsomkostninger; Quality/Value kun fremad (papirportefølje); valg af 5 eller 15 aktier pr. strategi |
| B-11 | **MTI sektor-del** (relativ styrke mod sektor ud over hjemmeindeks) | P2 | M | [MSS] G-dokument 3.7 | `mti_lite` med sektor; test |
| B-12 | **ADX > 25 som trendfilter** | P3 | S | [MT] H9 | Backtest i `regimes`/`exits` med og uden filter |
| B-13 | **Ugentlig notifikation** med ÆNDRING-linjer (Windows-toast eller e-mail) | P2 | S | Allan | Besked mandag morgen når noget skifter |
| B-14 | **Papirportefølje fremad**: log mandagslistens køb/salg og mål afkast uge for uge | P2 | M | — | `data/papir_portefolje.csv` + rapport i appen |
| B-15 | **Kalibrér mod facitlisten** (1180 video-observationer): brug dem med dato som stikprøver | P3 | M | `data/mss_video_observations.csv` | Rapport over hvor mange signaler/zoner vi rammer |
| B-16 | **TPI fuld metode** (sammenligning med 20–30 års mønstre i aktiens egen historik) | P3 | L | [MSS] H4, H6 | Analog-model; skal slå TPI-lite i urørt periode |
| B-17 | **WordPress Playbook-side** (fase 6) | P3 | L | TASKS | Side på hangar18.dk med mandagslisten |
| B-18 | **Visa i SEC-opslag** (kort ticker "V" giver forkert CIK) | P3 | S | Egen fejl | `cik_for("V")` giver Visa; test |
| B-19 | **Percentiler pr. region** (DK/Norden/Europa/USA hver for sig, som MSS) | P2 | S | [MSS] "Stock Scores" | Valg i `universe.percentiles`; sammenlign med høstede tal |

## 2. Udsat

| ID | Funktion | Hvorfor |
|---|---|---|
| U-01 | **Nordisk 10–20 års P/E-historik** (Børsdata eller FMP) | Koster penge – Allan 02-11-2026: venter |
| U-02 | **MTX** (Momentum Trend Explosion) | Ingen beskrivelse i nogen video |
| U-03 | **Mere data fra MSS** | Trial lukket 02-11-2026 efter automatisk høstning; ingen ny konto |
| U-04 | **Point-in-time-backtest af Quality/Value** | Kræver historiske regnskaber med offentliggørelsesdato |

## 3. Bygget (02-11-2026)

| Funktion | Modul | Resultat |
|---|---|---|
| Kvalitetsscore (faste tærskler) | `quality.py`, `fundamentals.py` | Rangkorr 0,65 mod MSS |
| Quality som percentil | `quality_rank.py`, `universe.py` | Rangkorr 0,73 (115 DK) |
| Moat-tilnærmelse + MSS-score | `quality_rank.py` | Moat rangkorr 0,70 (131 DK) |
| Value og Momentum som percentiler | `scores.py` | Ikke kalibreret (intet facit) |
| Sammenligningsunivers 316 aktier + markedsindeks | `universe.py`, `scripts/build_universe.py` | Opdateres ugentligt |
| Værdikanal, score i dag, PEG, implicit P/E | `valuation.py` | P/E-bånd rangkorr 0,70 (113 US) |
| SEC EDGAR EPS-historik | `sec_edgar.py` | ~19 års P/E for US |
| StockMap (ugebarer, RSP) | `stockmap.py` | Vinkler median 19° fra MSS; ramte 5/5 mandagshandler |
| TPI-lite | `tpi_lite.py` | Oversolgt ≈ 2 × gns. afkast 5–20 dage |
| MTI-lite (hjemmeindeks) | `mti_lite.py` | "Dobbelt grøn" |
| Candle-detektor + Daytrader-handler | `candles.py` | Kun hammer slår basis; tætte stop dårlige |
| Regimer A–C | `regimes.py` | Ingen sikker merafkast ved køb |
| Salgsregler | `exits.py` | Supertrend ×3 mest robust |
| Porteføljesimulering | `simulation.py`, `scripts/simulate_portfolio.py` | 12,5 % / −25 % mod RSP 13,6 % / −37 % |
| Mandagsliste + historik + portefølje | `weekly_list.py`, `portfolio.py`, `scan_cli.py --mandagsliste` | Windows-opgave mandag kl. 8 |
| Streamlit-side | `pages/1_Mandagsliste.py` | Liste, historik, research-liste, portefølje |
| UI-røgtest | `scripts/ui_smoke.py`, Playwright | Grøn |
| Køb-filtre: regnskab ≤ 7 dage, value trap (EPS-estimat −2 %/30 d eller −5 %/90 d), asymmetri ≥ 3 (B-01–B-03) | `analyst.py`, `weekly_list.py` | Kørt på research-listen 02-11-2026; 1INN.DE fik value trap-flag |
