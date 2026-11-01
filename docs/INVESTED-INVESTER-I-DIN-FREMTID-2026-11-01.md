# Invested.dk – Invester i din fremtid: Analyse til AI-Stock-Scanner

**Analyseret:** 1. november 2026  
**Bog:** *Invester i din fremtid – Grundbog i investering for alle* af Christian Jain Kongsted og Erik Bork, Invested.dk, 2021.  
**Kilde:** Dropbox: /AI-Stock-Scanner/E-bog-Invester-i-din-fremtid-2021_02.pdf (ca. 1,7 MB).  
**Projekt:** https://github.com/phenixdk2020/AI-Stock-Scanner  
**Markeder:** Danmark, Tyskland, Sverige, Norge og USA.

> Denne fil er en selvstændig analyse af bogen, ikke en kopi. Sidetal refererer til bogens trykte sider. Bogens historiske afkast og investeringsråd er ikke uafhængigt valideret. Ingen automatiske køb/salg anbefales.

## Konklusion

Bogen er et godt supplement til vores tidligere Daytrader Inside Bar-analyse. Her kombineres **fundamental virksomhedsanalyse**, **værdiansættelse**, **teknisk timing**, **risikostyring** og et passivt alternativ med brede indeks. Vi bør derfor udvikle to separate arbejdsprofiler:

1. **Langsigtet aktieinvestering:** Quality, Value, porteføljediversificering, benchmark og løbende investering.
2. **Swing/aktiv screening:** Trend, RSI, SMA200, støtte/modstand, breakout, stop-loss og Risk/Reward.

Scores for Quality, Value og Timing skal vises separat. En sund virksomhed kan være dyr, og en aktie med lav RSI kan blive ved med at falde.

## Relevante kapitler

| Bogens sider | Emne | Anvendelse i vores scanner | Nuværende status |
|---|---|---|---|
| 4–16 | Aktiv/passiv strategi, følelser, diversificering | Strategivalg, indeksbenchmark, koncentrationsadvarsler | Mangler |
| 17–20 | Kurs- og candlestick-grafer | OHLCV/candlestick og indikatoroverlays | Kun linjegraf |
| 21–25 | Glidende gennemsnit, trend following | SMA200-trendfilter, trendretning og signalhistorik | SMA200 findes |
| 25–29 | Trendkanaler, brud, støtte/modstand | Pivot- og breakout-detektor | Mangler |
| 30–34 | RSI og stigende aktier | RSI-retning kombineret med trend | RSI-niveau findes |
| 36–43 | P/E, ROE, payout ratio, kurs/indre værdi, P/S | Quality- og Value-nøgletal | Mangler |
| 43–49 | Ledelse, konkurrencefordele, branchetyper | Kvalitativ Moat/Quality-research | Mangler |
| 49–56 | Portefølje, beta, Risk/Reward og omkostninger | Risikopanel, omkostningsmodel | Mangler |
| 57–60 | Samlet strategi, ETF og skat | Benchmark og passiv-alternativ | Mangler |

## Quality – virksomhedsøkonomi

- **ROE:** egenkapitalforrentning; må vurderes sammen med gæld, da en høj ROE ikke nødvendigvis betyder høj operationel kvalitet.
- **Udbyttedækning/payout ratio:** vis både udbytte, indtjening og gerne frit cash flow.
- **Økonomisk stabilitet:** omsætning, indtjening, rentabilitet, gæld og balance.
- **Moat:** produkter, konkurrencestyrke, patenter, varemærke og andre varige fordele. Kvalitative udsagn skal have kilder og datoer.
- **Ledelse og branche:** dokumenter governance og klassificér cykliske kontra defensive virksomheder.
- **Sektorhensyn:** banker og forsikringsselskaber skal ikke bedømmes efter de samme balance- og EBITDA-kriterier som software og industri.

**Datakrav:** rapportdatoer, valuta, regnskabsperioder, link til kilde og håndtering af manglende felter. Returnér Ikke beregnet frem for at opfinde et nøgletal.

## Value – relativ værdiansættelse

- **P/E:** aktiekurs divideret med indtjening pr. aktie; vis historisk/TTM/forventet periode tydeligt.
- **P/B (kurs/indre værdi):** pris i forhold til bogført værdi; fortolkningen er brancheafhængig.
- **P/S:** markedsværdi i forhold til omsætning; kan ikke bruges uden blik for margin og gæld.
- **Peer-sammenligning:** relevante selskaber i samme sektor; undgå at sammenligne alle fem landes aktier på tværs af helt forskellige brancher.

Forslag: Value v1 viser rådata, historisk interval, branche/peer-reference og eventuelle mangler. DCF- og scenariomodeller følger først, når cash-flow-data og antagelser er valide. P/E med negativ eller nul indtjening vises som ikke meningsfuld.

## Timing – teknisk analyse

Bogen gennemgår SMA200 som trendfilter, glidende gennemsnit, trendkanaler, støtte/modstand og RSI. Vores nuværende Python-modul beregner allerede SMA50/200, RSI14 og MACD.

**Nye funktioner til test:**

1. Beregn SMA200-hældning og markér om aktien handler over/under en stigende/faldende lang trend.
2. Registrér højere toppe og bunde og mulige brud på trendkanaler.
3. Beregn støtte-/modstandszoner ud fra historiske pivots, og angiv datogrundlaget.
4. Kombinér RSI-retning med trendretning, således at oversolgt RSI ikke bliver et automatisk købssignal.
5. Tilføj daglige og ugentlige signaler og tydelig signalhistorik.

Eksempel på en **selvstændig kandidatregel til backtest**, ikke en gengivelse af bogens præcise strategi: kurs over stigende SMA200, RSI vender op og MACD krydser over signal. Dette må kaldes en observation, ikke en sikker købsmulighed.

## Risiko, portefølje og Risk/Reward

Bogen anbefaler at definere prisniveauer for planlagt exit allerede før indgang. Et **historisk undervisningseksempel** på trykte sider 54–55 bruger Novo Nordisk, købskurs 260, stopkurs 224 og muligt mål 400 DKK:

- Mulig gevinst pr. aktie: 140 DKK.
- Muligt tab til stopniveau: 36 DKK.
- Teoretisk Reward/Risk: cirka 3,89.

**Tallene er ikke aktuelle kurser og er ikke en handelsanbefaling.** Gaps, slippage og handelsomkostninger kan gøre reelt tab større end stoppets nominelle afstand.

Risikomodulet bør også beregne:

- Beta i forhold til relevant landebenchmark med angivelse af estimationsperiode.
- Porteføljevægt pr. aktie, sektor, tema, land og valuta (DKK, EUR, SEK, NOK, USD).
- Kurtage, spread og valutavekslingsomkostninger.
- Maksimalt fald, volatilitet og realistiske backtestafkast.
- Periodisk investering versus engangsinvestering som sammenligning med et passivt alternativ.

Bogens generelle udsagn om optimalt antal positioner og historisk aktieafkast skal ikke hardcodes som universelle sandheder.

## Kildekritik og forældede oplysninger

Bogen er fra **2021** og indeholder eksempler på historiske afkast, handelsplatforme, kurtage og danske skattesatser fra dengang. Disse er **ikke aktuelle 2026-værdier**. Ingen skattesatser, aktiesparekonto-grænser eller personlige investeringsregler må implementeres uden aktuelle, officielle kilder og korrekt tidspunkt.

Generelle trend-, RSI- og breakoutmetoder kan give falske signaler. Brug derfor test med omkostninger, split/udbytte, historiske datavintages, delistede aktier og out-of-sample perioder. Gratis Yahoo/yfinance-data kan være mangelfulde og må ikke præsenteres som komplet fundamental datadækning på tværs af fem markeder.

## Prioriteret backlog

| ID | Prioritet | Leverance | Krav |
|---|---|---|---|
| INV-01 | P0 | SMA200-trendfilter, RSI-retning | Gennemsigtige regler, uden fremadskuende data |
| INV-02 | P0 | Candlestick samt støtte/modstand | OHLCV og datoperioder korrekt markeret |
| INV-03 | P0 | Risk/Reward og stopniveauer | Prisgab, valuta og omkostninger |
| INV-04 | P1 | Fundamental dataadapter | Kilde og rapportdato for alle fem lande |
| INV-05 | P1 | Quality (ROE, indtjening, balance, moat) | Separat scoring og missing-data-status |
| INV-06 | P1 | Value (P/E, P/B, P/S, peers) | Periode- og sektoropmærksom |
| INV-07 | P1 | Portefølje/benchmark | Land, sektor, vægtning og valuta |
| INV-08 | P1 | Backtesting af RSI/trends | Out-of-sample og handelsomkostninger |
| INV-09 | P2 | Periodiske investeringer og ETF-benchmark | Sporbare antagelser og bidrag |
| INV-10 | P2 | Evt. danske skattefelter | Kun opdaterede, officielle kilder |

## Andre analyser

- [Daytrader – Inside Bar](DAYTRADER-INSIDE-BAR-2026-11-01.md)
- [MyStockScanner – Videoanalyse og roadmap](MYSTOCKSCANNER-VIDEOANALYSE-2026-11-01.md)
- [MyStockScanner – Dropbox-webappnoter](Dropbox/MyStockScanner-gennemgang-2026-11-01.md)
- [Hangar18 WordPress Update-plan](HANGAR18-UPDATE.md)

**Status:** Research dokumenteret. Ingen ændringer i aktiescannerens beregningskode på baggrund af denne PDF endnu. Originale PDF-rettigheder tilhører Invested.dk; filen genudgives ikke i dette repository via denne analyse.
