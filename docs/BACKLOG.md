# Backlog – AI-Stock-Scanner

Samlet liste over funktioner: hvad der er bygget, hvad der mangler, og hvorfor. Opdateret 02-11-2026 (v0.8).
Kilder: MSS-videoerne (`docs/MYSTOCKSCANNER-VAERKTOEJER-2026-11-02.md`, `docs/MYSTOCKSCANNER-BULL-ENTRY-2026-11-02.md`),
egne backtests og MSS' mandagsmail 02-11-2026. [MSS] = MyStockScanner, [MT] = MarketTimer.dk.

Prioritet: **P1** høj værdi / lav indsats, **P2** middel, **P3** lav eller svær. Indsats: S (timer), M (1–2 dage), L (flere dage).

---

## 1. Næste (åbne)

| ID | Funktion | Prio | Indsats | Kilde | Færdig når |
|---|---|---|---|---|---|
| B-23 | **Vurdér papirstillingen mod RSP og spredningsadvarslen** | P2 | Lille | 04-11-2026 | Tidligst efter 3 måneder (papirhandlerne startede 02-11-2026): læs `data/papir_stilling.csv` (forskel i %-point, antal sammenlignede handler); slår reglerne RSP efter udeladte handler og valuta? Vurdér også, om grænserne i spredningsadvarslen (flere end 3 / over 40 %, mindst 4) er fornuftige, når universet har sektorer. |
| B-22 | **Vurdér regnskabsrisikoen ud fra loggen** | P2 | Lille | 04-11-2026 | Efter 2-3 regnskabssæsoner: sammenlign `data/regnskabsrisiko_log.csv` (niveau, point, begrundelser) med `udfald_pct` (faktisk bevægelse). Punkt 1 (sænkede estimater) og punkt 2 (negative nyheder) kan IKKE backtestes, fordi vi ikke har gamle estimater og nyheder; kun punkt 3 (kursen steget 15 % på 30 dage) kan prøves bagud på kurser. Justér først point og grænser, når loggen viser en sammenhæng |

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
| Screenere Triple Green, TPI-trend, Stock of the Day (B-04–B-06) | `screeners.py`, `scan_cli.py --screener` | 15 / 3 / 0 hits af 316 den 02-11-2026; uge/dag-grøn er vores tilnærmelse |
| Percentiler pr. region (B-19) | `universe.percentiles(by_region=True)`, `--region` | USA/Norden/Europa hver for sig |
| Positionsstørrelse (B-09) | `sizing.py`, indstillinger på siden | Risiko 0,75 %, stop 3 × ATR, loft 3 %; antal og stop på køb-kandidater |
| Papirportefølje (B-14) | `paper.py`, `data/papir_portefolje.csv` | Køb-kandidater købes på papir, samme salgsregler; starter 02-11-2026 |
| Windows-besked med ÆNDRING-linjer (B-13) | `scripts/notify.ps1`, `mandagsliste.cmd` | Toast mandag efter listen |
| Visa i SEC-opslag (B-18) | `sec_edgar.py` (SEC's ticker-liste) | `cik_for("V")` = 1403161 |
| Regressionskanal som salg (B-08) – testet, ikke taget i brug | `regression.py`, `scripts/study_b08_b12.py` | Værste 5 % 2–3 × dårligere end Supertrend ×3 (dok. afsnit 12) |
| ADX > 25 som filter (B-12) – testet, ikke taget i brug | `regression.adx` | Ingen konsekvent forbedring, færre handler |
| Nyhedsscanner (B-20) | `news.py`, `scan_cli.py --nyheder`, mandagsliste, hjemmeside 0.6.1 | Google News RSS + lokal Ollama; STOR NEGATIV NYHED blokerer køb kun når de negative er flest (1 af 10 den 02-11-2026) |
| Tragt: scan hele universet (B-21) | `universe.buy_funnel`, `t_stockmap` i universet, mandagslisten | StockMap-køb + Quality ≥ 60 i de 316 → fuld analyse; ★ på hjemmesiden |
| Størrelses- og likviditetskategorier (04-11-2026) | `universe.size_class/liquidity_class/liquidity_facts`, `weekly_list.classify`, plugin 0.7.1 | Mega–Micro og Høj/Middel/Lav (21 dages gns. omsætning i USD; Lav < 2 mio. eller over 2 dage uden handel). Lav blokerer køb-kandidat ("for lidt handel") og tragten; ejede aktier rammes ikke. Vist i playbook, universet, filter på Aktie-scores og simulatorens opslag ("en dags handel", advarsel under ca. 14 mio. kr.). Universet skal genopbygges for at få x_adv_usd; indtil da gælder reglen kun via mandagslistens egne kurshistorikker |
| Regnskabsnedtælling og regnskabsrisiko (04-11-2026) | `earnings_risk.py`, `weekly_list.build_rows`, `playbook.earnings_risk_entry`, plugin 0.7.1 | Nedtælling "11-11-2026 (om 7 dage)" beregnes ved hver sidevisning (rød inden for 7 dage, KØB-KANDIDAT får "spærret: regnskab"; manglende dato = "Dato ukendt"). Køb-kandidat uden kendt dato forbliver kandidat med begrundelsen "regnskabsdato ukendt" (blokerer ikke; ejede aktier uberørt). Regnskabsrisiko fra 14 dage før regnskab: sænkede estimater, flest negative nyheder, kurs +15 % på 30 dage → Lav/Middel/Høj; ændrer aldrig handling eller salgsregler. Logges i `data/regnskabsrisiko_log.csv` med faktisk udfald. Kun advarsel: "Risikomål, ikke et salgssignal." |
| Samlet aktieside (04-11-2026) | `class-asc-stock-page.php`, `[ai_stock_page]`, menupunktet Aktie, `ASC_Market_Quotes::history/stock_chart`, plugin 0.8.0 | Symbolet er et link i alle tabeller; søgefelt på symbol eller navn (dansk katalog + playbook-aktier), også aktier man ikke følger. Kurs, ændring siden forrige lukkekurs, serverrenderet SVG-candlegraf med volumen, SMA50/SMA200 (beregnet på al historik), perioder 1m/6m/1y/5y (5y i uger) og markører for egne køb og salg. Lang historik (range=5y) har egen 6-timers cache og cooldown; fejler den, bruges 6 måneder fra kursopslaget og det siges. Playbook-analyse, regnskab, salgsregel og nyheder, knapper Følg / Køb i simulator / Registrér køb |
| Sektor pr. aktie og spredningsadvarsel (04-11-2026) | `universe.info_extras` (`x_sector`), `sector_rs.sector_name/sector_da`, `playbook.py`, `ASC_Playbook::concentration_warning`, plugin 0.8.4 | Kolonnen Sektor i Find aktier og på mandagslisten; advarsel hvis flere end 3 eller over 40 % af aktierne med entry ligger i samme sektor, og over 40 % af egne positioner (mindst 4) i simulator og portefølje. Blokerer intet. Universets `x_sector` kommer med ved næste kørsel af `build_universe.py`; indtil da bruges `data/sector_map.json` |
| Papirporteføljens stilling mod RSP (04-11-2026) | `paper.score/log_score`, `data/papir_stilling.csv`, `paper_score` i payloaden, plugin 0.8.4 | Antal handler, gns. afkast mod RSP i samme perioder, forskel i %-point, vinderandel og startdato; "Under 3 måneder siger tallene ikke noget."; afkast i aktiens egen valuta; handler uden RSP-kurs udelades og tælles |
| Kurser hvert 15. min på hjemmesiden | `ASC_Market_Quotes` (WP-Cron + auto-genindlæsning) | Kræver at "Yahoo-kurser" er slået til i WordPress-admin |
| Sektor-bekræftelse af StockMap og MTI-sektor (B-07, B-11) – testet, ikke krav | `sector_rs.py`, `scripts/study_b07_b11.py` | Effekt inden for støj; MTI-sektor mindsker kun værste 5 % (docs/RESULTAT-B07-B11.md) |
| De fire algostrategier (B-10) | `strategies.py`, `scripts/study_b10.py`, `scripts/strategies_monthly.py` | Kun pris-delene kan bagtestes: momentum 24 %/år mod RSP 13 % (overlevelsesbias!); QM/TPI+/VM/VQ spores fremad fra 03-11-2026 (docs/RESULTAT-B10.md) |
| Kalibrering mod videoernes facitliste (B-15) | `calibration.py`, `scripts/calibrate_b15.py` | MTI-lite 11/12 og TPI lang trend 8/9 stemmer; StockMap/værdikanal for få data (docs/RESULTAT-B15.md) |
| TPI fuld metode, analog (B-16) – testet, ikke taget i brug | `tpi_analog.py`, `scripts/study_b16.py` | Slår ikke TPI-lite i urørt periode (12,2 % mod 13,8 %) (docs/RESULTAT-B16.md) |
| Playbook på aktier.hangar18.dk (B-17) | plugin 0.6.x, `playbook.py`, `site_sync.py` | Automatisk upload efter hver kørsel |
| Salgsregel: kun brud efter købsdatoen | `portfolio.exit_check`, plugin | Rettet 03-11-2026: Supertrend tæller kun, hvis den vender ned efter købet |
| Aktiesimulator: virtuel konto, køb/salg, 30-dages runde mod RSP | `class-asc-simulator.php`, `[ai_stock_simulator]`, plugin 0.7.0 | Kurser fra Yahoo, 0,1 % i omkostning pr. handel; adskilt fra den rigtige portefølje |
