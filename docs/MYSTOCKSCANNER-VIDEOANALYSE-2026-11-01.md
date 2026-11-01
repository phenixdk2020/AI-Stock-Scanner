# MyStockScanner – videoanalyse og V2-backlog

**Dato:** 2026-11-01  
**Projekt:** [AI-Stock-Scanner](https://github.com/phenixdk2020/AI-Stock-Scanner)  
**Markeder:** Danmark, Tyskland, Sverige, Norge, USA  
**Kilde:** Brugeruploadede MyStockScanner-optagelser. Analyse af udvalgte tidsstemplede videobilleder; ikke komplet lydtransskription eller verificeret formelgrundlag.

**Vigtigt:** Dette dokument er en analyse og plan, ikke dokumentation for at alle forslag allerede er implementeret.

## Modtaget materiale

| Video | Varighed | Vigtigste fund |
|---|---:|---|
| Nyt i MyStockScanner - Intro til nye features | 14:44 | Watchlists, heatmap, avanceret screener, signalvisning, StockMap, 3-PointPlaybook |
| Velkommen til Temaer | 03:02 | Temakort, temaindhold, aktielister, beskrivelse og performance |
| Updatering på Tema-performance | 10:37 | Tema-performance og visuel sammenligning af aktier/temaer |
| Sådan vælger jeg aktier med MyStockScanner | 12:13 | Årsregnskaber, kvalitetsindikatorer, værdiansættelse og timing |
| Sådan vælger jeg aktier med MyStockScanner-77ebb4 | 12:13 | Identisk kopi af foregående video |
| StockMap - Forklaring 1 | 15:23 | Relativ styrke/momentum, fire kvadranter, benchmark og historiske spor |
| Tradingview gratis i MyStockScanner | 14:03 | Candlesticks, indikatorer, RSI, tegneværktøjer og interaktiv graf |
| Is it Overrated or underrated? | 00:57 | Over-/undervurdering som formidlingsemne |
| NEVER follow the hype! | 00:29 | Undgå at bruge hype alene som investeringsgrundlag |
| From a superior A+ to a failing F! | 01:38 | Bogstavkarakterer; den præcise scoremetode er ikke dokumenteret |

Ti videofiler, hvoraf ni er unikke. Den nye gruppe med seks uploads indeholder fem forskellige videoer.

## 1. Temaer

I videoen *Velkommen til Temaer* ses kuraterede aktiegrupper, bl.a. et FinTech-eksempel, som åbnes fra temakort og fører til beskrivelse, graf og aktieliste. Andre optagelser viser temaer relateret til eksempelvis AI-power, batteriteknologi og cybersikkerhed.

**Forslag:**
- Egen database for temaer, segmenter, aktier, sektorer og kilder.
- Navngivne investeringstemaer på tværs af de fem markeder.
- Tema-performance relativt til et valgt benchmark, med klart dokumenteret vægtning og rebalancering.
- Historiske medlemsskaber skal have gyldighedsdatoer, ellers giver backtest bagudskuende udvælgelsesbias.

## 2. StockMap / relativ rotation

*StockMap - Forklaring 1* viser Leading, Improving, Lagging og Weakening som fire kvadranter. Hvert værdipapir kan have et historisk spor; valg af benchmark, filtre og udjævningsmetode ses i kontrolpanelet. I en anden video vises StockMap sammen med tekniske prisgrafer.

**Forslag til egen model:** Beregn forholdet mellem aktiens og benchmarkets totalafkast, normalisér relativ styrke og mål ændringen heri som momentum. Plot aktiernes historiske ugentlige positioner med egne dokumenterede tærskler. Mulige indstillinger: benchmark, land, sektor/tema, sporlængde, aktier på listen, SMA/EMA og kvadrant.

**Metodekrav:** Harmonisering af valuta, udbytte/split, fælles handelsdage og observationer. Videoerne dokumenterer ikke de proprietære formler, så vi må ikke kalde vores resultat identisk med MyStockScanners StockMap eller MTI/TPI.

## 3. Aktieudvælgelse: Quality, Value og Timing

*Sådan vælger jeg aktier med MyStockScanner* viser historiske regnskabstal, EPS, P/E, indtjening/omsætning, risikonøgletal, værdiansættelsesgraf og tekniske signaler. Forskellige scenarier kan vises ved forskellige antagelser om vækst, multipler og horisont.

| Dimension | Vores egen kommende funktion | Validering |
|---|---|---|
| Quality | ROIC/ROE, profitabilitet, cash flow, vækst, balance, evt. Piotroski F-score | Regnskabsdato, kilde, selskabstype og manglende værdier |
| Value | P/E, EV/EBITDA, FCF-yield, konservativ/basis/optimistisk scenarie | Antagelser, historisk og peer-sammenligning, valuta |
| Timing | SMA/EMA, RSI-retning, MACD-kryds, ATR, volumen, støtte/modstand, dag/uge | Ingen fremadskuende data og backtesting |

Vi må ikke give en fuldt beregnet Quality- eller Value-score, når de nødvendige regnskabstal mangler. Finansselskaber kræver separat logik, og Altman Z-score er ikke universelt anvendelig.

## 4. Kursgraf og TradingView

*Tradingview gratis i MyStockScanner* viser candlesticks, trendlinjer, indikatorer, volumengrafer, RSI samt valg af tidsperiode og værktøjer.

**Vores anbefalede standard:** Byg candlestick + indikatorer med Plotly og de kursdata, vi har rettigheder til. En gratis TradingView-widget kan være et ekstra tilvalg under gældende vilkår, men deres avancerede selvhostede bibliotek er ikke automatisk frit anvendeligt til et privat hobbyprojekt. Titel og demonstration fra videoen er ikke bevis på licensrettigheder.

## 5. Avanceret screener og watchlists

Introvideoen viser filtrering, sortering, aktiescores og oversigter med flere dimensioner. Prioritér gemte filtre på: land, markedsværdi, sektor/tema, score, trend, volumen, RSI, MACD og potentiel overophedning. Understøt flere navngivne watchlists, eksport, historik og klik til aktiedetaljer.

## 6. Sammenligning med nuværende GitHub-version

| Funktion | Status | Næste opgave |
|---|---|---|
| Teknisk score med SMA50/200, RSI, MACD, 21 dage og volumen | Implementeret | Behold som transparent baseline |
| Fem markeder med eksempel-tickere | Implementeret | Fuld børsunivers-dækning kræver datakilde |
| Watchlist, lokal SQLite, CSV og Ollama | Implementeret | Flere lister og brugerfiltre |
| Enkelt sektoroverblik | Implementeret | Flere temaer og historik |
| Lokal GitHub Update-knap | Implementeret | Separat WordPress-opdatering mangler |
| Tema-performance og temaer | Mangler | Ny model og side |
| Avancerede charts | Mangler | Candlesticks og egne indikatorer |
| StockMap med historiske spor | Mangler | Egen relativ-styrke/momentum-metode |
| Fundamental Quality og Value | Mangler | Datakilder + forklarbare modeller |
| Valideret backtesting | Mangler | Point-in-time historik og handelsomkostninger |
| WordPress-frontend på hangar18.dk | Mangler | Separat frontend + sikker dataoverførsel |

## 7. Prioriteret teknisk backlog

| ID | Prioritet | Leverance | Acceptkriterier |
|---|---|---|---|
| VID-01 | P0 | Candlestick, SMA/EMA, RSI, MACD, volumen | Aktuel kursdato og valutakode vises; syntetiske enhedstests |
| VID-02 | P0 | Timing v1 med dag/uge, MACD-kryds, RSI-retning, ATR | Ingen "køb" alene på oversolgt RSI; ingen look-ahead |
| VID-03 | P0 | Gemte filtre og navngivne watchlists | Separate lister; ingen sletning af tidligere resultater |
| VID-04 | P1 | Temaer og historiske medlemsskaber | Dateret medlemskab og valideret temaafkast |
| VID-05 | P1 | StockMap og valg af benchmark | Fire kvadranter, forklarbar formel, sporlængde og tooltip |
| VID-06 | P1 | Tema-performance mod benchmark | Samme valuta, split/udbytte og datodækning |
| VID-07 | P1 | Fundamental dataadapter for fem lande | Klare datakilder, rapportdatoer og manglende-felt-markering |
| VID-08 | P2 | Separate Quality- og Value-scores | Dokumenterede faktorer, sektorhensyn og scenarier |
| VID-09 | P2 | Backtesting | Kurtage, valuta, overlevelsesbias, benchmark og drawdown |
| VID-10 | P2 | WordPress-version til Hangar18 | Installerbar plugin, autoriseret datavej og sikker Update/rollback |

## 8. Gratis drift og begrænsninger

- Ingen nye abonnementer eller betalte API-kald; vi bruger lokal Python/Ollama, hvor det er egnet.
- Gratis yfinance/Yahoo-kurser er uofficielle og giver ikke garanteret dækning/realtid eller komplette globale regnskaber.
- Videoerne bruges kun som funktionsinspiration, ikke til at kopiere proprietær kode, signalformler eller beskyttet design.
- Ingen automatisk handel eller løfter om afkast.
- Rapportér altid kilde, tidspunkt, parametre og manglende data.
- For Hangar18 skal WordPress-frontend og Python-motor holdes sikkerhedsmæssigt adskilt.

**Referencer i samme repository:**
- [MyStockScanner-gennemgang i Dropbox](Dropbox/MyStockScanner-gennemgang-2026-11-01.md)
- [Hangar18 Update-plan](HANGAR18-UPDATE.md)
- [Dropbox/GitHub Sync](DROPBOX-GITHUB-SYNC.md)

**Status ved udgivelsen:** Dette dokument tilføjer research og udviklingskrav, ikke implementering af nye analysefunktioner.
