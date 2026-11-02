# MyStockScanner – hvad mangler at blive gennemgået?

Status pr. 2. november 2026, efter T01–T66 (T60–T66 i emneloggen). Dette er den aktuelle restliste og erstatter ældre lister over manglende tests i de første rapporter. Et punkt her betyder, at den beskrevne del mangler – ikke nødvendigvis at hele funktionen er urørt.

## 1. Næste praktiske funktionstests

- [ ] **Dashboard:** tilføj, flyt og skjul en widget; kontrollér gemning efter genindlæsning og gendan opsætningen. Kun redigeringstilstand og widgetkatalog er prøvet.
- [ ] **Scannere:** flere samtidige regler, AND/OR og eventuelle grupper; sammenligning mellem nøgletal; første/efterfølgende timing; ugyldige intervaller og manglende data. En simpel avanceret regel og gemning af scanner er testet.
- [ ] **Gemt scanner:** genindlæs fra biblioteket, redigér en eksisterende regel og kontrollér ændringen efter nyt opslag. Oprettelsen er verificeret, men hele redigeringsforløbet mangler.
- [ ] **Watchlist:** kopiering, favoritter til/fra, fjernelse og gentilføjelse af en aktie samt eventuel deling/synlighed. Undersøg først konsekvenser og mulighed for gendannelse. Sletning af selve researchlisten er ikke nødvendig for at teste de andre funktioner.
- [ ] **Layouts:** fjern en tilføjet kolonne, omdøb eget layout, afprøv annullering og forskellen mellem valgt layout og listens standard. Eget layout med tilføjet/flyttet datokolonne er gemt og genfundet.
- [ ] **Aktiekort:** vælg og gendan benchmark; test reelt loft på en liste med over 50 aktier; zoom, punktvalg, afkastværktøjstip og vinkelinterval over 0°. Historik, EMA/SMA, sporlængde og udvalgte filtre er allerede testet.
- [ ] **Aktier i bevægelse:** anvend ændringer i indstillinger, vælg/fravælg grupper, skift sorteringsnøgle og kontrollér resultatlisten. Gruppetræ, søgning og indstillingsformular er gennemgået.
- [ ] **Værdiansættelse:** ugyldige og ekstreme P/E-værdier, andre estimattyper, ændret prognosehorisont, scenariesynlighed og estimatlåse/synkronisering. Normal beregning, gemning, genindlæsning, annullering og nulstilling er testet.
- [ ] **Fundamentaldata:** alle regnskabstyper, årlig/LTM/interim og kompakt/udvidet visning samt skift mellem dem. Kontrollér datoperioder, enheder og tomme værdier.
- [ ] **Analytikere:** flere selskaber, tomme anbefalinger versus tilstedeværende estimater, perioder og datadefinitioner. Enkelte serie- og intervalskift er testet.
- [ ] **Udbytte:** flere selskaber med/uden udbytte, historikfiltre og datofelter. Visningen er læst; fuld interaktion og datakontrol mangler.
- [ ] **Peeroversigt:** søgning, sortering på scorer og navigation til/fra et konkret peerselskab. Global/Regional/Land er testet.
- [ ] **Kalender:** landevalg, ex-udbyttefilter med kendte begivenheder, uge frem/tilbage over månedsskifte og forskellige kildetyper. Egen watchlist, regnskabsfilter og aktielink er testet.
- [ ] **Pension:** negative/tomme input, skat og procenter uden for normale intervaller, fordeling der ikke summerer til 100 %, ugyldig bidragsperiode og uopnåelig ønsket indkomst. Nulafkast, kapitalændring, bidrag og den omvendte beregningsfunktion er afprøvet; hele modellen er ikke matematisk revideret.
- [ ] **Porteføljer:** oprettelse og redigering af en særskilt øvelsesportefølje, kontantbevægelser, omkostninger, udbytte og lukning af fiktive positioner. Kun modelporteføljens læsevisninger og statistik er kontrolleret. Eventuel bogføring skal først bekræftes som ren simulering uden mæglerordre.
- [ ] **Temaer:** flere temaer, artikellinks, benchmarkvisning og øvrige segmenter. Ét tema og et segmentvalg er testet.
- [ ] **Forum:** type-/tagfiltre, ulæstfilter og Research Coverage-filtre med konkrete før/efter-resultater. Søgning, artikel, lyd, kort/feed og annullering af ny-opslag-formular er testet.
- [ ] **Hjælpecenter:** systematisk test af kontekstfølsom hjælp fra de forskellige sider og links mellem hjælp og kursuslektioner.
- [ ] **Notifikationer:** navigation fra en enkelt notifikation og valgt læst/ulæst-status. Menuen er kun åbnet og lukket; ingen nye leveringer er testet.
- [ ] **Akademi:** flere repræsentative kurser, kursuslistefiltre og adgangsvisning. Én video, tekstlektioner, næste/forrige og fuldførelse er testet. Alle 167 lektioners indhold er ikke gennemgået; det er en særskilt indholdsgennemgang.

## 2. Kendte afvigelser, der stadig skal afklares

- [x] **HY9H:** Afklaret i T61. Med kursdato 30.10 i både liste og Playbook stemmer score, kurs og timing (924 EUR, MSS 88, Behold). Den tidligere forskel skyldtes kursdatoen 29.10.
- [ ] **Øjebliksbilleder mellem indlæsninger (T62):** En ny indlæsning i samme session viste igen HY9H's tal fra 29.10 (978 EUR). Find ud af, hvornår appen henter en ny dataversion, og om der kan vises en datastempling.
- [ ] **Neutral uden tal (T63):** Udforskerens timingtælling viser "—" for Neutral, selv om tre aktier er neutrale.
- [ ] **MTI/TPI i ugegraf (T60):** TradingView viser "!" for MTI og TPI på 1W. Afklar, om indikatorerne kun findes dagligt i grafen.
- [ ] **Interest Cover 100,00 (T66):** Afklar, om 100,00 for 1990–2008 er et loft eller manglende data.
- [ ] **Afrunding og filtergrænser:** hvorfor udelades ASML med vist kvalitet 90 ved minimum 90, men inkluderes ved 89? Hvorfor giver HY9H's viste delscorer 86,67, mens totalen er 86? Skjult præcision er mulig, ikke bekræftet.
- [ ] **Timingfordeling:** kontrollér tidligere afvigelser mellem dashboard og tabel på samme snapshot. Skeln mellem overlappende/hierarkiske zonetællinger og eksklusive aktuelle zoner.
- [ ] **Kalenderens radioknapper:** valgt kilde rapporteres ikke korrekt i tilgængelighedstræet, selv om datakilden skifter.
- [ ] **Analytikergrafens valuta:** afklar USD-akse kontra DKK-tal på Novo.
- [ ] **Heatmap:** afklar slider-værdi 210 kontra tekst 200 og beskrivelse om maksimum 300.
- [ ] **Tekster og kodning:** gennemgå blandede danske/engelske tekster, rå indlæsningsnøgler og fejl som PortefÃ¸ljedatoer.
- [ ] **Scannernavne:** afklar navne/beskrivelser, som ikke præcist svarer til de aktive regler eller geografien.

## 3. Konkrete blokeringer og manglende grundlag

- ~~**TradingView:** den indlejrede graf var tom i den anvendte browser.~~ Ophævet i T60: Grafen indlæses i Claude-appens browser med candles, MTI, TPI og Valuation. Tilbage at teste: tegninger, indikatorbibliotek, gemning af layout og alle tidsrammer.
- **Låst indhold:** kurser og funktioner uden adgang kan ikke sluttestes med den nuværende konto.
- **Scoremodel:** uafhængig genskabelse af kvalitet, værdi og moat kræver beregningsformler, vægte, datodækning, peerunivers og behandling af manglende data. Vi har efterregnet totalscorer, ikke reproduceret delscorer fra rå årsrapporter.
- **Entry:** præcis formel, tærskler og eventuel fremtidig triggerkurs for Buy/Strong/Conviction er ikke fundet. Generel MTI/TPI-undervisning og historiske entrydatoer dokumenterer ikke hele reglen.
- **Kontogemning:** Detaljer/Emails/System er åbnet, men gemning er ikke sluttestet. Kontoen mangler et påkrævet land; det skal være brugerens korrekte oplysning, før en sådan test kan gennemføres.
- **Email/push:** levering kræver en kontrolleret hændelse og adgang til at verificere modtagelsen; det er ikke udført.

## 4. Handlinger uden for den hidtil udførte test

Disse punkter kræver en særskilt konkret opgave, relevant adgang eller et testmiljø; de skal ikke gennemføres som tilfældige klik på den rigtige konto:

- Betaling, opgradering, opsigelse og accept af bindingsvilkår.
- Virkelige aktiehandler eller andre økonomiske transaktioner.
- Offentliggørelse af forumindlæg/svar, indsendelse af fejlrapport og upload af personlige filer.
- Permanent sletning, ændring af deling/adgang og ændring af sikkerhedsoplysninger.
- Login fra udlogget tilstand, adgangskodegendannelse og sessionudløb.

## 5. Bredere kvalitetstest

- [ ] Flere mobilbredder, tablet og orientering. Kun 390 × 844 og mobilmenu er stikprøvet.
- [ ] Andre browsere og faktiske telefoner.
- [ ] Fuld tastaturnavigation, fokusorden, skærmlæser, kontrast og tilgængelighedspaletter.
- [ ] Regression efter genindlæsning, længere session og dataopdatering.
- [ ] Belastning, sikkerhed, backend/API og leverandørdata. Disse er ikke dækket af den manuelle browsergennemgang og kræver en anden testopsætning.
- [ ] Uafhængig kontrol af regnskabsdata og historiske afkast, inklusive valuta, split, udbytte, omkostninger og eventuelle overlevelses-/udvælgelseseffekter.

## Anbefalet rækkefølge ved fortsættelse

1. ~~Afklar TradingView og forskellene i dataopdatering for HY9H.~~ Udført i T60–T62. Tilbage er datastempling mellem indlæsninger og MTI/TPI på ugegrafen.
2. Afslut scannerkombinationer, dashboard, watchlist/favoritter og layoutredigering.
3. Test grænseværdier i værdiansættelse og pension samt de resterende datafaner.
4. Afslut forum-/tema-/kalenderfiltre og hjælp.
5. Tag særskilt stilling til konto-, leverings- og transaktionsforløb samt en egentlig indholds-/datavalidering.

Løbende observationer fortsætter i `MyStockScanner-loebende-emnelog-2026-11-02.md`. Denne restliste er ikke en liste over beviste fejl; den skelner mellem manglende test, afvigelser og blokeringer.
