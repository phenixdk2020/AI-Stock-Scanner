# TASKS – AI-Stock-Scanner

Åbne punkter. Opdateres ved hver session (Allan 02-11-2026).

## I gang
- [x] Kode-commit `764d08c` (fase 1–2) lavet lokalt 02-11-2026. Ikke pushet.
- [x] Dokumentations-commit `efbd0db` med alle billeder; grenen pushet 02-11-2026 (Allan valgte "push alt alligevel" trods brugernavnet `allanm_ller` i `test-watchlist-beskrivelse.png`).
- [ ] **Videoanalyse:** `D:\AI-Stock-Scanner videos` (24 filer, 1,2 GB). 10 af dem er delvist set ud fra stillbilleder i `docs/MYSTOCKSCANNER-VIDEOANALYSE-2026-11-01.md`, og intet er transskriberet. Whisper large-v3-turbo godkendt til download 02-11-2026 (Wan2GP-venv). Næste: transskribér, opsummér værdiansættelse/kvalitet/timing med lokal AI.

## Næste
- [x] Candle-detektor `stockscanner/candles.py` + `scan_cli.py --candles` (02-11-2026, 13 tests). Første backtest (20 aktier, 10 år, 0,1 % kurtage): kun **hammer** slår basis (+0,3/+0,5/+0,9 %-point ved 5/10/20 dage); Inside Bar-udbrud og lukning over top med volumen er under basis. Mangler: out-of-sample, flere aktier, signifikans (signaler overlapper), visning i appen (DAY-03).
- [x] Guide-handler (Daytrader.dk) på dagsdata: `trade_backtest` (købsstop over mother bar/signaltop, stop under mønsteret, evt. mål i R). Resultat 02-11-2026: 1 dag ≈ ingen edge; 20–60 dage stoppes 55–80 % ud og ligger 0,5–4,8 %-point under basis. Konklusion: guidens tætte daytrading-stop passer ikke til Playbook-timing (uger–måneder); candles bruges højst som udløser i en købszone med bredere stop/trendbrud som exit.
- [x] Kvalitetsvisningen prøvet i browser 02-11-2026 (MSFT 84,8 Stærk, ingen fejl).
- [ ] Fase 3: Pris/værdi (EPS × P/E-scenarier fra egen historik, værdiscore).
- [ ] Fase 4: Moat-tilnærmelse (stabile marginer, vedvarende ROIC).
- [ ] Fase 5: Timing-zoner med egne regler + backtest (bruger candle-detektoren).
- [ ] Fase 6: Playbook-side (app, derefter WordPress).
- [ ] Fase 7: Fornuftstjek mod MyStockScanners tal for de 9 researchaktier (ikke kopiering).
- [ ] Kvalitetstærskler: sektor-/branche-relativ scoring (i dag absolutte tærskler, ikke backtestet).

## Kendte forhold
- MyStockScanners formler er ikke offentlige; vi bygger egen åben model (se `docs/QUALITY-MODEL.md`).
- yfinance er uofficiel og har ca. 4 års årsregnskaber.
- MyStockScanner-research: `docs/Dropbox/` (emnelog T01–T66, restliste, datakatalog).
