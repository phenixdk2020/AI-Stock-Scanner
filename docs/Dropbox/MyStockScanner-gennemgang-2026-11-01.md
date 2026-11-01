# MyStockScanner – gennemgang af funktioner og arbejdsgange

Dato: 1. november 2026. Gennemgået i den indloggede webapp samt på de offentlige informationssider.

## Hovedkonklusion

MyStockScanner samler aktieudvælgelse, fundamental analyse, værdiansættelse og teknisk timing i én arbejdsgang. Den centrale idé er at finde en virksomhed med tilstrækkelig kvalitet, undersøge dens pris og derefter vurdere timingen. Appen gør dette konkret gennem scorekort, dynamiske scannere, aktiekort, scenariegrafer og lister.

Den vigtigste detalje er, at den samlede MyStockScanner-score og timingzonen er to forskellige vurderinger. Appen forklarer direkte, at MyStockScanner-scoren er gennemsnittet af moat, kvalitet og MyStockScanner-værdiansættelse. Timing vurderes separat.

Dette dokument beskriver observeret funktionalitet. Det er ikke en kontrol af dataleverandørernes tal eller en validering af strategiernes afkast.

## 1. Navigation og dashboard

Hovednavigationen indeholder Hjem, Aktiekort, Forum, Temaer, Watchlists, Porteføljer, Værktøjer og Akademi. Der findes også en global tickersøgning og en Udforsker, der kan åbnes som sidepanel.

Dashboardet viste:

- En introduktionsguide med syv trin og registreret fremdrift.
- Fortsæt din læring og adgang til kurser.
- En mulighedsliste med aktier og scores.
- Populære aktier med kurs og procentændring.
- Senest viste aktier.
- En knap til at redigere dashboardet.

Mulighedslisten indeholder ticker, børs, handelsvaluta, lukkekurs, markedsværdi, aktiekortstatus, QVMS-scorer og timingzone. Markedsværdier blev på dashboardet vist i GBP, selv for aktier med USD eller EUR som handelsvaluta. Scanneren havde samtidig DKK som valuta for markedsværdifilteret. Man skal derfor holde handelsvaluta og visnings-/filtervaluta adskilt.

## 2. Aktiesiden og scorekortet

Novo Nordisk B blev brugt som konkret eksempel. Aktiesiden havde Playbook, Resumé og Værdiansættelser samt adgang til yderligere visninger. Der var knapper til watchlist, aktiekort og kommentarer.

Playbook samler:

- Næste regnskab og tidspunkt i forhold til børsåbning.
- Markedsværdi, virksomhedsværdi og udbytteprocent.
- Virksomhedsbeskrivelse.
- MyStockScanner-scorekort.
- Aktiekort med aktien, dens branche og sektor.
- Valuegraf og kursdiagram.

Observerede værdier for NOVO-B under gennemgangen:

| Felt | Vist værdi |
|---|---|
| Kurs i listevisning | 266,10 DKK |
| Samlet MyStockScanner-score | 78/100, God |
| Kvalitet | 61/100, God |
| MSS-værdiansættelse | 87/100, Billig |
| Moat | 86/100, God |
| Timing | Købszone |
| Egen værdiansættelse | Ingen angivet |
| Næste regnskab | 4. november 2026, før åbning |
| Udbytteprocent | 4,48 % |

Tallene er appens viste øjebliksbillede, ikke selvstændigt verificerede markedsdata. Gennemsnittet af 61, 87 og 86 er 78, hvilket stemmer med scorekortets forklaring.

## 3. Hvad kvalitetsscoren viser

Et klik på kvalitetsscoren åbner et detaljepanel i Playbook. Appens beskrivelse knytter kvalitet til virksomhedens historiske holdbarhed og indtjeningsevne, vækst, kapitalafkast og balancestyrke.

Panelet indeholdt:

- MyStockScanner-kvalitetsscore og en særskilt Kvalitets-StockScore.
- Indtjening pr. aktie med rapporterede tal og estimater.
- PEG.
- Frit cashflow pr. aktie.
- Omsætning med historik og estimater.
- Revisioner af analytikerestimater.
- Moat-score.
- ROCE, ROE og ROIC.
- Price to free cashflow, current ratio og rentedækning.

Et vigtigt skel: NOVO-B havde MSS-kvalitet 61, men Kvalitets-StockScore 99. De to betegnelser er altså ikke udskiftelige. De præcise beregningsregler og vægte blev ikke fastlagt ved denne gennemgang.

## 4. Værdiansættelse og Valuegraf

Fanen Værdiansættelser åbner en model med historisk kurs, værdiansættelseskanaler og fremadrettede scenarier. Der var separate faner for Historical Data og Analytiker-scorekort.

Modellens estimattyper omfatter indtjening, omsætning, frit cashflow, driftslikviditet, bogført værdi og tangibel bogført værdi. Antallet af fremtidige år kan vælges.

I den observerede indtjeningsmodel beregnes en scenariepris som:

`Fremtidig indtjening pr. aktie × valgt P/E = anslået aktiepris`

Tabellen viste dette udtrykkeligt. For NOVO-B blev EPS for 2027 vist som cirka 22,19 DKK, med følgende scenarier:

| Scenarie | P/E | Anslået pris | Vist samlet afkast |
|---|---:|---:|---:|
| Bull | 22,77 | 505,30 DKK | +89,9 % |
| Standard | 16,59 | 368,16 DKK | +38,4 % |
| Bear | 10,41 | 231,01 DKK | -13,2 % |
| Analytikere | 13,43 | 298,03 DKK | +12,0 % |

Her var EPS næsten ens på tværs af scenarierne, mens multiplen varierede. Forskellen i scenariepriser kom derfor i dette eksempel primært fra P/E-antagelsen.

Der var valg mellem manuel multipel, aktuelle multipler, estimatbaserede multipler og historiske gennemsnit over 3, 5, 10 og 20 år. Modellen viste knapper til at synkronisere med analytikerestimater, nulstille, annullere og gemme. Flere estimatfelter var låst i den aktuelle adgang. Jeg ændrede eller gemte ingen modelværdier.

Afkastbokse var mærket “over 2 år”, mens den årlige procent ikke umiddelbart svarede til almindelig annualisering over præcis to år. Eksempelvis stod standardscenariet som +38,4 % samlet og +30,8 % årligt. Det kan skyldes den faktiske resterende tid frem til prognosedatoen. Beregningskonventionen blev ikke verificeret og bør afklares før genbrug af de årlige afkasttal.

## 5. Udforsker og screening

Udforsker er et sidepanel med kildevalg, resultater, filtre, søgning i den aktuelle liste, kolonnevalg, fuld tabelvisning, sortering og en Export-knap. Eksportformatet blev ikke testet.

Kildevalg viste alle aktier, åbning af en liste, oprettelse af en ny watchlist og senest brugte scannere/porteføljer. Scanneren er dermed tæt integreret med de samme listevisninger som watchlists og porteføljer.

Den aktuelle scanner hed “MSS - Europe - Value + strong/conviction buy” og viste 79 resultater ved opslaget. Filterpanelet viste seks aktive filtre og både Enkel og Avanceret redigering.

Konkret observeret opsætning:

| Filter | Værdi |
|---|---|
| Lande | DK, GB og syv yderligere valgte lande |
| Minimum markedsværdi | 5 mia. DKK |
| Minimum MSS-kvalitet | 60 |
| Minimum MSS-værdiansættelse | 60 |
| Timingzoner | Købszone, Stærk købszone, Købszone med overbevisning |
| Minimum samlet MSS-score | 0 |

De syv øvrige lande blev ikke udfoldet. For hver af de tre købszoner kunne signalforekomst vælges som Alle, Første eller Efterfølgende. UI-teksten forklarede, at enhver valgt zone matcher, og at Alle omfatter både første og efterfølgende signaler.

Der var også en sektion for strategistatus og mulighed for flere filtre. Avancerede filterudtryk blev ikke undersøgt.

### Uoverensstemmelse mellem navn og indhold

Scannernavnet fremhæver stærk/overbevisende køb, men de aktive filtre accepterede også almindelig Købszone. Listebeskrivelsen nævnte også alle tre købszoner. Filterindholdet er derfor mere præcist end navnet. Beskrivelsen bruger formuleringen “over 60”, mens feltet hedder Minimum og viser 60; inklusion af præcis 60 blev ikke testet.

## 6. Listebiblioteket og færdige strategier

Watchlists-siden er i praksis et fælles bibliotek for lister, scannere, porteføljer og temaer. Den har søgning, kort-/tabelvisning og filtre for ejer: Mine, MSS og Andet. Der er også favoritter og en knap til ny liste.

Observerede færdige scannere omfattede europæiske og amerikanske købszoner, skandinavisk værdi, mulighedslister til forskellige investortyper og swing-scanning.

Swing-scannerens beskrivelse angav Danmark og USA, markedsværdi mindst 1 mia. DKK, køb/stærkt køb/overbevisende køb eller behold, grøn daglig MTI, oversolgt daglig TPI, lukkekurs over 200 SMA og en lukkekurs højere end dagen før. Dette er beskrivelsens regler; det underliggende filter blev ikke særskilt kontrolleret.

En liste kaldet “Verdensomspændende daglig scanning” havde en beskrivelse, der sagde europæiske aktier. Også her bør man kontrollere filtrene frem for at stole på navnet.

Flere scannerbeskrivelser henviser til seneste kursopdatering fra dagen før. De bør derfor ikke uden videre forstås som intradagsscannere. Den generelle opdateringsfrekvens og eventuel kursforsinkelse blev ikke fastlagt.

## 7. Aktiekort

Aktiekortet viser fire kvadranter: Forbedring, Førende, Halter efter og Svækkelse. Der er bevægelsesspor og retning angivet i grader. UI forklarer vinkelretningerne som 0° op, 90° højre, 180° ned og 270° venstre.

Regionsvisningen viste fem regionsgrupper, og kontrolpanelet havde sporlængde på otte uger samt sektionerne Analyse, Hurtigt filter og Flere indstillinger. Der var en alternativ visning “Aktier i bevægelse”. Instruktionen sagde, at man kan vælge en gruppe eller aktie og holde markøren over et ugepunkt for at se afkast frem til sporets slutdato.

På aktiesiden kan aktie, branche og sektor sammenlignes. NOVO-B var eksempelvis i Halter efter med en bevægelsesretning tæt på opad. Det demonstrerer, at kvadrant og bevægelsesretning er forskellige oplysninger.

De præcise akseberegninger, benchmark og normalisering blev ikke fastlagt. Kortet bør derfor ikke fortolkes som en dokumenteret sandsynlighedsmodel ud fra denne gennemgang alene.

## 8. Porteføljer

Porteføljeoversigten indeholder egne, MSS' og andres porteføljer, søgning, visningsvalg og adgang til algoporteføljer. Tabellen har afkast for 1 dag, 1 uge, 1 måned, år til dato og samlet afkast samt scores og timingfordeling.

Modelporteføljen “3-PointPlaybook Live Performance” havde fanerne Resumé, Positioner og Transactions. Positionsvisningen viste 13 åbne, 194 lukkede og 207 positioner i alt. Tabellen viste blandt andet timingzone, aktiekort, retning, ind-/udgangsdatoer, dage i position og antal.

Biblioteket indeholdt også strategier mærket Experimental, blandt andet Quality Momentum, Value Momentum, Value Quality og TPI+. Deres resultater, handelsomkostninger, benchmark og eventuelle backtestantagelser blev ikke valideret.

## 9. Temaer, værktøjer og læring

Temaer optræder som kuraterede aktiegrupper med beskrivelse, scores og timingfordeling i listebiblioteket. Eksempler var AI-strømforsyning, cybersikkerhed, europæisk forsvar, batteriteknologi og danske aktier. Detaljesiderne for de enkelte temaer blev ikke gennemgået.

Værktøjssiden gav adgang til aktiekalender og pensionsberegner. Beregnernes konkrete felter og regnemetoder blev ikke testet.

Akademiet viste en platformsguide med 167 lektioner og andre kurser om Playbook, investering, teknisk analyse, algoritmer og begreber. Flere kurser stod som abonnementskrævende, selv om appen samtidig viste en igangværende prøveperiode. Faktisk adgang skal derfor vurderes pr. funktion. Kursusindholdet blev ikke afspillet.

Forum er tilgængeligt i hovednavigationen, men indlæggene blev ikke gennemgået.

## 10. Samlet forståelse af arbejdsgangen

En naturlig arbejdsgang ud fra appens struktur er:

1. Vælg et aktieunivers eller en færdig scanner.
2. Afgræns på størrelse, kvalitet og værdiansættelse.
3. Se timingzoner og signalforekomst.
4. Åbn aktiens Playbook og kontroller scorekomponenterne.
5. Læs kvalitetstal, estimater og revisioner.
6. Undersøg flere værdiansættelsesscenarier og deres antagelser.
7. Sammenhold aktiens udvikling med branche og sektor på aktiekortet.
8. Organisér videre research i watchlists og følg positioner i porteføljer.

Hvis dette senere skal bruges som reference til en AI-aktiescanner, er de mest nyttige principper: adskil kvalitet, pris og timing; vis begrundelser bag scores; gør scannerregler synlige; skeln mellem observerede tal og prognoser; vis datodækning og valuta; og lad scenariernes antagelser være gennemskuelige. Dette er mine designobservationer, ikke en beskrivelse af et allerede bygget system.

## 11. Hvad der stadig mangler at blive verificeret

- De præcise formler, vægte og tærskler for kvalitet, moat, værdi og timing.
- Om scoreberegninger er sammenlignelige på tværs af sektorer og selskaber med manglende data.
- Dataleverandører, forsinkelse, opdateringsfrekvens og behandling af selskabshændelser.
- MTI-/TPI-formler, tidshorisonter og forskellen mellem første og efterfølgende signal.
- Aktiekortets benchmark, akser og normalisering.
- Den årlige afkastberegning i scenarierne.
- Eksportformat, eventuelle API-muligheder og datarettigheder.
- Avancerede filtre og præcis grænseadfærd ved minimumværdier.
- Porteføljernes afkastmetode, kontantandel, valuta, udbytter, omkostninger og historiske ændringer.

Der blev ikke foretaget handler, købt abonnement, oprettet lister eller gemt ændringer i værdiansættelser. Navigation kan have opdateret appens oversigt over senest viste aktier.

## Kilder og genveje

- [Offentlig platformbeskrivelse](https://mystockscanner.com/platform/)
- [Offentlig beskrivelse af 3-PointPlaybook](https://mystockscanner.com/3-pointplaybook/)
- [Dashboard](https://app.mystockscanner.com/)
- [NOVO-B Playbook](https://app.mystockscanner.com/Security/182562/SecurityPlaybook)
- [NOVO-B værdiansættelse](https://app.mystockscanner.com/Security/182562/SecurityValueChart)
- [Lister og scannere](https://app.mystockscanner.com/Watchlists)
- [Europæisk value-scanner](https://app.mystockscanner.com/Watchlist/14480/WatchlistTable)
- [Aktiekort](https://app.mystockscanner.com/StockMapExplorer/Regions)
- [Porteføljer](https://app.mystockscanner.com/Portfolios)
- [Playbook-modelportefølje](https://app.mystockscanner.com/Portfolio/1321/PortfolioPositions)
- [Værktøjer](https://app.mystockscanner.com/Tools)
- [Akademi](https://app.mystockscanner.com/Course)

App-links kræver muligvis login og relevant adgang. Noterne bygger primært på direkte observation i appen; offentlige salgspåstande om performance er ikke anvendt som dokumentation for investeringsresultater.

## 12. Supplerende gennemgang: Playbook og Resumé

Begge faner er nu gennemgået direkte på NOVO-B. Playbook var med i den oprindelige gennemgang; Resumé er tilføjet i denne opfølgning.

### Forskellen mellem de to faner

| Fane | Formål og indhold |
|---|---|
| Playbook | Samler vurderingen: kvalitet, værdiansættelse, moat, timing, aktiekort og scenarier. Scorefelter kan åbnes til detaljer. |
| Resumé | Samler datagrundlaget: regnskaber, historiske og aktuelle multipler, prognoser, risiko, momentum og flere forskellige scorefamilier. |

Min fortolkning af arbejdsgangen er: Brug Playbook til at få overblik over vurderingen, og Resumé til at kontrollere tallene og finde forhold, der kræver mere analyse.

### Playbook: timingpanelet

Et klik på Timingzone åbner en konkret signalhistorik. For NOVO-B stod data pr. 30. oktober 2026:

- Købszone aktiv.
- Første købszonesignal: 18. september 2026, vist kursafkast -5,49 %.
- Et efterfølgende signal: 16. oktober 2026, vist kursafkast +2,50 %.
- Ingen stærke eller overbevisende købssignaler i det aktuelle kvadrantophold.
- Strategiens indgang: 18. september 2026.
- Seneste viste udgangsdato under Salgszone: 31. juli 2026.

Appens forklaring af signalafkast er særlig nyttig: Det måles fra lukkekursen ved signalet til seneste lukkekurs, justeret for split. Udbytte og handelsomkostninger er ikke med. Signalerne beskriver strategien og er ikke brugerens porteføljebeholdninger. Signaler i en igangværende uge kan ændres, før ugen er afsluttet.

Dette afklarer dele af de tidligere åbne spørgsmål om første/efterfølgende signal og afkastmetode for signaler. Det afklarer ikke nødvendigvis modelporteføljernes afkastmetode.

### Resumé: faktisk indhold

Resumé indeholder først de samme virksomhedsoplysninger som Playbook samt et kursdiagram med 1, 3 og 5 år eller hele perioden. Derefter følger en omfattende finansiel oversigt, i eksemplet med regnskabstal i millioner DKK.

Sektionerne omfatter:

- Omsætning og driftsresultat.
- Nettoresultat, EBIT, EBITDA, EPS og vækstrater.
- P/E, PEG, P/B, pris/tangibel bogført værdi, P/FCF, P/S og EV/EBITDA.
- Brutto- og driftsmargin samt ROA, ROCE, ROE og ROIC.
- Udbyttedækning via indtjening og frit cashflow.
- Driftscashflow, capex og frit cashflow pr. aktie.
- Gearing, likviditet, current ratio, quick ratio og rentedækning.
- Kontanter, arbejdskapital, nettogæld, aktiver, bogført værdi og antal aktier.
- MSS-scorer, aktiekort, MTI og TPI.
- En separat gruppe algoritmescorer.
- Prognoser og seneste værdiansættelser.
- Company Health med F-Score og Altman Z-Score.
- Momentum: kursafkast, volumenændring og afstand til 52-ugers top samt 50- og 200-dages gennemsnit.

Historiske tal for 2024 og 2025 stod sammen med estimater mærket 2026E og 2027E, hvor disse var tilgængelige. Manglende værdier blev vist som tomme felter eller streger.

### Tre vigtige fund i Resumé

**1. Historiske og aktuelle multipler skal adskilles.** Den finansielle oversigt siger udtrykkeligt, at den bruger kurser fra regnskabsperiodens slutdato til beregning af nøgletal. Længere nede findes en separat sektion med seneste værdiansættelser, mærket ann. og stm. Forkortelsen stm blev ikke afklaret. Man bør ikke sammenligne alle P/E-tal på siden som om de er beregnet på samme dato og periodegrundlag.

**2. Der findes forskellige scorefamilier.** NOVO-B viste MSS-score 78, kvalitet 61, MSS-værdi 87 og moat 86. Algoritmescorerne var derimod værdi 58, kvalitet 99, momentum 32 og Aktie Score 74. Algoritmescoren er altså ikke samme score som MSS-scorekortet. De præcise algoritmeformler er fortsat uafklarede.

**3. Risiko og pengestrømme giver ekstra kontekst.** Eksemplet viste F-Score 6/9 og Altman Z-Score 3,70. Frit cashflow pr. aktie faldt fra 15,61 i 2024 til 6,52 i 2025, mens capex pr. aktie steg fra 11,50 til 20,25. Udbyttets FCF-dækning stod til 0,6 i 2025. Disse tal gør det muligt at undersøge, hvad en samlet score eventuelt skjuler. Tallene er appens data, ikke eksternt kontrolleret.

### Forbehold om egen værdiansættelse

Ved første opslag viste Playbook ingen egen værdiansættelse. Ved opfølgningen viste både Playbook og Resumé en egen værdiansættelsesscore på 87, og Valuegraf var mærket som baseret på brugerens indstillinger. Jeg havde ikke klikket Gem eller ændret modellens felter. Årsagen til ændringen i visningen er derfor ikke fastlagt; den kan ikke bruges som bevis for en bevidst gemt brugerværdiansættelse.

[Resumé for NOVO-B](https://app.mystockscanner.com/Security/182562/SecuritySummary)

## 13. Udvidet gennemklikning af platformen

### Flere aktiefaner

Menuen Mere på aktiesiden giver adgang til Sammenlignelige selskaber, Analytikere, Seasonality, Fundamentaler og Udbytte. Disse blev åbnet på NOVO-B.

- **Sammenlignelige selskaber:** branchebaseret peer-liste med globalt, regionalt og nationalt univers, søgning, markedsværdi, scores, timing og Explorer-genveje. Appen advarede om aktive filtre: listen viste derfor kun en del af universet. Flere noteringer af samme virksomhed kunne optræde.
- **Analytikere:** fremtidige EPS-/omsætningsestimater, kursmål, revisionernes historik og scorekort med faktiske GAAP-/Non-GAAP-tal, estimater og overraskelser. Omsætning og perioden 3M blev afprøvet og ændrede grafen. NOVO havde ingen analytikeranbefalinger i anbefalingsboksen, selv om estimater og kursmål fandtes. Grafens aksebeskrivelser brugte USD, mens kortene brugte DKK; enhederne kræver kontrol.
- **Seasonality:** månedligt gennemsnit, median, andel positive måneder og år-for-år-afkast. En slider vælger antal historiske år; den stod på 10. Historiske sæsonmønstre er ikke dokumentation for fremtidigt afkast.
- **Fundamentaler:** nøgletal, resultatopgørelse, balance og pengestrømme; årlig, seneste tolv måneder eller mellemliggende periode. Pengestrømsfanen blev afprøvet. Opgørelserne har kompakt/udvidet visning og lang historik; årsoversigten for NOVO gik tilbage til 1990.
- **Udbytte:** historisk og fremadrettet udbytteprocent, forventet årsbeløb, grafer for udbytte og dækning samt udbetalingshistorik med ex-dato, betalingsdato, type, beløb og split. NOVO viste trailing yield 4,40 %, forward yield 4,48 % og forventet årsbeløb 11,92 DKK. Næste ex-dato var tom.

### Playbook og historisk værdiansættelse

Moat-panelet viste faktorer for indtjeningsholdbarhed, marginstyrke/stabilitet, cashflow, vækstkvalitet, balance, kapitaleffektivitet og disciplin over for aktionærerne. For NOVO var alle listet som støttende og ingen som svækkende. De numeriske vægte blev ikke vist.

Klik på MSS-værdiansættelsesscoren førte til værdiansættelsesfanen. Historical Data blev åbnet: her vises historiske vækstrater og multipler for 20, 10, 5 og 3 år samt aktuelle årlige tal, LTM og estimater. Historiske EPS-, P/E- og kurstal vises også pr. år.

### Aktiekortets indstillinger

- Analyse åbner valg af sporets slutdato med ugenavigation; datoen var 30. oktober 2026.
- Hurtigt filter giver kvadranter og et vinkelinterval med inkluderede endepunkter. Et interval med start større end slut krydser 0 grader.
- Flere indstillinger giver maksimum antal værdipapirer, benchmark og EMA/SMA. Appen forklarer, at relativ styrke måles mod det valgte benchmark. EMA reagerer hurtigere, mens SMA vægter perioder ens.
- Klik på Europe gav 21 lande og mulighed for at skifte mellem lande og sektorer. Det er således muligt at bevæge sig gennem et geografisk hierarki.

### Kalender, pension, forum og temaer

Kalenderen kan bruge favoritlister, alle aktier eller en valgt liste, med lande- og begivenhedsfiltre. Begivenheder omfatter regnskab og ex-udbytte; den danske etiket Ekskl. udbytte ser ud til at være en oversættelse af ex-dividend. En tom kalender afhænger af kildevalget og er ikke i sig selv bevis for, at der ingen markedsbegivenheder er.

Pensionsberegneren har alder, investeringer, udbetalingsrate, årlig indkomststigning, skat, fordeling på aktier/obligationer/kontanter, afkast, udbytte og bidragsperioder. Den kan beregne beløb ved en pensionsalder eller alder ved en ønsket årsindkomst. Beregningsmodellen blev ikke selvstændigt valideret.

Forum har søgning, type-/tagfiltre, ulæste indlæg og kort-/feedvisning. Research Coverage er en særskilt oversigt over dækkede selskaber med seneste analyse, scenarier og Playbook-vurdering; der findes filtre for status, kvalitet, værdi og timing.

AI-Power-temaet blev åbnet og segmentet Kernekraft/Uran afprøvet. Segmentvalget ændrede beholdninger, scores og afkaststatistikker. Temaet har benchmark RSP og viser samlet afkast, CAGR, Sharpe, drawdown og beta. Appen beskriver temaprisen som et markedsværdivægtet indeks, der rebalanceres dagligt. Temaet var oprettet 12. august 2026, men havde afkaststart 31. december 2025. Historikken indeholder derfor en periode før udgivelsen og må ikke uden videre fortolkes som live-performance siden lancering. Hele temaet havde 56 aktier, fem segmenter og fem artikler.

## 14. Oprettet research-watchlist

Efter brugerens tilladelse blev en manuel liste oprettet: **AI Stock Scanner – research**, ID 14814.

[Åbn listen](https://app.mystockscanner.com/Watchlist/14814/WatchlistTable)

Listen indeholder nu seks værdipapirer:

| Ticker/børs | Selskab | Rolle i observationslisten |
|---|---|---|
| NOVO-B / CO | Novo Nordisk | Sundhed |
| MSFT / NASDAQ | Microsoft | Software/cloud |
| V / NYSE | Visa Class A | Betalinger |
| ASML / AS | ASML | Halvlederudstyr |
| CAT / NYSE | Caterpillar | Industri |
| HY9H / F | SK HYNIX GDR 144A/REGS 1 | Tilføjet efter brugerens konkrete ønske |

De første fem blev valgt som en lille tværgående researchgruppe, ikke ud fra en fuld investeringsanalyse. HY9H er Frankfurt-noteringen i EUR og et GDR-papir. Tilføjelsen blev bekræftet i tabelvisningen med seks resultater.

Watchlist-oprettelse bruger navn, beskrivelse, manuel liste/dynamisk scanning og valgfri favoritmarkering. Symbolsøgningen blander almindelige aktier, andre noteringer, CDR'er og ETF/ETP-produkter, herunder gearede produkter. Derfor blev den konkrete børs og instrumentbetegnelse kontrolleret ved hver tilføjelse.

Listen har Dashboard, Tabelvisning, Heatmap og Aktiekort. Dashboard og heatmap blev åbnet. Dashboard viser kalender, beskrivelse, købs-/salgsoversigt, dagsbevægelser, samlede scorer og timingfordeling. Heatmap giver historikperiode og størrelse efter markedsværdi eller performance samt vinder-/taberlister. Den stod på én uge.

En mulig inkonsistens blev observeret før HY9H blev tilføjet: tabellen viste MSFT og Visa som Neutral, mens dashboardets timingfordeling viste to i Salgszone; en anden salgsoversigt viste nul. Det blev ikke afklaret, om dette skyldes indlæsning, forskellige grupperingsregler eller en visningsfejl.

Tidligere afsnits udsagn om, at ingen lister var oprettet, gælder kun den første gennemgang. Denne liste er nu oprettet efter udtrykkelig tilladelse. Ingen køb eller salg af værdipapirer blev foretaget.

### HY9H.F og bekræftet sammenligning

HY9H.F blev tilføjet og scorekortet åbnet. MSS-score var 86, kvalitet 94 (Excellent), værdiansættelse 91 (Meget billig), moat 75 (God), og timing Købszone med overbevisning. Kursen i listen var 978 EUR. Aktiekortet viste Svækkelse; høj fundamental score og købszone er derfor ikke ensbetydende med, at alle tekniske visninger er positive. Retningen var 298 grader i listen og 270 grader på Playbook ved opslaget; forskellen blev ikke afklaret.

Det færdige tabelbillede viste:

| Selskab | Kvalitet | Værdi | Moat | MSS-score | Timing |
|---|---:|---:|---:|---:|---|
| Microsoft | 73 | 54 | 87 | 71 | Neutral |
| Visa | 84 | 38 | 93 | 72 | Neutral |
| HY9H.F | 94 | 91 | 75 | 86 | Købszone med overbevisning |
| ASML | 90 | 61 | 92 | 81 | Behold |
| Caterpillar | 82 | 71 | 72 | 75 | Behold |
| Novo Nordisk | 61 | 87 | 86 | 78 | Købszone |

HY9H.F havde således den højeste samlede MSS-score og kvalitetsscore blandt de seks på listen ved denne gennemgang. Scorerne er appens observationer pr. 1. november 2026 og er ikke en selvstændig købsanbefaling.

## 15. Stærk købszone versus købszone med overbevisning

Hjælpeknapperne for timing i både watchlist og Playbook viste ingen hjælpetopics. Den præcise regelmæssige forskel mellem Strong Buy og Conviction Buy blev derfor ikke verificeret. Betegnelserne antyder en rangorden, men dokumenterer ikke i sig selv højere sandsynlighed, afkast eller bestemte scoretærskler.

Ved dette nye opslag viste HY9H's Playbook MSS-score 88, værdi 94 og timing Behold, mens den tidligere liste viste 86, værdi 91 og Købszone med overbevisning. Timinghistorikken pr. 30. oktober 2026 viste første signal i alle tre købszoner den 14. august 2026 og Behold som aktiv. Signalafkastet stod til -10,29 %. Forskellen mellem visningerne blev ikke afklaret; tidligere beskrevne scorer og timing må læses som de konkrete observerede øjebliksbilleder.

