> Senest opdateret 2. november 2026: 59 nummererede testtilfælde fordelt på denne oprindelige rapport (T01–T23), den supplerende rapport (T24–T52) og den løbende emnelog (T53–T59). Nyere resultater erstatter ældre åbne punkter i det afprøvede omfang. Se 00-Laes-mig.md.

# MyStockScanner – funktionstest

Testdato: 1. november 2026. Webapp version 57.8. Miljø: indlogget konto med aktiv prøveperiode, desktopbrowser. Seneste markedsdag i flere visninger: 30. oktober 2026.

## Resultat og rækkevidde

De centrale arbejdsgange til aktieresearch fungerer: søgning, oprettelse og udvidelse af watchlist, tabelsøgning, timingfilter, heatmap, aktiedetaljer, scenarier, porteføljevisninger og udvalgte kursuslektioner. Der er fundet datainkonsistenser og en tilgængelighedsfejl, som bør afklares, før signaler bruges som beslutningsgrundlag.

Dette er en bred manuel funktionstest og en samlet dækningsoversigt. **Det er ikke en fuldstændig godkendelse af samtlige funktioner.** Betalingsforløb, emaillevering, alle videoer, alle filterkombinationer, mobilvisning og leverandørernes beregningsmodeller er ikke sluttestet. En synlig knap eller åbnet side tæller ikke som en bestået gemme-, leverings- eller beregningstest.

Testen samler den tidligere gennemgang i denne session og de efterfølgende målrettede tests. Tidligere observationer er markeret særskilt. Der er ikke købt eller solgt værdipapirer, publiceret forumindlæg eller ændret abonnement. Researchlisten indeholder fortsat ni værdipapirer.

Statusdefinitioner: **Bestået** = det beskrevne resultat blev observeret; **Delvis** = kun en afgrænset del blev kontrolleret; **Afvigelse** = observeret modstrid eller fejl; **Ikke udført** = ingen dokumenteret sluttest. Bestået gælder kun det angivne testtilfælde.

## Målrettede tests

| ID | Funktion og fremgangsmåde | Forventet resultat | Observeret resultat | Status |
|---|---|---|---|---|
| T01 | Søg efter AI Stock Scanner i listebiblioteket | Egen researchliste findes | Præcis én egen liste | Bestået |
| T02 | Søg MSFT i listen med ni aktier | Kun Microsoft | Ét resultat | Bestået |
| T03 | Søg ukendt ticker i samme liste | Ingen resultater, tydelig tomtilstand | Nul resultater og tomtilstand; søgning ryddet | Bestået |
| T04 | Åbn Export | Eksport matcher listen | TradingView-tickertekst med ni aktier | Bestået |
| T05 | Importér eksisterende NASDAQ:MSFT | Ingen dublet | All tickers were imported; fortsat ni aktier | Bestået |
| T06 | Fravælg Neutral i timingfilter, anvend | MSFT, Visa og Schneider fjernes | Ni bliver til seks; aktivfilterindikator vises | Bestået |
| T07 | Vælg Alle igen | Hele listen gendannes | Ni resultater | Bestået |
| T08 | Heatmap: skift 1 Week til 1 Day | Periode og afkast ændres | Novo +2,21 %, ASML -6,11 % på dagen | Bestået |
| T09 | Gendan heatmap til 1 Week | Ugens data vender tilbage | HY9H +15,60 %, SOBI +7,93 %, CAT -9,35 % | Bestået |
| T10 | Pension: startkapital 100000 → 200000 og beregn | Output reagerer på kapital | Første års værdi 105333 → 210666 | Bestået |
| T11 | Pension: gendan 100000 og beregn | Oprindeligt output vender tilbage | Første års værdi igen 105333 | Bestået |
| T12 | Modelportefølje 1321: åbn Resumé | Afkast, risiko, allokering og statistik | Grafer og tabeller indlæses | Bestået |
| T13 | Statistik: All/Open/Closed Positions | Antal og statistik skifter konsistent | 207/13/194; 13 + 194 = 207; All gendannet | Bestået |
| T14 | Åbn Transactions | Historik med dato, type, ticker og værdi | Køb, salg, udbytte og startkontanter vises | Bestået |
| T15 | Kontrollér én udbytterække i modelporteføljen | Netto = brutto minus skat | TRV: 157,50 − 23,62 = 133,88 USD | Bestået |
| T16 | Kontomenu og Detaljer/Emails/System | Fanerne åbner | Formularer vises; lukket uden gemning | Delvis |
| T17 | Dashboard: Rediger, Tilføj widget, Færdig | Redigering og katalog åbner og lukker | Widgetkatalog med liste, tema, kalender, forum m.m.; ingen layoutændring afprøvet | Delvis |
| T18 | Kalender: Forrige uge | Ugen flyttes tilbage | Uge 45 → uge 44, 26.–30. oktober | Bestået |
| T19 | Kalender: I dag | Retur til aktuel kalendervisning | Navigation udført; søndagsovergang gør standardvisningen til kommende arbejdsuge | Delvis |
| T20 | Kalender: vælg Alle aktier | Begivenheder fra det brede univers | Mange regnskabsbegivenheder indlæses fra tidligere tom kalender | Bestået |
| T21 | Kalender: aflæs valgt radioknap | Én kilde angives valgt | Alle tre rapporterer Value 0; automatisk check fejler, selv om data skifter | Afvigelse |
| T22 | Kursus 32, direkte link til lektion 100 | Lektion åbner | Tekstlektion 100/167, kapitler og næste/forrige synlige; næste/forrige ikke sluttestet her | Bestået |
| T23 | Efterregn MSS for ti selskaber | Gennemsnit af Q/V/M afrundes til total | Ni af ti stemmer; HY9H afviger ét point ved afrunding af de viste komponenter | Afvigelse |

Export i T04 er **symboltekst til TradingView**, ikke dokumenteret CSV-eksport af regnskaber eller scores. Clipboardknappen og ekstern TradingView-import er ikke testet. T10–T11 kontrollerer reaktion og gendannelse, ikke hele pensionsmodellens matematik.

Kalenderkilden blev efter T21 sat tilbage til Favoritlister. Den oprindelige kilde kunne ikke aflæses entydigt, netop fordi valgtstatus manglede. Heatmap blev gendannet til én uge, timingfilter til Alle og pensionskapital til 100000.

## Tidligere verificerede arbejdsgange i samme session

| Område | Dokumenteret handling og resultat | Dækning |
|---|---|---|
| Hovednavigation | Hjem, Aktiekort, Forum, Temaer, Watchlists, Porteføljer, Værktøjer og Akademi åbnet | Navigationskontrol; ikke alle underfunktioner |
| Global søgning | Selskaber fundet; børs og instrumenttype kontrolleret ved tilføjelse | Positiv søgning bestået; fuld validering ikke udført |
| Watchlist-oprettelse | AI Stock Scanner – research, ID 14814, oprettet med navn og beskrivelse | Oprettelse bestået |
| Watchlist-tilføjelse | Først fem aktier, derpå HY9H.F, senere SU, SOBI og 1INN | Ni aktier bekræftet i tabel |
| Watchlist Dashboard | Kalender, beskrivelse, scores, timing og dagsbevægelser vises | Visning kontrolleret; timingafvigelse nedenfor |
| Playbook | Novo, HY9H, Schneider, SOBI og innoscripta undersøgt | Visninger og detaljepaneler kontrolleret |
| Kvalitet og moat | Klik åbner underliggende nøgletal og forklaringer | Paneler virker; delscoremodel ikke genskabt |
| Timinghistorik | Første/efterfølgende signaler, entry, exit og aktiv strategi aflæst | Historik kontrolleret; fremtidig triggerregel uafklaret |
| Valuegraf | Historik, scenarier, estimattyper, P/E-input og gem/annuller fundet | Delvis; vedvarende gemning ikke testet |
| Resumé | Historiske tal, estimater, cashflow, balance og risikonøgletal vises | Indhold kontrolleret; rå regnskabstal ikke revideret |
| Analytikere | EPS/omsætning og intervalvalg ændrer serier | Interaktion kontrolleret; valutamærkning bør afklares |
| Fundamentaldata | Års-/LTM-data og cashflowfane åbnet | Delvis; ikke alle periode/typekombinationer |
| Udbytte | Historik, ex-dato, betalingsdato og udbytteoversigt | Visningskontrol; fremtidige tomme felter ikke fejlbevis |
| Sæson | Månedsmiddel, median og vinderandel observeret | Delvis; historikslider ikke afprøvet |
| Explorer/scanner | MSS Europe-liste 14480 åbnet med 79 resultater; simple regler aflæst | Delvis; ikke alle grænser eller regelkombinationer |
| Aktiekort | Regioner → Europe → 21 lande; lande/sektorer og aktiespor undersøgt | Navigation kontrolleret; benchmark/EMA/SMA ikke sluttestet |
| Tema | AI-Power, tema 19, åbnet; Kernekraft/Uran valgt | Segment ændrer beholdninger, scores og afkast |
| Forum | Oversigt, typer/tags, ulæstvisning og Research Coverage undersøgt | Delvis; søgning og publicering ikke sluttestet |
| Akademi | Kursus 32 samt relevante tekstlektioner åbnet | Delvis; 167 lektioner og videoafspilning ikke alle testet |

Den mere detaljerede funktionsbeskrivelse findes i `MyStockScanner-gennemgang-2026-11-01.md` i samme mappe.

## Fejl og afklaringspunkter

### F01 – HY9H viser forskellige signaler og scores mellem visninger

Prioritet: høj. Status: observeret afvigelse, årsag uafklaret.

Åbn researchlistens tabel og HY9H's Playbook. Tabellen har vist kurs 978 EUR, Q94/V91/M75/MSS86 og Købszone med overbevisning. Playbook har ved et andet opslag vist kurs 924 EUR, V94/MSS88 og Behold. Playbooks historik pr. 30. oktober viste første købssignaler 14. august og aktiv Behold-strategi med −10,29 % signalafkast. Bevægelsesretning har også været forskellig, 298° versus 270°.

Forventning: enten konsistente snapshots eller tydelig forklaring af forskellige datotidspunkter/beregningsgrundlag. Det er ikke bevist, at de to opslag havde identisk snapshot. Cache, opdateringsfrekvens og datodækning er mulige forklaringer, ikke fastslåede årsager. Den præcise signalstatus bør derfor afklares i appen før brug.

### F02 – Kalenderens valgte datakilde mangler tilgængelig status

Prioritet: mellem. Status: reproduceret i målrettet test.

Åbn Værktøjer → Aktiekalender → Kalenderindstillinger. Vælg Alle aktier. Begivenheder indlæses, men Favoritlister, Alle aktier og Brugerdefineret liste rapporterer alle Value 0 i tilgængelighedstræet. En semantisk check-handling rapporterer, at checked ikke blev true, selv om datakilden ændres. Et almindeligt klik på Favoritlister virker.

Forventning: den aktive kilde har korrekt valgtstatus, fx aria-checked=true. Det er en tilgængeligheds-/automatiseringsfejl; selve datakildeskiftet virker.

### F03 – Timinghjælp gav ingen hjælpetopics

Prioritet: mellem. Status: tidligere observeret i både tabel og Playbook.

Hjælp ved timing gav ingen emner. Kursusmaterialet beskriver MTI/TPI, men en fuld definition af forskellen mellem Købszone, Stærk købszone og Købszone med overbevisning blev ikke fundet i den læste dokumentation. Der blev heller ikke fundet en bestemt fremtidig triggerkurs.

### F04 – Øvrige forhold til afklaring

- Watchlist-dashboardets timingfordeling har tidligere afveget fra tabellen. Nogle zonetællinger er tilsyneladende hierarkiske: researchlisten viste 1 conviction, 3 strong og 4 buy, selv om de eksklusive rækker indeholdt én conviction, to strong og én almindelig buy. Disse tal må ikke blot summeres som disjunkte grupper. Det forklarer ikke nødvendigvis den tidligere Neutral/Salgszone-afvigelse.
- Analytikergraf har vist USD-akse, mens Novo-kort brugte DKK. Beregnings- og mærkningsgrundlaget bør afklares.
- Heatmap viste slider-værdi 210, tekst 200 og en forklaring om op til 300 værdipapirer. Det er en mulig mærkningsafvigelse; grænserne blev ikke testet.
- På dansk ses engelske tekster, fx Transactions, Recently Viewed og engelske valideringsbeskeder. Kortvarige LoadingText/Definition.LoadingText blev observeret under indlæsning; ikke dokumenteret som permanent fejl.
- Scannernavne kan være snævrere end reglerne: strong/conviction-listen inkluderer også almindelig buy. En Worldwide-beskrivelse omtalte Europa. Reglerne bør læses frem for at stole på titlen.
- Temaets historik begynder før oprettelsesdatoen. Det er ikke i sig selv en fejl, men historisk temaperformance må skelnes fra dokumenteret live-performance.

## Scorekontrol: ti selskaber

Appen beskriver MSS som gennemsnittet af kvalitet, værdi og moat. Timing indgår separat. Følgende er en **aritmetisk konsistenskontrol af appens egne delscorer**, ikke en uafhængig analyse ud fra selskabernes årsrapporter.

| Selskab/ticker | Kvalitet | Værdi | Moat | Beregnet gennemsnit | Afrundet | Vist MSS |
|---|---:|---:|---:|---:|---:|---:|
| Microsoft / MSFT | 73 | 54 | 87 | 71,33 | 71 | 71 |
| Visa / V | 84 | 38 | 93 | 71,67 | 72 | 72 |
| SK Hynix GDR / HY9H.F | 94 | 91 | 75 | 86,67 | 87 | 86 |
| ASML | 90 | 61 | 92 | 81,00 | 81 | 81 |
| Caterpillar / CAT | 82 | 71 | 72 | 75,00 | 75 | 75 |
| Novo Nordisk / NOVO-B | 61 | 87 | 86 | 78,00 | 78 | 78 |
| Schneider / SU | 87 | 100 | 72 | 86,33 | 86 | 86 |
| Swedish Orphan Biovitrum / SOBI | 75 | 96 | 70 | 80,33 | 80 | 80 |
| innoscripta / 1INN | 93 | 97 | 87 | 92,33 | 92 | 92 |
| QuinStreet / QNST | 87 | 92 | 59 | 79,33 | 79 | 79 |

**Resultat: ni af ti stemmer ved almindelig afrunding af viste heltalskomponenter. HY9H afviger én point.** Hvis delscorerne allerede er afrundede, kan skjult præcision forklare en sådan afvigelse; alternativt kan snapshots være forskellige. Dette er ikke bevis for en forkert beregning, men skal med som en undtagelse. HY9H's andet snapshot Q94/V94/M75 giver 87,67 → 88 og matcher den pågældende Playbook-total.

QNST blev genaflæst på dashboardet og blev ikke tilføjet til listen. Ni andre observationer kommer fra researchlisten og de tidligere detaljerede opslag. Delscorer er ikke nødvendigvis opdateret samtidig på tværs af sider.

En reel uafhængig reproduktion af kvalitet, værdi og moat kræver de nøjagtige variable, normaliseringer, vægte, peergrupper, datoklip, estimater og behandling af manglende data. Disse blev ikke offentliggjort i de undersøgte paneler. Derfor kan vi ikke hævde at nå samme delscorer ud fra rå regnskabstal.

## Entry og candles

Timinghistorikken viser strategiens konkrete historiske entry-dato og efterfølgende signaler. Det er ikke nødvendigvis samme begivenhed. SOBI havde fx strategi-entry 26. juni, men et efterfølgende stærkt signal 30. oktober. innoscripta havde entry og første stærke signal 23. oktober. Schneider ventede på ny indgang trods høj fundamental score.

Den læste TradingView-lektion foretrækker grøn daglig og ugentlig MTI og omtaler TPI til finjustering. Candles kan vises dagligt, ugentligt og månedligt. Der blev ikke dokumenteret en bestemt candlestickformation eller regel om brud over et candles højeste kurs som den officielle entry-trigger. Der blev heller ikke fastlagt en fremtidig triggerkurs. Et igangværende ugesignal kan ændre sig før ugens afslutning.

## Resterende testdækning

| Funktion/testtype | Status og konkret begrænsning |
|---|---|
| Alle filterkombinationer, grænseværdier, Advanced, AND/OR og gemt dynamisk scanner | Ikke udført end-to-end; simple regler kun undersøgt |
| Watchlist redigering, sletning, deling, favoritter og egne kolonnelayouts | Ikke sluttestet; oprettelse/tilføjelse/import er testet |
| Tabelsortering, gitter og alle layoutvarianter | Ikke systematisk testet |
| Aktiekort historik, benchmark, spor, maxantal, EMA/SMA og alle kvadrantfiltre | Kontroller identificeret; ikke fuld kombinationstest |
| Egne værdiansættelser: gem, genåbn, nulstil og ugyldige tal | Ikke udført; model og redigeringsfelter undersøgt |
| TradingView-tegninger, indikatorer, gemning og alle tidsrammer | Ikke sluttestet |
| Pensionsberegner: nul/negative værdier, fordeling ≠100 %, bidragsperioder, omvendt aldersberegning | Ikke udført; kapitalreaktion og gendannelse bestået |
| Porteføljeoprettelse og manuel bogføring | Ikke udført; offentlig modelportefølje læst |
| Forum publicering, svar, vedhæftning, rapportering og emailnotifikationer | Ikke udført; sender til andre og kræver særskilt konkret beskedopgave |
| Kursusvideoer, lyd, fuldførelse og alle 167 lektioner | Ikke fuldt udført; tekstlektioner åbnet; videoindhold ikke gennemgået |
| Låste kurser og betalt adgang | Kan ikke verificeres med nuværende adgang; paywall ikke omgået |
| Kontogemning, landvalidering efter rettelse, emaillevering og upload af profilbillede | Ikke udført; faner kontrolleret uden gemning |
| Betaling, abonnement, bindinger og opsigelse | Ikke udført; ingen betalingsforpligtelser accepteret |
| Login fra udlogget tilstand, adgangskode, kontogendannelse og sessionudløb | Ikke udført; eksisterende login anvendt |
| Mobil, andre browsere, fuld tastaturtest, skærmlæser og farvepaletter | Ikke systematisk udført |
| Belastning, sikkerhed, server/API, leverandørdatakvalitet og fuld historisk afkastvalidering | Uden for denne manuelle UI-tests dokumenterede rækkevidde |

En fuld accepttest kræver et aftalt funktionsinventar, testkonto med relevante rettigheder og et miljø, hvor gemning, sletning, mails og betalingsforløb kan sluttestes uden at påvirke den rigtige konto. Ovenstående åbne punkter er bevidst ikke registreret som beståede.

## Sporbarhed og filer

- Researchliste: https://app.mystockscanner.com/Watchlist/14814/WatchlistTable
- HY9H Playbook: https://app.mystockscanner.com/Security/120113/SecurityPlaybook
- Modelportefølje: https://app.mystockscanner.com/Portfolio/1321/PortfolioPositions
- Kalender: https://app.mystockscanner.com/Tools/StockCalendar
- Pensionsberegner: https://app.mystockscanner.com/RetirementCalculator
- Kursuslektion: https://app.mystockscanner.com/Course/32/Course/2382
- Tidligere detaljer: MyStockScanner-gennemgang-2026-11-01.md
- Skærmbillede af den samlede liste: watchlist-9.png

Rapporten gemmes både i den ønskede lokale Dropbox-mappe og i chatprojektets outputs. At filen er skrevet lokalt bekræfter ikke i sig selv, at Dropbox-klienten har færdigsynkroniseret den.


## Opdatering 2. november 2026

Supplerende funktionstest T24–T52 er nu udført og beskrevet i `MyStockScanner-supplerende-test-2026-11-01.md`. Denne fil erstatter de tidligere åbne punkter i det omfang, de nye tests dækker dem. Der er nu i alt 52 nummererede testtilfælde; blokerede/delvise tests er fortsat ikke fuldt godkendte. Ny emnevis dokumentation føres løbende i `MyStockScanner-loebende-emnelog-2026-11-02.md`.

