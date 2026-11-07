# B-17: Entry-kæden med point-in-time fundamentaldata (USA)

Genereret af `scripts/study_b17.py` 2026-11-05 19:38. Rå tal: `data/b17_resultater.csv`. Historisk test, IKKE en købsanbefaling.

**Spørgsmål:** Giver StockMap-køb + Kvalitet + Værdi mere end StockMap-køb alene, og mere end RSP (køb og hold)?

## Opsætning

- Univers: de amerikanske tickers i `data/universe.txt` (uden børssuffiks): 902; 900 har US-GAAP-tal hos SEC; 897 har nok kurshistorik til ugepanelet. Kun aktier, der findes i dag.
- Samme `simulate()` som `scripts/simulate_portfolio.py`: højst 40 lige store positioner, køb ugen efter KØB-signalet (næste åbning), salg ved Supertrend x3-vending eller StockMap-salg, 0,1 % pr. handel. Filtrene lægges kun på købet; salgsreglerne er uændrede. Ledig kontant står stille (ingen rente).
- Fundamentale tal: SEC companyfacts, hver værdi med `filed`-dato (`stockscanner/pit_fundamentals.py`). På en given uge bruges kun tal indleveret senest dagen før ugens lukning, og for hver periode den senest indleverede version (omarbejdede tal tæller først fra deres egen `filed`-dato).
- Kvalitet (forenklet): percentil i tværsnittet pr. uge af ROE, ROA, bruttomargin, rentedækning, omsætningsvækst og (omvendt) gæld/egenkapital; middelværdien rangeres igen; kræver mindst halvdelen af nøgletallene og mindst 50 aktier på datoen. Krav: >= 60.
- Værdi (forenklet): aktiens P/E (kurs / TTM-EPS, EPS splitomregnet) mod aktiens egen P/E-historik til og med ugen (højst 10 år, mindst 3 år): andel af tidligere uger med højere P/E. Krav: >= 50 (P/E på eller under egen median).
- **Begge scorer er tilnærmelser af de rigtige (`quality_rank.py`, værdikanalen i `valuation.py`), ikke samme formel.** Værdikanalens PEG-, asymmetri-, regnskabs- og estimatkrav fra mandagslisten indgår ikke.

## Resultater

### Hele perioden 2012 → i dag

| Variant | CAGR % | Største fald % | Handler | Vindere % | Gns. handel % | Købssignaler | Fyldte pladser % |
|---|---:|---:|---:|---:|---:|---:|---:|
| RSP køb-og-hold | 12.7 | -36.7 | – | – | – | – | – |
| StockMap alene | 12.7 | -36.6 | 12536 | 48 | 0.63 | 66872 | 96 |
| + Kvalitet >= 60 | 10.8 | -30.2 | 12360 | 48 | 0.54 | 25723 | 94 |
| + Værdi >= 50 | 8.3 | -32.9 | 11191 | 47 | 0.47 | 21784 | 82 |
| + begge | 5.7 | -24.8 | 9113 | 47 | 0.38 | 10745 | 67 |

### Udvikling 2012 → 2024-11

| Variant | CAGR % | Største fald % | Handler | Vindere % | Gns. handel % | Købssignaler | Fyldte pladser % |
|---|---:|---:|---:|---:|---:|---:|---:|
| RSP køb-og-hold | 12.8 | -36.7 | – | – | – | – | – |
| StockMap alene | 12.8 | -36.6 | 10682 | 48 | 0.65 | 56591 | 96 |
| + Kvalitet >= 60 | 11.5 | -30.2 | 10485 | 48 | 0.59 | 21688 | 94 |
| + Værdi >= 50 | 7.7 | -32.9 | 9321 | 47 | 0.48 | 17441 | 80 |
| + begge | 5.7 | -24.8 | 7423 | 47 | 0.42 | 8720 | 64 |

### Urørt 2024-11 → i dag

| Variant | CAGR % | Største fald % | Handler | Vindere % | Gns. handel % | Købssignaler | Fyldte pladser % |
|---|---:|---:|---:|---:|---:|---:|---:|
| RSP køb-og-hold | 12.9 | -15.5 | – | – | – | – | – |
| StockMap alene | 12.3 | -17.1 | 1852 | 46 | 0.37 | 10281 | 92 |
| + Kvalitet >= 60 | 6.4 | -21.8 | 1871 | 46 | 0.13 | 4035 | 91 |
| + Værdi >= 50 | 10.8 | -14.8 | 1885 | 47 | 0.25 | 4343 | 91 |
| + begge | 6.1 | -17.8 | 1674 | 46 | 0.07 | 2025 | 81 |

`Fyldte pladser` er gennemsnittet af de 40 pladser, der var optaget (kun lukkede handler); lav værdi betyder, at kontanter stod ubrugt, fordi filtrene lader få signaler igennem. Det trækker CAGR ned uden at sige noget om signalernes kvalitet; `Gns. handel %` (afkast pr. handel efter omkostning) er derfor et renere mål for signalkvaliteten.

## Usikkerhed

90 %-interval for forskel i årlig vækst (procentpoint) ved blok-bootstrap (13 uger) af ugentlige afkast. Et interval, der indeholder 0, betyder, at forskellen ikke kan skilles fra tilfældighed. Intervallerne antager, at ugeafkast kan genbruges i blokke, og undervurderer sandsynligvis usikkerheden, fordi variantene deler signaler og er koncentreret i få markedsfaser.

| Periode | Variant | Sammenlignet med | 5 % | 95 % |
|---|---|---|---:|---:|
| hele | + Kvalitet >= 60 | mod StockMap alene | -5.3 | 1.6 |
| hele | + Værdi >= 50 | mod StockMap alene | -7.6 | -0.6 |
| hele | + begge | mod StockMap alene | -11.2 | -2.3 |
| hele | StockMap alene | mod RSP | -2.9 | 2.9 |
| hele | + Kvalitet >= 60 | mod RSP | -4.9 | 1.1 |
| hele | + Værdi >= 50 | mod RSP | -7.2 | -1.2 |
| hele | + begge | mod RSP | -10.5 | -3.0 |
| urørt | + Kvalitet >= 60 | mod StockMap alene | -11.3 | 4.5 |
| urørt | + Værdi >= 50 | mod StockMap alene | -11.2 | 10.8 |
| urørt | + begge | mod StockMap alene | -20.9 | 7.0 |
| urørt | StockMap alene | mod RSP | -12.5 | 6.0 |
| urørt | + Kvalitet >= 60 | mod RSP | -13.8 | 0.9 |
| urørt | + Værdi >= 50 | mod RSP | -8.4 | 1.7 |
| urørt | + begge | mod RSP | -19.1 | -1.3 |

## Dækning (median antal aktier pr. uge, pr. år)

| År | med Quality | med Value | Quality >= 60 | Value >= 50 |
|---|---:|---:|---:|---:|
| 2009 | 0 | 0 | 0 | 0 |
| 2010 | 193 | 0 | 78 | 0 |
| 2011 | 476 | 0 | 191 | 0 |
| 2012 | 632 | 0 | 253 | 0 |
| 2013 | 674 | 190 | 270 | 53 |
| 2014 | 691 | 442 | 277 | 118 |
| 2015 | 705 | 546 | 283 | 190 |
| 2016 | 726 | 563 | 291 | 218 |
| 2017 | 740 | 594 | 297 | 187 |
| 2018 | 758 | 609 | 304 | 254 |
| 2019 | 771 | 638 | 309 | 320 |
| 2020 | 805 | 623 | 323 | 264 |
| 2021 | 824 | 618 | 330 | 196 |
| 2022 | 843 | 685 | 338 | 419 |
| 2023 | 848 | 689 | 340 | 410 |
| 2024 | 859 | 709 | 344 | 342 |
| 2025 | 869 | 730 | 348 | 342 |
| 2026 | 875 | 742 | 351 | 357 |

Værdiscoren kræver 3 års P/E-historik, så den dækker først fra ca. 2012-2013, og tidligt kun få aktier.

## Konklusion

(Skrevet af hånden efter kørslen 05-11-2026; scriptet overskriver kun denne tekst, hvis det køres igen.)

- **Nej: i denne test giver kvalitet og værdi på toppen af StockMap-køb ikke mere, men mindre.** Hele perioden: StockMap alene 12,7 % om året, + Kvalitet 10,8 %, + Værdi 8,3 %, + begge 5,7 %; RSP 12,7 %. Det samme mønster i udviklingsperioden (12,8 / 11,5 / 7,7 / 5,7 %). Gennemsnitsafkast pr. handel falder også for hvert filter (0,63 % → 0,54 / 0,47 / 0,38 %), så det er ikke kun et kontanteffekt (pladserne er 67-96 % fyldt).
- **StockMap alene slår ikke RSP** (12,7 mod 12,7 %, ens drawdown -36,6 mod -36,7 %; forskellen -2,9 til +2,9 pp i 90 %-intervallet). Filtrene giver lavere største fald for "begge" (-24,8 %), men til en lavere vækst, der er klart under RSP (-10,5 til -3,0 pp).
- **Urørt periode (2024-11 →):** StockMap alene 12,3 %, + Kvalitet 6,4 %, + Værdi 10,8 %, + begge 6,1 %, RSP 12,9 %. Værdi alene er næsten på højde med StockMap alene og har det mindste fald (-14,8 mod -17,1 %), men intervallerne er brede (op til +/-10-20 pp), så ingen forskel mod StockMap alene kan skilles fra tilfældighed. Kun "+ begge" er klart under RSP (-19,1 til -1,3 pp).
- **Altså:** testen støtter ikke, at Quality/Value-kravene i KØB-KANDIDAT forbedrer afkastet af StockMap-køb; den kan kun sige, at de mindsker udsvinget lidt (kombinationen) og koster afkast. Det betyder ikke, at de rigtige MSS-scorer er værdiløse: vores scorer er forenklede, og testen dækker kun købsvalget, ikke PEG, asymmetri, regnskabs- og estimatreglerne.
- **Forbehold ved de tal, der gør filtrene dårligere:** (1) når mange signaler konkurrerer om 40 pladser, vælger `simulate()` alfabetisk, så et filter ændrer kun hvilke aktier der kommer først i alfabetet, ikke en rangering efter kvalitet; (2) Værdi har ingen data før 2013 (3 års P/E-historik), så "+ Værdi" og "+ begge" står i kontanter i 2012 og dækker kun få aktier i 2013; (3) overlevelsesbias favoriserer især de ufiltrerede varianter, fordi svage selskaber, der døde, mangler for dem alle, men filtrene ville have fravalgt dem.


## Svagheder

- **Sortering ved fyldte pladser:** `simulate()` tager kandidater i alfabetisk rækkefølge, når der er flere end ledige pladser; filtrene rangerer ikke kandidaterne efter score.
- **Overlevelsesbias:** universet er aktier, der findes i dag. Konkurser og udgåede aktier mangler, og indekstilføjelser kendes bagud. Det favoriserer alle varianter, især dem uden kvalitetskrav.
- **Forenklede scorer:** ikke MSS' formler; ROIC, FCF, Piotroski m.fl. indgår ikke. Tag-valg i XBRL er forenklet (ét tag pr. begreb), og selskaber med usædvanlig kontoplan får manglende nøgletal.
- **Kun USA, kun US-GAAP** (10-K/10-Q); udenlandske selskaber uden companyfacts er udeladt. Ingen analytikerestimater (PEG, value trap, regnskabsblokering mangler).
- **EPS og splits:** EPS er i enheder ved indleveringen og omregnes med splits bagefter; et split mellem to indleveringer kan give et fejlbehæftet TTM-tal i enkelte uger (P/E over 500 og EPS <= 0 udelades).
- **Få uafhængige beslutninger:** få handler pr. variant i urørt periode og tydelige markedsfaser (2012-2021 bull, 2022 bear). Resultaterne er ikke statistisk sikre.
- Kvalitetskravet er en percentil i et univers på ca. 900 aktier (ikke hele markedet). Kurser er fra Yahoo (uofficiel) og kan have huller. Ingen skat, spread eller slippage ud over 0,1 %.
- Tærsklerne 60 og 50 er mandagslistens værdier og blev ikke tunet på disse data.

## B-17b: rangering og Top 10

(Skrevet af hånden 05-11-2026 ud fra `scripts/study_b17_rank.py` og `data/b17b_resultater.csv`. `study_b17.py` overskriver hele denne fil, hvis den køres igen, så den skal ikke køres uden at gemme konklusionerne først.)

**Spørgsmål:** Bliver resultatet bedre, når de højeste scorer købes først i stedet for alfabetisk, og når pengene samles i 10 aktier som Top 10?

Samme data, regler og omkostninger som B-17. `simulate()` har fået en valgfri `rank`, og uden den vælges der stadig alfabetisk. Samlet er her middel af forenklet Kvalitet og Værdi. Omvendt rangering køber de laveste scorer først og er kontrol: er den lige så god, måler testen tilfældighed og ikke scoren. Hver periode er en selvstændig kørsel med egen start, så hele perioden er ikke de to andre lagt sammen.

### Hele perioden 2012 → i dag

| Variant | CAGR % | Største fald % | Handler | Gns. handel % | 90 %-interval mod RSP (pp) |
|---|---:|---:|---:|---:|---|
| RSP køb-og-hold | 12,7 | -36,8 | – | – | – |
| StockMap, alfabetisk, 40 | 12,7 | -36,6 | 12536 | 0,63 | -3,0 til 2,9 |
| StockMap, Samlet, 40 | 11,4 | -36,2 | 12849 | 0,55 | -4,2 til 1,5 |
| StockMap, Samlet, 10 | 8,3 | -46,1 | 3300 | 0,43 | -9,2 til -0,0 |
| StockMap, omvendt, 10 | 10,2 | -38,0 | 3125 | 0,56 | -7,5 til 2,8 |
| Begge krav, alfabetisk, 40 | 5,7 | -24,8 | 9113 | 0,38 | -10,5 til -3,0 |
| Begge krav, Samlet, 40 | 7,0 | -24,5 | 9033 | 0,46 | -9,4 til -1,5 |
| Begge krav, alfabetisk, 10 | 8,0 | -46,5 | 3088 | 0,41 | -9,4 til -0,7 |
| Begge krav, Samlet, 10 | 6,3 | -44,8 | 3015 | 0,36 | -10,9 til -1,2 |
| Begge krav, omvendt, 10 | 6,5 | -28,8 | 3039 | 0,36 | -10,6 til -1,7 |

### Udvikling 2012 → 2024-10

| Variant | CAGR % | Største fald % | Handler | Gns. handel % | 90 %-interval mod RSP (pp) |
|---|---:|---:|---:|---:|---|
| RSP køb-og-hold | 12,8 | -36,8 | – | – | – |
| StockMap, alfabetisk, 40 | 12,8 | -36,6 | 10682 | 0,65 | -2,9 til 3,1 |
| StockMap, Samlet, 40 | 9,9 | -36,2 | 11013 | 0,50 | -5,9 til 0,1 |
| StockMap, Samlet, 10 | 8,3 | -46,1 | 2795 | 0,44 | -9,2 til 0,6 |
| StockMap, omvendt, 10 | 11,3 | -38,0 | 2657 | 0,63 | -6,3 til 3,6 |
| Begge krav, alfabetisk, 40 | 5,7 | -24,8 | 7423 | 0,42 | -10,8 til -2,1 |
| Begge krav, Samlet, 40 | 6,4 | -24,5 | 7380 | 0,47 | -10,3 til -1,3 |
| Begge krav, alfabetisk, 10 | 6,8 | -46,5 | 2613 | 0,40 | -10,0 til -0,5 |
| Begge krav, Samlet, 10 | 5,9 | -44,8 | 2517 | 0,35 | -11,5 til -0,9 |
| Begge krav, omvendt, 10 | 7,5 | -28,8 | 2552 | 0,42 | -9,3 til 0,5 |

### Urørt 2024-11 → i dag

| Variant | CAGR % | Største fald % | Handler | Gns. handel % | 90 %-interval mod RSP (pp) |
|---|---:|---:|---:|---:|---|
| RSP køb-og-hold | 12,9 | -15,5 | – | – | – |
| StockMap, alfabetisk, 40 | 12,3 | -17,1 | 1852 | 0,37 | -12,5 til 6,0 |
| StockMap, Samlet, 40 | 21,2 | -14,1 | 1843 | 0,70 | 0,3 til 15,8 |
| StockMap, Samlet, 10 | 6,8 | -18,1 | 507 | 0,17 | -22,2 til 4,4 |
| StockMap, omvendt, 10 | 4,2 | -20,8 | 470 | 0,08 | -28,5 til 7,0 |
| Begge krav, alfabetisk, 40 | 6,0 | -17,8 | 1674 | 0,07 | -19,1 til -1,3 |
| Begge krav, Samlet, 40 | 10,0 | -18,1 | 1639 | 0,24 | -15,1 til 4,2 |
| Begge krav, alfabetisk, 10 | 17,4 | -16,5 | 479 | 0,34 | -10,1 til 11,3 |
| Begge krav, Samlet, 10 | 7,5 | -18,5 | 503 | 0,20 | -20,7 til 4,6 |
| Begge krav, omvendt, 10 | 0,8 | -19,1 | 484 | -0,14 | -26,1 til -5,0 |

### Konklusion

- **Nej: testen viser ikke, at Samlet vælger bedre aktier.** Rangering hjælper ikke konsekvent. Hele perioden med 40 pladser: StockMap falder fra 12,7 til 11,4 %, mens Begge krav stiger fra 5,7 til 7,0 %. Med 10 pladser er Samlet under alfabetisk for Begge krav (6,3 mod 8,0 %).
- **Kontrollen viser det samme.** Hele perioden er omvendt rangering lige så god eller bedre end Samlet med 10 pladser: StockMap 10,2 mod 8,3 % og Begge krav 6,5 mod 6,3 %. Omvendt har desuden klart mindre største fald (-38,0 mod -46,1 % og -28,8 mod -44,8 %). I udviklingsperioden gælder det samme (11,3 mod 8,3 % og 7,5 mod 5,9 %).
- **Kun i den urørte periode slår Samlet omvendt rangering** (6,8 mod 4,2 % og 7,5 mod 0,8 %). Perioden er på ca. to år, og mønsteret er modsat de 13 år før, så det kan ikke bære en konklusion.
- **Top 10-måden (Begge krav, Samlet, 10 pladser) ligger klart under RSP:** 6,3 mod 12,7 % om året og største fald -44,8 mod -36,7 %. I urørt periode 7,5 mod 12,9 %. Samling i 10 aktier øger faldet uden at øge afkastet. Det er historik for en forenklet udgave, ikke for sidens Top 10.
- **Det bedste enkelttal er StockMap, Samlet, 40 i urørt periode:** 21,2 % og interval 0,3 til 15,8 pp over RSP. Det er det eneste interval mod RSP, der ligger helt over 0, ud af 27 kørsler. Samme variant lå under alfabetisk i udviklingsperioden (9,9 mod 12,8 %). Tallet bør derfor ses som et muligt tilfældigt fund og følges fremad, ikke som et bevis.
- **Det største tilfældighedstegn:** Begge krav, alfabetisk, 10 giver 17,4 % i urørt periode. Alfabetet er ingen strategi, så udsving af den størrelse kan komme af ren tilfældighed med 10 pladser.
- **Samlet billede med B-17:** intet sikkert tegn på, at reglerne slår RSP. Købsreglerne er ikke ændret; det er Allans beslutning.

### Svagheder

- Samlet er kun middel af forenklet Kvalitet og Værdi. Moat og værdikanalen findes ikke point-in-time, så sidens rigtige Samlet er ikke testet.
- Intet sektorloft og ingen regnskabsspærring som i Top 10, og PEG, asymmetri og estimatkrav mangler.
- Kun nuværende aktier i USA (overlevelsesbias), og ingen omkostninger ud over 0,1 % pr. handel.
- Mange varianter og perioder er sammenlignet, så et enkelt pænt tal er forventeligt. Intervallerne undervurderer sandsynligvis usikkerheden.
- Med 10 pladser fylder hver aktie 10 %, så få handler styrer resultatet.
