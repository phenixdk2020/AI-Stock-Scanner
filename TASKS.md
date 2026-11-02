# TASKS – AI-Stock-Scanner

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
- [ ] **Næste i fase 5: exit ved trendbrud** (SMA50/SMA200, evt. Supertrend) mod fast holdetid, målt på maks. drawdown og afkast.
- [ ] Fase 5 (oprindelig plan): Timing-zoner med egne regler + backtest. Copilot-review 02-11-2026 af `docs/MYSTOCKSCANNER-BULL-ENTRY-2026-11-02.md` afsnit 7: start med kun tre tests – A trendfilter alene (én trenddefinition, harmonisér 7.2 med `trend_context`), B + relativ styrke mod RSP, C med/uden tilbagerekyl. Urørt slutperiode, flere aktier inkl. afnoterede. Udskyd Supertrend-exit og positionsstørrelse. Kvalitetsfilteret kan ikke backtestes ærligt med yfinance (ingen filing-datoer; `altman_z` bruger nuværende market cap) – test det fremad med daterede snapshots.
- [ ] Fase 6: Playbook-side (app, derefter WordPress).
- [x] **Egen StockMap** (`stockscanner/stockmap.py`, 02-11-2026): RS mod RSP på ugebarer, EMA-udglattet, kvadranter, kompasvinkel, MSS' simple køb/salg-regel. Kalibreret (54 kombinationer): smooth 12 / vindue 40 / momentum 2 / EMA → 47 aktier 2019–2026: 60 % vindere, +5,3 %/handel, PF 2,2, median 14 uger (MSS oplyser ca. 60–65 %, 5,3 %, ~18 uger, PF 1,6–2,25); vinkler median 19° fra MSS, 8/9 inden for 45° (før 86°). Risiko for overfitting – genbekræft på nye observationer.
- [ ] **Fase 7: sammenligning med MSS** – `stockscanner/mss_compare.py`, `scan_cli.py --sammenlign-mss` (02-11-2026). Observationer i `data/mss_observations.csv` (lokalt, ikke i git). Første resultat, 9 aktier 30-10-2026: kvalitet rangkorrelation 0,27 (gns. 13 point fra); StockMap-vinkel median 86° fra (≈ tilfældigt) med RSP/SPY/URTH. MSS gav Novo "Købszone" uden optrend → deres timing er ikke ren trendfølge. **Allans trial udløber ca. 09–12-11-2026:** dagligt Export af en større watchlist + skærmbilleder af TPI/MTI-signalhistorik og StockMap. Importer bygges, når første eksportfil foreligger.
- [ ] Kvalitetstærskler: sektor-/branche-relativ scoring (i dag absolutte tærskler, ikke backtestet).

## Kendte forhold
- MyStockScanners formler er ikke offentlige; vi bygger egen åben model (se `docs/QUALITY-MODEL.md`).
- yfinance er uofficiel og har ca. 4 års årsregnskaber.
- MyStockScanner-research: `docs/Dropbox/` (emnelog T01–T66, restliste, datakatalog).
