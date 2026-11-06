# TASKS – AI-Stock-Scanner

> Samlet backlog med prioritet, kilde og "færdig når": **`docs/BACKLOG.md`**. Denne fil er logbogen.

Åbne punkter. Opdateres ved hver session (Allan 02-11-2026).

## I gang
- [x] Kode-commit `764d08c` (fase 1–2) lavet lokalt 02-11-2026. Ikke pushet.
- [x] Dokumentations-commit `efbd0db` med alle billeder; grenen pushet 02-11-2026 (Allan valgte "push alt alligevel" trods brugernavnet `allanm_ller` i `test-watchlist-beskrivelse.png`).
- [x] **Videoanalyse** 02-11-2026: 23 videoer skrevet ud med Whisper large-v3-turbo (`data/video-transcripts/`, ikke i git). Samlet i `docs/MYSTOCKSCANNER-BULL-ENTRY-2026-11-02.md` (udvælgelse, trend, timing, entry/exit, huller, forslag til fase 5). Stikprøver tjekket mod udskrifterne.
- [ ] MSS' kursus "Sådan bruges MyStockScanner" (appens lektioner) er ikke i videomappen – venter på Allan, hvis det skal med.

## Næste
- [x] Candle-detektor `stockscanner/candles.py` + `scan_cli.py --candles` (02-11-2026, 13 tests). Første backtest (20 aktier, 10 år, 0,1 % kurtage): kun **hammer** slår basis (+0,3/+0,5/+0,9 %-point ved 5/10/20 dage); Inside Bar-udbrud og lukning over top med volumen er under basis. Mangler: out-of-sample, flere aktier, signifikans (signaler overlapper), visning i appen (DAY-03).
- [x] Guide-handler (Daytrader.dk) på dagsdata: `trade_backtest` (købsstop over mother bar/signaltop, stop under mønsteret, evt. mål i R). Resultat 02-11-2026: 1 dag ≈ ingen edge; 20–60 dage stoppes 55–80 % ud og ligger 0,5–4,8 %-point under basis. Konklusion: guidens tætte daytrading-stop passer ikke til Playbook-timing (uger–måneder); candles bruges højst som udløser i en købszone med bredere stop/trendbrud som exit.
- [x] Kvalitetsvisningen prøvet i browser 02-11-2026 (MSFT 84,8 Stærk, ingen fejl).
- [ ] Fase 3: Pris/værdi (EPS × P/E-scenarier fra egen historik, værdiscore).
- [ ] Fase 4: Moat-tilnærmelse (stabile marginer, vedvarende ROIC).
- [x] Fase 5 A–C bygget (`stockscanner/regimes.py`, `scan_cli.py --regimer`, 02-11-2026): 47 aktier, 15 år. Ingen sikker merafkast ved køb i den urørte periode; trendfilter mindsker kun de værste udfald lidt. Se afsnit 9 i `docs/MYSTOCKSCANNER-BULL-ENTRY-2026-11-02.md`.
- [x] **Salgsregler (punkt 9)** – `stockscanner/exits.py`, `scan_cli.py --salg` (02-11-2026): Supertrend ×3 mest robust (samme afkast pr. tid som fast hold, ~40 % mindre værste udfald, holder i urørt periode); efter StockMap-køb er SMA50-brud bedre end MSS' StockMap-salg. Se afsnit 10 i bull/entry-dokumentet.
- [ ] Næste: forslag 1 (value trap-alarm via estimatrevisioner) og 5 (ingen køb tæt på regnskab); senere portefølje-simulering (forslag 11).
- [ ] ~~Næste i fase 5: exit ved trendbrud~~ (gjort i punkt 9) (SMA50/SMA200, evt. Supertrend) mod fast holdetid, målt på maks. drawdown og afkast.
- [ ] Fase 5 (oprindelig plan): Timing-zoner med egne regler + backtest. Copilot-review 02-11-2026 af `docs/MYSTOCKSCANNER-BULL-ENTRY-2026-11-02.md` afsnit 7: start med kun tre tests – A trendfilter alene (én trenddefinition, harmonisér 7.2 med `trend_context`), B + relativ styrke mod RSP, C med/uden tilbagerekyl. Urørt slutperiode, flere aktier inkl. afnoterede. Udskyd Supertrend-exit og positionsstørrelse. Kvalitetsfilteret kan ikke backtestes ærligt med yfinance (ingen filing-datoer; `altman_z` bruger nuværende market cap) – test det fremad med daterede snapshots.
- [ ] Fase 6: Playbook-side (app, derefter WordPress).
- [x] **Egen StockMap** (`stockscanner/stockmap.py`, 02-11-2026): RS mod RSP på ugebarer, EMA-udglattet, kvadranter, kompasvinkel, MSS' simple køb/salg-regel. Kalibreret (54 kombinationer): smooth 12 / vindue 40 / momentum 2 / EMA → 47 aktier 2019–2026: 60 % vindere, +5,3 %/handel, PF 2,2, median 14 uger (MSS oplyser ca. 60–65 %, 5,3 %, ~18 uger, PF 1,6–2,25); vinkler median 19° fra MSS, 8/9 inden for 45° (før 86°). Risiko for overfitting – genbekræft på nye observationer.
- [x] Værktøjsanalyse af 69 videoer: `docs/MYSTOCKSCANNER-VAERKTOEJER-2026-11-02.md` (02-11-2026). Facitliste `data/mss_video_observations.csv` (435 rækker, lokalt). MSS-score = middel af Quality, Value, Moat (tjekket på 9 aktier, afvigelse ≤ 0,7).
- [x] **Værdikanal** (`stockscanner/valuation.py`, `scan_cli.py --vaerdi`, 02-11-2026): EPS-sti (seneste regnskab → 0y → +1y, fremskrevet) × P/E bear/base/bull = base ±20 % (passer med MSS' eksempler Vestas, CoreCivic, Micron, GN, Pandora, Nvidia). Base = median af 3/5/10-års gennemsnit af årlige median-P/E, år uden for 3–60 udelades. Score 100 = bear, 0 = bull, ikke afkortet; variant "i dag" og "horisont". PEG, implicit P/E, asymmetri. Afviser inkonsistente yfinance-estimater (SOBI, innoscripta, Netcompany). Mod MSS' watchlist-Value (6 aktier): rangkorr 0,54 – men det er uafklaret, om den kolonne er kanalscoren eller percentil af nøgletal (percentil-test gav 0,72 på 9, men Schneider = 100 modsiger). Afgøres med C25-skærmbilleder.
- [x] Høstning af 318 danske aktier færdig 02-11-2026 → `data/mss_playbook_dk_part1/2.json`, analyse i `data/mss_playbook_dk_analyse.csv` og `data/mss_band_rule.csv`. Bekræftet: MSS = middel(Q,V,M); kanal symmetrisk; værdiscore = placering i dag. Båndbredde varierer (median ±31 %), regel ikke fundet (kræver 10 års P/E). Se afsnit 8 i værktøjsdokumentet.
- [x] Quality-percentil (`stockscanner/quality_rank.py`, 02-11-2026): 11 MSS-lignende delmål, lige vægt, percentil i universet → rangkorr 0,73 mod 115 høstede danske MSS-Q (faste tærskler: 0,65). Bedste delmål: ROCE, ROIC, rentedækning, ROA, Piotroski.
- [x] Værdikanal: MSS' båndregel bygget ind (`band_rule="minmax"`: bear/bull = laveste/højeste af 3/5/10/20-års gns. og nuværende P/E, base = midtpunkt; kilde "Nye features i valuegrafen" 0:02:45). Kræver 10–20 års EPS-historik for at virke; yfinance har ~4 år → næste: SEC EDGAR (gratis, USA).
- [x] SEC EDGAR (`stockscanner/sec_edgar.py`, 02-11-2026): årlig EPS fra 2007/08 for amerikanske aktier (gratis, cache i `data/sec/`, splitjusteret); `valuation.fetch_inputs` forlænger P/E-historikken til ~19 år. Båndreglen kalibreret mod 113 høstede US-kanaler (`data/mss_us_channels.csv`): median af daglig P/E over 1/3/5/10/20 år + nuværende → rangkorr 0,70 for bear/bull-forholdet (før 0,37). Valgfri kontakt: miljøvariabel `SEC_USER_AGENT`.
- [!] **Høstning stoppet 02-11-2026 ca. 15:45:** efter ~1100 sidevisninger på få timer svarede MSS med fejl og derefter "You are not authorised to perform this action"; forsiden tilbyder ny 14-dages trial → trial-adgangen er sandsynligvis trukket tilbage pga. automatisk høstning. Ingen yderligere adgang. Data sikret: `data/mss_playbook_dk_part1/2.json` (318 DK), `data/mss_playbook_checkpoint_500.json` (501 US + 183 DK), `..._739.json`, og `mss_playbook_final.json` (562, fra browserens lager – skal flyttes fra Overførsler). Lærdom: høst aldrig i dette tempo igen; MSS' vilkår forbyder sandsynligvis automatisering.
- [x] TPI-lite (`stockscanner/tpi_lite.py`): oversolgte uger giver ca. dobbelt gennemsnitsafkast over 5–20 dage (holder i urørt periode); lang grøn trend tilføjer lidt ved 130 dage.
- [x] Value- og Momentum-percentiler (`stockscanner/scores.py`), samme faktorer som MSS' Stock Scores.
- [x] Mandagsliste (`stockscanner/weekly_list.py`, `scan_cli.py --mandagsliste`): ramte MSS' mandag 02-11-2026 (IVSO salg, ENTG køb, LTMC køb). Kun afsluttede uger tæller. Mangler: percentiler mod et stort univers i stedet for listen selv; salg kun for ejede aktier (portefølje-fil).
- [x] Overvågning af research-aktierne (`data/research_watchlist.txt`): Windows-opgaven "AI-Stock-Scanner mandagsliste" kører `scripts/mandagsliste.cmd` hver mandag kl. 8 (oprettet 02-11-2026 med Allans OK, testkørt OK). Output: `data/mandagsliste_<dato>.csv`, `data/mandagsliste_historik.csv`, log i `data/mandagsliste.log`.
- [x] Punkt 1–7 og 9 fra planen 02-11-2026: univers-percentiler (316 aktier, `data/universe.txt`, cache `data/universe_factors.csv`, opdateres ugentligt), portefølje (`data/portfolio.csv`, kun ejede får salgsregler), MTI-lite (`stockscanner/mti_lite.py`), Moat-tilnærmelse + MSS-score (rangkorr 0,70 mod MSS Moat), markedsindeks, porteføljesimulering (`scripts/simulate_portfolio.py`: StockMap-regler 12,5 % CAGR / −25 % fald mod RSP 13,6 % / −37 %), Streamlit-side `pages/1_Mandagsliste.py`, PR til main.
- [ ] Punkt 8 udsat (Allan 02-11-2026): nordisk 10–20 års P/E-historik kræver betalt kilde (Børsdata/FMP) – venter.
- [ ] Idéer: sektor-del af MTI; simulering med point-in-time-kvalitet hvis data findes; ugentlig e-mail/notifikation med ÆNDRING-linjer.
- [ ] Næste: ~~Quality-percentil mod de 182 høstede Q-scorer;~~ ret `valuation.py` (score i dag, bredere bånd); evt. høst flere markeder (SE/NO/DE/US) mens trial varer.
- [ ] ~~**Høstning fra MSS (Allan gav lov 02-11-2026, "massehøstning"):** Playbook-siderne for 318 danske aktier læses i den indbyggede browser (indlogget trial) → `data/mss_playbook_dk.json` (lokalt, ikke i git). Fund: valuegrafens linjer er symmetriske om base (bear = base − d, bull = base + d i P/E); værdiansættelsesscoren = placering i kanalen I DAG (horisont-linjer ÷ EPS-vækst), ikke ved horisonten. Risiko: MSS' vilkår kan forbyde automatisk høstning.
- [ ] Kendte datahuller: yfinance har kun 4 års årsregnskaber (ingen 5/10-års P/E) og kun 0y/+1y-estimater; Pandoras +1y-estimat (48) ser forkert ud.
- [ ] **Byggeplan (afsnit 5):** 1) ~~værdikanal + værdiscore + PEG~~ (bygget), 2) StockMap-zoner/tilstandsmaskine, 3) Quality-percentil + Moat + MSS-score, 4) regelpakke (SMA-exit, Supertrend, regressionskanal, positionsstørrelse), 5) MTI-lite. Udskudt: TPI, MTX, algostrategier.
- [ ] **Allans dataindsamling inden trial udløber** (afsnit 6): screener-lister, StockMap- og værdikanal-skærmbilleder, fast watchlist fredag+mandag, hjælpetekster, hele C25 én dag.
- [x] MSS' mandagshandler 02-11-2026 (salg IVSO; køb LTMC, ENTG, JLL, RTX) → `data/mss_signal_observations.csv`. Vores ugentlige StockMap: IVSO-salg og ENTG-køb i præcis samme uge, de tre andre køb 1–2 uger før. Deres proces: "MSS world daily scan" (>100) → høj interest coverage, lav PEG (35–40) → manuel udvælgelse (4). Gem fremtidige mandagsmails i samme fil.
- [ ] **Fase 7: sammenligning med MSS** – `stockscanner/mss_compare.py`, `scan_cli.py --sammenlign-mss` (02-11-2026). Observationer i `data/mss_observations.csv` (lokalt, ikke i git). Første resultat, 9 aktier 30-10-2026: kvalitet rangkorrelation 0,27 (gns. 13 point fra); StockMap-vinkel median 86° fra (≈ tilfældigt) med RSP/SPY/URTH. MSS gav Novo "Købszone" uden optrend → deres timing er ikke ren trendfølge. **Allans trial udløber ca. 09–12-11-2026:** dagligt Export af en større watchlist + skærmbilleder af TPI/MTI-signalhistorik og StockMap. Importer bygges, når første eksportfil foreligger.
- [ ] Kvalitetstærskler: sektor-/branche-relativ scoring (i dag absolutte tærskler, ikke backtestet).

## Kendte forhold
- MyStockScanners formler er ikke offentlige; vi bygger egen åben model (se `docs/QUALITY-MODEL.md`).
- yfinance er uofficiel og har ca. 4 års årsregnskaber.
- MyStockScanner-research: `docs/Dropbox/` (emnelog T01–T66, restliste, datakatalog).

## 06-11-2026: entry-tjek og candles (plugin 0.8.10)
- [x] `scan_cli.py --entry-tjek`: opdaterer Entry for fulgte, ikke-ejede aktier i seneste playbook. StockMap følger afsluttede uger, så tjekket fanger kun kurs, værdikanal, regnskab og estimater. Ingen GPU, nyheder eller papirhandler. Candle-mønstre vises kun som oplysning.
- [ ] Windows-opgaven til `scripts/entry_tjek.cmd` (tirsdag-lørdag, indhenter når PC'en tændes) oprettes efter fletning.

## 06-11-2026: Aktiescanner ud af menuen (plugin 0.8.9)
- [x] Siden var en kort udgave af Playbook → Mandagsliste. Fjernet fra menu, Overblik og Hjælp; shortcoden `[ai_stock_scanner]` og snapshot-data er bevaret (Overblik og Analyse bruger dem). Allan valgte det 06-11-2026.

## 05-11-2026: støtte til analyse og entry (plugin 0.8.8, ikke committet ved skrivning)
- [x] Entry-tjekliste og plan på aktiesiden, advarsel ved svagt marked, regnskabsdatoer fra regnskabslisten, anslået dato som advarsel, stigende estimater, insiderkøb (Yahoo, kun USA), Hvorfor er den billig (lokal AI). Ingen af dem ændrer købsreglerne.
- [x] B-17 backtest: `docs/B17-ENTRY-BACKTEST.md`. Kvalitet og værdi oven på StockMap gav lavere afkast; simulate() vælger alfabetisk, så rangering efter score er ikke testet.
- [ ] Næste: gentag B-17 med rangering efter score (Samlet) i stedet for alfabetisk.
- [ ] SEC Form 4 direkte (`insiders.fetch_sec`) kræver SEC_USER_AGENT med kontaktoplysninger; afventer Allan. Danske insiderkøb er ikke dækket.
