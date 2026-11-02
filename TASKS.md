# TASKS – AI-Stock-Scanner

Åbne punkter. Opdateres ved hver session (Allan 02-11-2026).

## I gang
- [x] Kode-commit `764d08c` (fase 1–2) lavet lokalt 02-11-2026. Ikke pushet.
- [x] Dokumentations-commit `efbd0db` med alle billeder; grenen pushet 02-11-2026 (Allan valgte "push alt alligevel" trods brugernavnet `allanm_ller` i `test-watchlist-beskrivelse.png`).
- [ ] **Videoanalyse:** `D:\AI-Stock-Scanner videos` (24 filer, 1,2 GB). 10 af dem er delvist set ud fra stillbilleder i `docs/MYSTOCKSCANNER-VIDEOANALYSE-2026-11-01.md`, og intet er transskriberet. Whisper large-v3-turbo godkendt til download 02-11-2026 (Wan2GP-venv). Næste: transskribér, opsummér værdiansættelse/kvalitet/timing med lokal AI.

## Næste
- [ ] **Candle-detektor (timing, punkt 3):** Inside Bar-udbrud, bullish engulfing, hammer, morning star, lukning over forrige top med volumen. Kun tæller i optrend/efter tilbagerekyl. Backtest 5/10/20 dage mod tilfældig dag, signal ved lukning og køb næste åbning, kurtage med. Se `docs/DAYTRADER-INSIDE-BAR-2026-11-01.md` (DAY-01–05). Afventer Allans OK.
- [ ] Kvalitetsvisningen i Streamlit-appen er ikke prøvet i en browser.
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
