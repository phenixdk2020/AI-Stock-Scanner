# Daytrader.dk – guide til daytrading: relevans for AI-Stock-Scanner

**Analyseret:** 2026-11-01  
**Kildedokument:** `/AI-Stock-Scanner/daytrading_guide-1.pdf` i brugerens Dropbox-mappe  
**Oprindelse:** Daytrader.dk, *Daytrading som hobby eller levevej*, opdateret maj 2024.  
**Mål:** Udvælge generelle, testbare principper til aktier i Danmark, Tyskland, Sverige, Norge og USA.

> Dette dokument er en selvstændig teknisk vurdering. Det er ikke en kopi af PDF'en, og der er ikke verificeret nogen historisk merperformance. Guiden omhandler overvejende CFD'er med gearing og kortsigtet handel. Vores projekt skal fortsat være en analyseservice, ikke et system til at handle gearede CFD'er.

## Centrale fund

- **Candlestick/OHLC:** Kursbjælker viser open, high, low og close. Vores nuværende enkle linjegraf bør suppleres med candlesticks, volumen og zoom.
- **Inside Bar:** Et konsolideringsmønster, hvor en bjælkes højeste/laveste kurs er indeholdt i den foregående bjælkes interval. Vigtig nuance: definér eksplicit om lige høj/lav accepteres.
- **Brud på interval:** Guidens eksempel søger et brud op over eller ned under mønsterets udvendige referencebjælke (mother bar), ikke blot et vilkårligt RSI-signal.
- **Stop-loss og take-profit:** Prisniveau, procent og samlet beløbsrisiko kan vises. Et stop kan blive udført dårligere end niveauet ved prisgab eller hurtige markedsbevægelser.
- **Omkostninger:** Spread, evt. kurtage, slippage og finansieringsomkostninger påvirker backtests. CFD-regler må ikke ukritisk anvendes på kontantaktier.
- **Tidshorisont:** Bogens eksempel bruger 15-minutterskurser og amerikanske åbningstider. Daglige/ugentlige candles kan også bruges som mønstre, men er **en anden strategi**, som skal testes separat.

## Forslag: selvstændig Inside Bar-detektor

Input: dags- eller ugedata med **Open, High, Low, Close, Volume**. Sammenlign forrige afsluttede candle (mother bar) med seneste afsluttede candle (inside bar).

1. `inside = inside_high < mother_high AND inside_low > mother_low` (strengt mønster – parameter for tilladte ligheder).
2. Først **efter** inside bar er lukket, oprettes overvågningsniveauer: `breakout_up = mother_high`, `breakout_down = mother_low`.
3. En ny **senere** candle kan bekræfte brud op eller ned. Ingen fremadskuende brug af samme candles lukkepris.
4. Separate filtre kan kræve positiv trend, relativ volumen og tilstrækkelig Risk/Reward.
5. Stop-/målberegning skal være en separat, parameterstyret funktion og ikke et løfte om eksekvering på en bestemt pris.
6. Backtesting bruger først næste tilgængelige handelspris efter et observerbart signal og håndterer gaps, omkostninger, udbytter, splits og forskellige børskalendere.

Eksempel på signaltilstande: **Intet mønster → Inside bar fundet → Afventer breakout → Bekræftet opad/nedad → Udløbet/annulleret**.

## Afgrænsninger for vores setup

- Gratis `yfinance` understøtter historiske OHLCV, men pålidelig og vedvarende **15-minutters historik** for alle fem markeder må ikke antages. Første version bør fokusere på **daglige candles** og eventuelt ugentlige.
- Ingen CFD-trading, gearing, broker-konti eller automatiske ordrer i denne funktion.
- Mønsteret er alene et screeningssignal. Det kræver data- og markedsvis backtesting og bør ikke automatisk give købsscore.
- Bevar adskillelsen mellem **Quality**, **Value** og **Timing**; Inside Bar hører udelukkende til Timing.

## Backlog (tilføjelse til videoanalysen)

| ID | Prioritet | Funktion | Acceptkriterium |
|---|---|---|---|
| DAY-01 | P1 | Inside Bar-mønstergenkendelse | Deterministiske tests af high/low, lighed og manglende OHLC |
| DAY-02 | P1 | Overvågning af efterfølgende breakout | Ingen look-ahead og klart tidsstemplet signal |
| DAY-03 | P1 | Visning i Plotly candlestick | Marker mother/inside bar og brudniveauer |
| DAY-04 | P1 | Risk/Reward med stop, mål og positionsrisiko | Håndtering af prisgab, omkostninger og valuta |
| DAY-05 | P2 | Historisk strategitest | In/out-of-sample, markedsindeks, transaktionsomkostninger og max drawdown |

## Ophavsret og kildekritik

Originalguiden er © Daytrader.dk. Dette dokument gengiver kun selvstændige tekniske konklusioner, ikke længere tekstpassager eller figurer. Guiden er fra 2024 og har introduktion til en handelsplatform og risici ved gearede CFD'er; den er ikke en uafhængig test af en profitabel strategi. Bogens risikoadvarsel fremhæver, at en stor andel af detailkunder taber penge på CFD'er.

**Status:** Analyse og forslag gemt; Inside Bar-funktionen er **ikke implementeret** i scannerkoden.
