# MyStockScanner – løbende emnelog

Dato: 2. november 2026, Europe/Copenhagen.

Denne fil opdateres ved hvert nyt testemne. De samlede rapporter ligger i samme mappe. Browserobservationer er øjebliksbilleder; indlæsningsfejl registreres særskilt fra konstaterede produktfejl.

## Dokumentation og status

Den supplerende rapport er nu opdateret fra T24 til T52. Den første rapport dækkede T01–T23. Tidligere ikke testede områder som egne layouts, gemt scanner, scenariegemning, aktiekortfiltre, pensionskontrol, forumsøgning, lyd, sæsonslider, kursusvideo og mobilmenu er nu afprøvet i det beskrevne omfang.

## Næste emne: importvalidering

Status: påbegyndes. Formål: kontrollere, at en ukendt ticker giver en forståelig fejl, uden at ændre listen med ni selskaber.


## Observation under importtesten: datodækning

Researchlayoutets Last Close Date viser HY9H med 29.10.2026 og de øvrige otte selskaber med 30.10.2026. HY9H-listens kurs 978 EUR er dermed ikke dokumenteret som samme dags snapshot som de andre. Dette kan bidrage til tidligere afvigelser mellem liste og Playbook, men årsagen er endnu ikke bevist. Importtesten afventer svar.


## T53 – import af ukendt ticker: bestået

Input NASDAQ:ZZZZ_FUNCTION_TEST_20261102 blev afvist med Tickers not imported og selve tickeren i fejloversigten. Importknappen blev deaktiveret efter behandling. Listen viste fortsat ni resultater. Behandlingen tog flere observationer; den første indlæsning blev ikke fejlagtigt registreret som et slutresultat.


## Nyt emne: HY9H-dato og sammenlignelighed

Formål: kontrollere om Playbook viser en nyere kursdato end watchlistens 29. oktober. Ingen kurser eller modeller ændres.


## T54 – HY9H-snapshots: dateret forskel bekræftet

Watchlist: seneste kursdato 29.10.2026, kurs 978 EUR og Købszone med overbevisning. Playbooks timingpanel: Pr. 30.10.2026, aktiv Behold, entry 14.08.2026 og signalafkast −10,29 %. Playbooks scorekort viste MSS 88, Q94/V94/M75, mens tabellen tidligere viste MSS86/Q94/V91/M75. Der er altså en dokumenteret forskel i datodækning. Det er en plausibel forklaring på afvigelsen, men ikke et bevis for, at alle forskelle skyldes datoen. Ingen fremtidig triggerkurs blev vist.


## Nyt emne: aktiekalender med researchlisten

Formål: teste valg af konkret watchlist og regnskabsbegivenheder frem for kalenderens tidligere tomme favoritkilde.


## T55 – kalender med watchlist: bestået

Brugerdefineret liste → AI Stock Scanner – research viser én regnskabsbegivenhed i uge45: Novo Nordisk onsdag4.november. Klik på begivenheden åbner Novo Playbook med link tilbage til kalenderen. Kildevalget virker også for egen liste; radioknappernes manglende valgtstatus er fortsat et særskilt punkt.


## T56 – kalenderens begivenhedsfilter: bestået

Regnskabsfilter Indtjening fra fjerner Novo-begivenheden, så dagene viser Ingen begivenheder. Filteret er slået til igen. Returlinket fra aktiesiden førte tilbage til kalenderen med den valgte researchliste.


## Nyt emne: sammenlignelige selskaber

Formål: teste aktiens peeroversigt, tilhørende scorer og retur til aktiesiden. Kalenderkilden er sat tilbage til Favoritlister og regnskabsfilteret er til.


## T57 – peergrupper: bestået i afprøvet omfang

Novo Peer-gruppe Global indlæser en verdensomspændende Biotechnology-liste med bl.a.AbbVie,Amgen,ModernaogRegeneron samt flere noteringer af samme selskab. Land skifter beskrivelse til Denmark og viser bl.a.Novo,Genmab,ALK,Bavarian,Zealand,GubraogBioPorto. Regional skifter til Europe. Global er gendannet. Scorer,timing,markedsværdiogaktielinks vises. Dette er en branchegruppe, ikke nødvendigvis klinisk/forretningsmæssigt direkte konkurrence; flere noteringer kan optræde.


## Nyt emne: notifikationsmenu

Formål: kontrollere læseadgang og navigation uden at sende beskeder eller markere alle som læst.


## T58 – notifikationsmenu: delvis

Klokken åbner en liste med ulæst forumaktivitet og tekst om videobehandlingsnotifikationer. Titel, forfatter og relativ alder vises. Mark all read findes, men blev ikke brugt. Menuen blev lukket igen. Push-/emaillevering og nye hændelser er ikke valideret.


## Nyt emne: afsluttende konsistenskontrol

Formål: genåbne researchlisten, kontrollere de ni aktier og det gemte layout og sikre, at alle nye observationer er skrevet i Dropbox og kopieret til outputs.


## T59 – slutkontrol: bestået

Researchlisten er genåbnet og viser ni resultater. Kolonnen Last Close Date findes fortsat i den gemte tabelopsætning; HY9H viser29.10.2026. Visningsknappen hedder nu Listens standard, mens datokolonnen er bevaret. Ingen ukendt ticker blev tilføjet under importtesten.


## Ny session: datakatalog og genkontrol (2. november 2026, formiddag)

Udført af Claude i Claude-appens indbyggede browser, efter at brugeren selv var logget ind. Skærmbilleder ligger i `screenshots-2026-11-02/`. Det fulde datakatalog står i `MyStockScanner-datakatalog-2026-11-02.md`.


## T60 – TradingView-graf: bestået (ophæver blokeringen fra T36)

NOVO-B → TradingView indlæses med daglige candles og OHLC (30.10.2026: O 264,80 / H 268,40 / L 262,90 / C 266,10, +2,21 %), regnskabs- og udbyttemarkører, MTI (dag/uge), TPI (dag/uge/trend) og MSS Valuation Lines (Bull 89,89 %, Base 38,35 %, Analysts 12,00 %, Bear −13,19 %, som i scenarietabellen). Interval 5y skifter til ugecandles. T36's tomme graf var altså afhængig af browseren. Skærmbilleder 10–12.

**Afvigelse:** I ugevisningen (1W) viste MTI- og TPI-felterne et rødt "!" i stedet for bånd. I dagsvisningen var de fyldt. Det er ikke afklaret, om indikatorerne kun findes dagligt i grafen, selv om Resumé viser ugentlig MTI/TPI. Indikatorlagene blev slået til uden at gemme; Save viste ugemt ændring og blev ikke brugt.


## T61 – HY9H liste kontra Playbook: konsistent på samme dato

Researchlistens tabel viste HY9H med Last Close Date 30.10.2026, kurs 924,00 EUR, Q94/V94/M75/MSS 88 og Behold. Playbook viste MSS 88, kvalitet 94, værdi 94, moat 75 og Behold. Når begge visninger har kursdato 30.10, stemmer de. Det bekræfter T54's forklaring: F01 skyldtes forskellige kursdatoer (29.10 og 30.10), ikke forskellige beregninger. Skærmbilleder 04–05.


## T62 – samme session, ny indlæsning: gammelt øjebliksbillede igen (afvigelse)

Efter navigation til NOVO-B Fundamentaler (ny indlæsning af appen) viste Udforsker-sidepanelet for samme researchliste HY9H til **978,00 EUR, −3,2 %**, altså tallene fra 29.10. Cirka 30 minutter før havde tabellen vist 924,00 EUR, −5,5 %. Appen henter versionerede datafiler, og versionsnummeret var forskelligt mellem indlæsningerne. Indlæsninger i samme session kan altså give forskellige øjebliksbilleder, og en enkelt visning kan ikke bruges som bevis for det aktuelle signal. Kontrollér Last Close Date. Skærmbillede 14.


## T63 – timingtællinger i Udforskeren: hierarkiske, Neutral uden tal

På samme indlæsning som T62: Købszone med overbevisning 1, Stærk købszone 3, Købszone 4, Behold 2, Salgszone 0, Neutral "—", Alle 9. Med HY9H som overbevisning passer 1/3/4 med **kumulative** tællinger (overbevisning ⊂ stærk ⊂ køb). Behold 2 er ASML og CAT. De tre Neutral-selskaber (MSFT, V, SU) vises som "—" og ikke som 3. Det bekræfter F04's hierarkiske tælling og er en ny observation om Neutral.


## T64 – nøgletalskatalog: 12 grupper, 173 felter

Udforsker → Filtre → Tilføj andre filtre viser 173 felter i 12 grupper (fuld liste i datakataloget). Asset Type har 16 værdier, blandt andet Virtual Security for brancher og sektorer. Forklaringspanelet for Asset Type og Asset Type Name siger, at der endnu ingen forklaring er. Filterudkast blev annulleret med Afbestille, og ingen filtre blev anvendt eller gemt på researchlisten.

**Observation:** Ved hurtige skiftende valg (scriptede klik) sprang kataloget videre til "Angiv betingelse" for et andet felt end det sidst klikkede. Det er ikke reproduceret manuelt og registreres ikke som produktfejl.


## T65 – univers pr. land: optalt

Udforsker → Alle aktier: 70.604 uden filtre. DK 407, NO 375, SE 1.061, DE 4.400, GB 7.319, US 12.546. Alle instrumenttyper er med. "Alle aktier" starter med landefilter GB og filtervaluta GBP. Det forklarer GBP-markedsværdierne. Den ugemte scanner blev ikke gemt. Skærmbilleder 09 og 09b.


## T66 – Fundamentaler: rækker og historik

NOVO-B Nøgleforhold (Årligt) viser 1990–2025. Rækkerne for de fire opgørelser er aflæst (datakataloget afsnit 4). Interest Cover er præcis 100,00 i alle år 1990–2008, hvilket tyder på et loft eller en standardværdi. Cash/Assets mangler i flere år. Skærmbillede 13.


## Slutstatus for sessionen

Researchlisten har fortsat ni aktier. Ingen filtre, layouts, scannere, grafer eller værdiansættelser er gemt. Ugemte ændringer: Udforskerens kilde blev midlertidigt sat til Alle aktier med ændrede landefiltre, og grafens indikatorlag og 5y-interval blev slået til. Begge forsvinder ved genindlæsning uden at blive gemt. Senest viste aktier kan være opdateret af navigationen. Ingen handler, betalinger, beskeder eller forumindlæg.
