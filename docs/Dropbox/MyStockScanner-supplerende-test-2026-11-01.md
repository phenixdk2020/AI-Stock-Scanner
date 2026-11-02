# MyStockScanner – supplerende funktionstest

Opdateret 2. november 2026. T24–T52 fortsætter den oprindelige rapport med T01–T23. Disse resultater erstatter de tilsvarende åbne punkter i den første rapport. Tests er udført i samme indloggede konto; de er ikke en fuld godkendelse af alle kombinationer.

| ID | Resultat | Observation |
|---|---|---|
| T24 | Bestået | Gitter viser ni selskabskort med12måneders kursgraf,kurser,QVMS,timing. |
| T25 | Bestået | Ticker stigende1INN,ASML,CAT,HY9H,MSFT,NOVO,SOBI,SU,V; faldende testet. Multi-sort prioritet vises. |
| T26 | Bestået | Beskrivelse gemt efter eksplicit Tab ud af feltet og genåbning viser ny tekst omni selskaber. Første fill-forsøg blev ikke bundet til modellen; gentest med normal feltafslutning lykkedes. |
| T27 | Afvigelse | Kvalitetsminimum90 giverHY9H+1INN(2),ASML medvistQ90udelades. Minimum89giver3inklASML. Kan skyldes skjultdecimalpræcision eller streng>grænse; filterreaktion virker. |
| T28 | Bestået | Avanceret regel MSS≥90 giver1resultat,innoscripta92; regel vises korrekt og ugemtmarkering. |
| T29 | Bestået | Gem som scanner opretter AI Stock Scanner – MSS mindst90; ugemtmarkering forsvinder og regel≥90bevares. |
| T30 | Bestået | SystemlayoutKvalitetviser15kolonnermedROCE,vækst,Piotroski,Z-scoreogdata;valgbevaresovernybrowserforbindelse. |
| T31 | Bestået | EgetlayoutoprettetfraStandard,navngivetAI Stock Scanner – researchlayout,LastCloseDate tilføjetogflyttetførTiming. Gemningoganvendelsebekræftet;reload viser fortsatlayoutogkolonne. |
| T32 | Bestået | Novo basePE16,59->20 ændrer2027pris368,16->443,83DKK. Annuller gendanner16,59/368,16. Grafogtabelstemmer. |
| T33 | Bestået | P/E20gemtogreloadbevarer20og443,83DKK. |
| T34 | Bestået | Nulstilgendannerbase16,59/368,16;gemtigenforatfjernePE20test. |
| T35 | Bestået | HistoricalDatafanenviserEPS/PE/priser2016-2025,CurrentAnnualogLTM;analytiskPE11,56vs10,14ogEPS23,02vs26,25. |
| T36 | Blokeret | TradingView-sideåbner,meniframeer visuelt blankuden graf/tidsrammer. DOMviserkuniframeogPoweredby. Derforingenfunktionellekontrollerforcandles,indikatorerellertegningerkanudføresidennebrowser. |
| T37 | Bestået | Sporlængde8->7->8;analysedato30okt->23okt;historiskmarkørvises;Nulstiltilsenestelukkekursgendanner30okt. |
| T38 | Bestået | EMA->SMAændrervalgtstatusogkortberegnespåny;EMA gendannet. |
| T39 | Bestået | FravalgSvækkelsefjernerNorthAmericafra5til4;gendannet5. Vinkel0-90giveringenregioner,0-360gendannet. |
| T40 | Bestået | Maksantalminimum50,trin10;50->60->50testet. Kun5regioner,såreelafskæringaf>50ikkeprøvet. |
| T41 | Delvis | Aktieribevægelseindlæser857aktier. Gruppernes søgningDenmarkviserDanmarkmedunderbrancher. Indstillingerviserobjekttyper,vinkel,kvadrant,kvalitet,værdi,timing;ændringerikkeanvendt. |
| T42 | Bestået | Kendt nulafkasttest:100000kapital,allekapitalafkast/udbytter0,udbetaling0giver100000fraalder17til100. |
| T43 | Bestået | Bidragsperiode30-65,12000,3%:alder29=0,30=12000,31=12360,65=0. Slutalder65eksklusiv iobserveretberegning. |
| T44 | Delvis | Omvendtberegning24000årsindkomstændrerresultatoverskrifttilPensionsaldermedenindkomstpå24000oggrafgenberegnes;præcisalderikkeselvstændigtvalideret. |
| T45 | Bestået | Forumsøgningpåhelartikeloverskriftgiverpræcistimingbacktestartiklen. |
| T46 | Bestået | Forumartikel3299ogkommentarerindlæses.Lydafspilskiftertilpause;pausegendannerafspil.Lydindholdikkefuldtaflyttet. |
| T47 | Bestået | Kort->Feedændrervisningtilartikelrække;Kortgendannetogsøgningryddet. |
| T48 | Delvis | OpretnytopslagåbnerType,Sprog,titel,indhold,medier,tags;Annullerredigeringreturnerertilforumudenopslag.Gem/publiceringikkeudført. |
| T49 | Bestået | Seasonality10->9årændrerjanuargennemsnit1,7%->2,2%,grafogtabelogårsantal.Gendannet10år. |
| T50 | Bestået | TPI-video74sekstarter:afspillerpaused=false,currentTime9,42sek,readyState4ogbillederændres. Fuldvideoikkeaflyttetellerindholdvalideret. |
| T51 | Bestået | NæstefraTPI104tilSeasonality105virker;tekstlæst.Markérsomfuldførtøgerkursusfremskridtfra0til1;knapforsvinder. Dennelektionsfuldførelseerefterladt,ingenfortrydknapvist. |
| T52 | Bestået | 390x844mobil:menuåbner/lukkeroghar8hovedlinks;niaktierindlæses,tabelkanrullehorisontalt,søgning/timing/importeksporttilgængelige. Reklamefyldermegetoglogoafkortes;ingenfuldmobilaccepttest. |

## Ændringer på kontoen

- Listen har fortsat ni selskaber. Beskrivelsen er opdateret til alle ni.
- Scanneren AI Stock Scanner – MSS mindst 90 er gemt.
- Eget layout AI Stock Scanner – researchlayout er gemt med Last Close Date før Timingzone. Layoutet blev senere set igen efter navigation og mobiltest.
- Novo-scenariets P/E blev midlertidigt ændret til 20, gemt og kontrolleret efter genindlæsning. Standardværdierne blev derefter gendannet og gemt.
- Aktiekortets spor, dato, beregningsmetode og filtre er gendannet.
- Pensionsberegnerens testbidrag er fjernet og oprindelige afkast/input gendannet. Den omvendte beregning viste pensionsalder 52 ved den afprøvede årsindkomst 24000; denne alder er ikke selvstændigt modelvalideret.
- Seasonality-lektion 105 er markeret fuldført under funktionstesten. Ingen fortrydknap blev vist.
- Mobiltest ved 390 × 844 er afsluttet og viewport-override fjernet.
- Ingen handler, betalinger eller forumindlæg er gennemført.

## Ny timingdokumentation

Artiklen BACKTEST AF VORES NYE TIMING-INDIKATOR, dateret 30. oktober 2026, blev åbnet. Den beskriver udvikling på 2003–2019 og test på 2019–2026. Appens rapporterede gennemsnit pr. handel var 5,33 % for Buy, 12,93 % for Strong Buy og 16,68 % for Conviction Buy. Det er udbyderens backtestresultater, ikke uafhængigt verificerede forventninger. Artiklen siger, at deres fremtidige handler foretages mandage. Den offentliggør ikke den præcise formel for entry eller signalniveauerne.

[Åbn artiklen](https://app.mystockscanner.com/Forum/1/ForumItem/3299/BACKTEST+AF+VORES+NYE+TIMING-INDIKATOR)

## Vigtigste nye afvigelser

- Minimum kvalitet 90 udelod ASML med vist kvalitet 90, mens minimum 89 inkluderede den. Skjulte decimaler eller en streng sammenligningsgrænse er mulige forklaringer.
- TradingView-grafen stod tom i browseren. Candles, tegninger og indikatorer kunne derfor ikke sluttestes der.
- Layouteditoren viste enkelte tekstkodningsfejl, eksempelvis PortefÃ¸ljedatoer.

Tilbageværende begrænsninger omfatter bl.a. betalings- og loginforløb, emaillevering, permanent sletning, låst indhold, fuld krydsbrowser-/tilgængelighedstest, alle filterkombinationer og en uafhængig revision af scoremodeller. Åbnede formularer tæller ikke som en gennemført publicering eller transaktion.

## Seneste status – 2. november 2026

Der er nu 59 nummererede testtilfælde. T53–T59 er dokumenteret i den løbende emnelog: ukendt importticker, daterede HY9H-snapshots, kalender med konkret watchlist, regnskabsfilter, globale/regionale/nationale peergrupper, notifikationsmenu og slutkontrol af ni aktier.

HY9H-tabellen viser Last Close Date 29.10.2026, mens Playbooks timingpanel viser Pr.30.10.2026. Det dokumenterer forskellige datodækninger og er en mulig forklaring på de tidligere modstridende værdier; årsagen er ikke endeligt fastslået. Kalenderen viser Novo-regnskab 4.november, når researchlisten vælges som kilde.

Kontoens ni aktier er bevaret. Kalenderen er sat tilbage til Favoritlister med regnskabsfilter til. Peervisningen er sat tilbage til Global. Ingen betalinger, handler, emailbeskeder eller forumopslag er gennemført.

Se `00-Laes-mig.md` for dokumentoversigt og `MyStockScanner-loebende-emnelog-2026-11-02.md` for den nyeste emnevise dokumentation. Åbne og blokerede tests er fortsat ikke en godkendelse af alle funktioner.
