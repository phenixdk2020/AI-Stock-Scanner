# MyStockScanner: solide bull-aktier, entry og exit – og hvad vi selv bygger og tester

Dato: 02-11-2026. Status: arbejdsdokument til fase 5 (timing-zoner med egne regler + backtest).

**Ikke investeringsrådgivning.** Dokumentet beskriver, hvad MyStockScanners (MSS) videoer *siger* om metoden, og hvad vi selv vil teste. Intet her er en købs- eller salgsanbefaling. MSS' formler og tærskler er ikke offentlige; vi kopierer dem ikke, men bygger en egen, åben model (se `docs/QUALITY-MODEL.md`). Alle MSS-tal er deres egne, ikke verificerede, og aktienavne er kun eksempler fra videoerne.

Kilder er Whisper-udskrifter i `data/video-transcripts/` (tidsstempler `[mm:ss]`). Udskrifterne har hørefejl; usikre steder er markeret "(usikkert)". Noterne bag dokumentet er udtræk, og påstande, der ikke holdt ved opslag i udskriften, er rettet (se afsnit 5b).

---

## 1. Kort resumé

1. MSS' metode ("3Point Playbook") kræver tre ja, før en aktie kommer på watchlist: kvalitetsvirksomhed, potentiale til kursstigning, og at timingen er rigtig nu (Green Hydrogen 00:59-01:21).
2. Udvælgelsen er et fundamentalt filter (kvalitetsscore 0-100, EPS/omsætning/ROCE/FCF/rentedækning) plus en værdi-/potentialevurdering; kvalitetsscoren skal være mindst 60, helst over 70 (Green Hydrogen 01:54-02:00). Selve formlen og de øvrige tærskler oplyses ikke.
3. Trend og relativ styrke: kursen over SMA200 (webinar 35:07-35:22) og en StockMap, der viser relativ styrke mod et benchmark i fire kvadranter (StockMap 02:21-03:40). Foretrukket benchmark er RSP (equal-weight S&P 500); SPY bruges som eksempel.
4. Timing: egne indikatorer (TPI, MTI, MTX). Signalet, de venter på, er "dobbelt grøn" (MTI på dags- og ugegraf), og de køber ikke, mens den langsigtede ugentlige trend er rød.
5. Exit: første alarm er brud under SMA50, og SMA200-brud er salg. Supertrend (ATR 10 gange en faktor, 3 eller 5) vises som alternativt stop. Automatiske stop-ordrer lægges som regel ikke ind (webinar 46:37-47:01).
6. Risiko: 0,5 % af kapitalen pr. handel (som eksempel i videoen) og en enkelt position på ca. 2,5-3,2 % af porteføljen, op til ca. 40 aktier. Der bruges ikke fast rebalancering, kun signaler.
7. MSS' egne tal (afkast 33-34 %, maks. drawdown ca. 7-8 %) er selvrapporterede, delvist bagudfyldte og ikke verificerede. Vi bruger dem som hypotese, ikke dokumentation.
8. Vores egne backtests på dagsdata (20 store aktier, 10 år, 0,1 % kurtage) viser kun en lille edge for candle-udløsere (kun hammer slår en tilfældig dag), og at tæt daytrading-stop passer dårligt til uge/måned-horisonten. Derfor foreslår vi bredere, trendbaseret exit og tester varianter out-of-sample (afsnit 7).

---

## 2. MSS' tre lag

### 2.1 Lag 1: udvælgelse (kvalitet, værdi, potentiale)

| Element | Hvad videoerne siger | Kilde |
|---|---|---|
| Tre-trins proces | (1) Er det en kvalitetsvirksomhed? (2) Er der potentiale/upside? (3) Er timingen rigtig? Dårlig kvalitet stopper processen. | Green Hydrogen 00:59-01:21; webinar 24:21-24:33 |
| Quality score | Egen score 0-100. "Minimum 60, men gerne over 70"; Green Hydrogen havde 17 og blev afvist. En score på 99 er top 1-2 % ifølge webinaret. | Green Hydrogen 01:43-02:03; webinar 25:16-25:27 |
| Kvalitetskriterier (grønne i platformen) | Stigende EPS, stigende omsætning, analytikernes estimater og tro peger op (uge/måned/3 mdr.), god og gerne stigende ROCE, positiv og helst stigende free cash flow, sund rentedækning. "De fleste grønne" = aktien er ok. Ingen tærskler. | Webinar 25:51-28:10 |
| Røde flag | Ingen overskud noget år, negativ driftsmargin og ROCE, negativ cash flow, Altman Z-røde flag, dårlig likviditet og negativ rentedækning. Aktien afvises. | Green Hydrogen 02:45-05:44 |
| Value | Value-percentil bygger på P/E, P/B, P/S og EV/EBITDA; Quality på ændringer i indtjening/kvalitet; Momentum; samlet "stock score". Alle rangeret som percentil i region. Eksempel: en aktie i 80-97 percentilen på alle tre. | Danske swing 08:12-08:53; Sådan vælger jeg 01:55-02:22 |
| Potentiale/værdikanal | Analytikernes forventede indtjening et par år frem gange en forventet P/E i tre cases (worst, base, bull) giver en "værdikanal". Er worst case meget negativ og upside lille, købes ikke. Historisk P/E bruges som billigt/dyrt niveau. | Webinar 30:51-33:52 |
| PEG | Under ca. 2-2,5 nævnt som værktøj, ikke hård regel (usikkert). | Webinar 49:18-49:25 |
| Nøgletal i et eksempel | P/E 10,6, ROIC 21,6 %, driftsmargin 18,1 %, Piotroski 6 af 9, konkursrisiko nær 0, rentedækning ca. 40 gange, udbytte dækket af earnings og FCF. Tallene er fra én aktie (DHI), ikke tærskler. | Sådan vælger jeg 03:05-05:58 |
| Negativ indtjeningstrend | "Ingen køb", selv om kursen kan se interessant ud (Pandora, Torm m.fl.). | Webinar 54:15-54:33 |
| Moat/MSS-score/bogstavkarakterer | Moat og Stability findes ikke i udskrifterne. Én video viser bogstavkarakterer A+ til F, men udskriften er ødelagt, og karakterernes grundlag er uklart (usikkert). | Webinar (oversigt); "From a superior A+ to a failing F" |
| Farvekode | En video viser grøn/rød pr. aktie uden at forklare, hvad farven bygger på. | "NEVER follow the hype!" 00:05-00:18 |

Bemærk: Green Hydrogen-videoen viser, at kvalitetsfilteret *er* et nej-filter først; timing kommer slet ikke i spil for dårlige aktier.

### 2.2 Lag 2: trend og relativ styrke

- **Trendfilter:** kursen skal ligge over SMA200 ("den sorte streg"), og "nye lavere bunde" er et nej (webinar 35:07-35:22, 43:45-44:04). I Playbook-eksemplerne bruges også SMA50 (afsnit 3).
- **StockMap** er en relativ-styrke-graf mod et benchmark med fire kvadranter (StockMap 02:21-03:40):
  - Grøn = leading (bedre end benchmark, og relativ styrke accelererer).
  - Gul = weakening (stadig bedre, men mister fart).
  - Rød = lagging (dårligere og falder).
  - Blå = improving (stadig dårligere, men accelererer mod 100-linjen).
  - Normal rotation er blå, grøn, gul, rød. Halen er standard 8 uger (StockMap 08:47-08:59).
- **Brug:** find først sektor/industrigruppe, der accelererer, og kig derefter på aktier i den (StockMap 13:23-13:30). Entryønske: aktier der "tipper op i blå" mod nulpunktet; gul er som regel salgssignal (StockMap 14:33-15:03). Videoen siger udtrykkeligt, at kvadranterne er tidlige tegn, ikke købs-/salgssignaler (StockMap 08:11-08:31). Til sidst filtreres med TPI, MTI dobbelt grøn og MTX (StockMap 13:30-13:43).
- **Benchmark, SPY mod RSP:** Der er ikke en egentlig modstrid, men to udsagn. StockMap-videoen bruger SPY som eksempel ("i det her tilfælde", StockMap 01:53) og siger, at man kan sætte ethvert benchmark ind (13:57). Intro-videoen siger "jeg kan godt lide at sammenligne med RSP" (Nyt i MSS - Intro 10:21), temavideoen måler "som regel" mod RSP (Tema-performance 02:11), og de automatiske porteføljer bruges mod RSP, så de største aktier ikke styrer indekset (Automatiske porteføljer 01:40-02:05). Konsekvens for os: vælg ét fast benchmark, og test begge (afsnit 7).
- **Temaer:** et nyt tema hver uge, valgt manuelt ud fra mediemonitorering og StockMap (Velkommen til Temaer 01:00-01:06; Tema-performance 01:25-01:35). Ingen exit-regel for temaer.

### 2.3 Lag 3: timing (TPI, MTI, MTX)

- **TPI (Turning Point Indicator):** statistisk indikator pr. aktie for over-/undervurdering på dags-, uge- og langsigtet plan. Den langsigtede ugentlige trend skal være grøn. Køb-området er "oversolgt akkumulering" og vent derefter på grønt; "overkøbt akkumulering" og en rød dag er salgsområde (Protector 01:21-01:55, 02:37-02:50; Intro 06:52-07:10). Farverne er ikke ens i alle videoer: oversolgt kaldes gul i nogle (Protector, Intro) og lyserød på ugegrafen i en anden (Danske swing 02:01) (usikkert, om det er forskellige versioner).
- **MTI (Momentum Trend Indicator):** måler kursen mod indeks og sektorer og er grøn, når aktien klarer sig bedre. MSS lægger den ofte ind to gange, én på daglig og én på ugentlig (Nye features 05:02-05:27). **"Dobbelt grøn"** er det, de venter på (Nye features 05:33-05:39). Dagsgrøn alene er kortsigtet swing, og er ugentlig MTI rød, er den overordnede trend ned (Nye features 05:42-05:55). I webinaret nævnes to MTI-varianter ("DAWS-MTI" og "UMTI", navnene er usikre), og dobbelt grøn + kurs over SMA200 er der, hvor de går med trenden (webinar 35:35-36:21).
- **MTX (Momentum Trend Explosion):** ny indikator oven på MTI (lysegrøn baggrund = i køb) (Nyt i MSS - Intro 07:50-08:00; StockMap 13:35-13:42). Formlen oplyses ikke.
- **"Triple green":** langsigtet TPI (uge) grøn og dags-TPI grøn (Sådan vælger jeg 08:43-08:59). Eksemplet DHI blev købt, da screeningen viste triple green; ugetrenden var lidt overkøbt, men dagsgrafen var ved at blive oversolgt (09:13-09:31).
- **Dags- og ugegraf:** ugegrafen vurderer, om trenden er intakt (webinar 47:11); hvornår dagsgrafen afgør, er uklart (usikkert).
- **Zoner:** webinaret bruger "billig zone"/"dyr zone" i værdikanalen. Købssignal = dobbelt grøn efter fald til nederste del af værdikanalen (webinar 34:06-34:13, 36:01-36:15). Udtrykkene "Købszone", "Stærk købszone", "Behold" og "Salgszone" findes ikke i de læste udskrifter.
- **Ikke købe:** dobbelt rød og nye lavere bunde (webinar 43:45-44:04), over "price for perfection" (41:07-41:11), lige før regnskab (46:14-46:17), og når langsigtet TPI er rød (Danske swing 02:36-02:45; Sådan vælger jeg 08:37-08:41).
- **Dags-/swing-entry i Danske swing:** vent på en grøn dag med god volumen, efter at TPI har været oversolgt (Danske swing 05:52-06:42). Målet for swing er ca. 5-7 % (14:53).
- **Hvad MSS ikke gør:** køber ikke på bunden ("vi kommer altid først med, når aktien har trendet et stykke", webinar 36:12-36:15) og skifter ikke regler midt i en periode (Styr din risiko 19:45-20:41).

---

## 3. Entry og exit/risiko

### 3.1 Entry

Der findes ingen enkelt, komplet entry-formel i kilderne. Det, der siges, er:

- Aktien har bestået kvalitet/potentiale (afsnit 2.1), ligger over SMA200, og MTI er dobbelt grøn (dags + uge) (webinar 35:07-36:21).
- Alternativ (Playbook-swing): langsigtet TPI grøn, dags-TPI grøn, helst efter en oversolgt periode (Sådan vælger jeg 08:43-09:31; Protector 01:21-02:03).
- Eksempel Royal Unibrew: købt efter brud op over SMA200 og dobbelt grøn MTI, og trenden blev fulgt uden stop-ordre (webinar 45:44-46:44).
- Eksempel Nvidia og Micron: MSS "kom ind", blev stoppet ud og kom ind igen; billetprisen for at være med i de store trends (Styr din risiko 07:44-09:19). Hvorfor entry skete, forklares ikke præcist.
- **50-dages SMA:** MSS siger, at "normalt" er trendlinjen SMA50 (lukkekurs), vist på dags- og ugegraf (Styr din risiko 07:25-07:39). Videoen angiver *ikke*, at et entry sker ved luk over SMA50; SMA50 beskrives som exit-/trendlinje. Entry ved Supertrend nævnes som dårligt, fordi aktien først skal stige meget (12:35-12:50).

### 3.2 Exit og stop

- **SMA50-brud** er første alarm. Ligger et gammelt støtteniveau tæt på, gives lidt "snor", men brydes det, går de ud (webinar 41:41-41:46, 61:44-62:26).
- **SMA200-brud** er salg; ligger SMA200 22 % væk, trækker de stikket før (webinar 62:30-62:46).
- **Supertrend som stop:** ATR (gennemsnitlig daglig bevægelse) over 10 dage gange en faktor. I videoen vises først ×10 som overdrivelse (et fald på 36 % fra toppen for Nvidia, 12:26-12:30), derefter ×7, og til sidst sammenlignes ×3 og ×5 (13:58-14:09). Stop med faktor 3 lå ca. 6 % væk og faktor 5 ca. 13-14 % væk i eksemplet (15:46-15:50). Tættere stop = kortere trend og mindre tab pr. aktie; længere stop = mere af trenden, men færre aktier for samme risiko.
- **Ingen automatisk stop-ordre som regel** (webinar 46:37-47:01): man "ved, hvor man vil ud", men lægger det sjældent ind, fordi kortvarige udsving stopper ud til værste kurs.
- **Stram stop ved overkøbt TPI** (Nye features 04:26-04:33; Intro).
- **Salg ved RS-svækkelse:** i StockMap ofte salg, når aktien er et stykke inde i gul (StockMap 14:55-15:03).
- **Swing-mål:** 5-7 % op, derefter tage gevinsten; ugentlig TPI til rød er salgssignal (Danske swing 04:00-04:24, 14:53). I Protector-videoen sælges i overkøbt zone på en rød dag; tre swingtrades på uger til måneder (Protector 02:37-05:16). Eksemplerne er gennemgået bagudrettet.

### 3.3 Positionsstørrelse

- **0,5 % risiko pr. handel:** antal aktier = tilladt tab / afstand til stop. I videoens TradingView-eksempel gav stop 6 % væk 378 aktier og stop 13-14 % væk 174 aktier for samme tab på 0,5 % af kapitalen (Styr din risiko 14:54-15:50). Det er en illustration af et hypotetisk køb "i dag", ikke en rapporteret handel.
- **Position i porteføljen:** MSS siger gennemgående 2,5-3,2 % af kapitalen pr. aktie (Styr din risiko 08:12-08:16; webinar 19:44-19:52), op til ca. 40 aktier, i praksis ca. 30 (webinar 19:54, 66:13-66:16).
- **Spændingen mellem de to tal er uafklaret (usikkert):** 0,5 % risiko ved en position på 2,5-3 % svarer til et stop 17-20 % væk. Videoens eget Nvidia-tab (ca. 12 % af 2,5 % = ca. 0,3 % af kapitalen, 08:02-08:22) passer med en fast positionsstørrelse. Hvordan de to regler kombineres i praksis, siges ikke.
- Accepteret drawdown 5-10 % (webinar 67:24-67:31).

### 3.4 Eksempler (kun som illustration, ikke anbefalinger)

| Aktie | Hvad der siges | Kilde |
|---|---|---|
| Nvidia | Købt, faldt gennem SMA50 og SMA200, solgt med ca. 10-12 % tab; købt igen, da den steg; gik glip af en optur på 19 %. Stor position i webinaret, sidelæns længe. | Styr din risiko 07:44-08:50; webinar 36:32-36:38 |
| Micron | Entry, rystet ud af markedsfald, steg igen. | Styr din risiko 09:00-09:12 |
| Novo Nordisk | Fulgt i optrend, solgt ved brud under SMA50 (høj P/E, "price for perfection"); bagefter en gæt-på-bund med ca. 6 % tab. "Vi vidste ikke, at den skulle ned." Nu dobbelt rød. | Styr din risiko 09:31-10:10; webinar 40:38-44:04 |
| Rheinmetall | Fulgt i optrend; solgt i sommeren sidste år, da den brød ned. MSS siger, at hvis de var blevet, havde de haft ca. 25 % tab og pengene låst i ca. 10 måneder. Det er en "hvad nu hvis"-betragtning, ikke en faktisk handel. | Styr din risiko 16:53-18:30; webinar 50:00-50:06 |
| Protector | Tre swingtrades på uger til måneder ud fra TPI; kursnavne i udskriften er løse. | Protector 02:03-05:45 |

---

## 4. Egenrapporterede resultater (MSS' egne tal, ikke verificeret)

Alle tal nedenfor kommer fra MSS selv i videoer, er ikke uafhængigt kontrolleret, og er ikke en prognose. Afkast er målt af MSS i en live-portefølje, der delvist er bagudfyldt med regler.

| Tal | Hvad der siges | Kilde |
|---|---|---|
| Samlet afkast | 33 % siden 1. januar sidste år (video om stop-niveau); 34,48 % i 2025 (webinar) | Styr din risiko 04:14-04:18; webinar 64:27-64:30 |
| Maks. drawdown | 7,8 % mod 23 % for markedet (stop-videoen); ca. 7 % (webinar) | Styr din risiko 05:03-05:14; webinar 19:04 |
| Aktuel drawdown | Ca. 3,3 % | Webinar 19:11 |
| Gennemsnit pr. handel | Gennemsnitlig gevinst pr. aktie 6,16 %; vindere 23,05 %; tabere "minus 17" | Styr din risiko 06:21-06:32 |
| Vinderprocent | 44 % lige nu; "55-60 %" ifølge MSS over 4-8 år | Styr din risiko 06:36-06:55 |
| Aktivitet | 143 køb/salg siden start; ca. 30 aktier | Webinar 66:03-66:16 |
| 3Point Playbook i år | 20,67 % målt i EUR mod S&P 500 i USD; ingen tabsmåned endnu. Porteføljen er udfyldt med dagens aktier fra starten af året og bagud til 2024 ("100 % specificerede regler"), altså delvist bagudfyldt. | Nye features 06:37-07:36 |
| Swing-portefølje USA | +3,6 % siden slutningen af maj mod markedet +1,73 % | Danske swing 15:13-15:26 |
| Automatiske porteføljer | Fire strategier (Quality Momentum, TPI Plus, Value Momentum, Value Quality) mod RSP; gennemsnit ca. 4,5 % YTD mod ca. 3 %; tilbageregnet til ca. 2000 (usikkert, Whisper-fejl i tallene) | Automatiske porteføljer 01:25-06:05 |
| Tema-performance | Udvalgte tema-ETF'er og aktier med +9 % til +41 % i uklare perioder; valgt i bagklogskab | Tema-performance 04:53-07:00 |

**Forbehold:**
- Det gennemsnitlige tab "minus 17 %" kan ikke passe med de øvrige tal: 44 % vindere à 23,05 % og et gennemsnit på 6,16 % giver et gennemsnitligt tab på ca. 7 %. Udskriften er sandsynligvis forkert hørt (usikkert).
- Der oplyses ikke omkostninger, skat eller valutaeffekt udover ét sted (EUR).
- Videoen om stop-niveau siger selv, at porteføljen har været bagud i en periode, at strategien bliver "sendt ud" i hurtige nedture, og at et simpelt buy-and-hold i S&P 500 ofte ville have været bedre uden hensyn til drawdown (Styr din risiko 02:44-02:54).
- Titlen på webinaret ("Novo faldt 47,9 %") står ikke i udskriften; perioden er uklar (usikkert).

---

## 5. Hvad der ikke findes i kilderne

**Huller (må ikke opdigtes):**
- Formlen for MSS' quality score, value-score, momentum og samlet stock score, og vægtene. Kun én tærskel er oplyst (kvalitet mindst 60, helst over 70).
- Tærskler for ROCE, rentedækning, FCF, Altman Z, Piotroski og analytikerrevisioner. Piotroski 6 af 9 og rentedækning ca. 40 er eksempelværdier for én aktie.
- Moat og Stability. Ordene bruges ikke i de læste udskrifter.
- Præcis definition af TPI, MTI og MTX (inputs, perioder, grænser), af "oversolgt/overkøbt akkumulering" og af zonerne "Købszone", "Stærk købszone", "Behold", "Salgszone".
- Hvad "dobbelt grøn" er numerisk (en MTI-farve er et statistisk resultat uden oplyst formel).
- Om entry kræver kurs over SMA50 på både dags- og ugegraf (det siges ikke).
- Hvornår dagsgrafen afgør mod ugegrafen.
- Præcis hvordan 0,5 % risiko og 2,5-3,2 % positionsstørrelse hænger sammen.
- Rebalanceringsregler og hvordan nye aktier prioriteres, når flere opfylder reglerne.
- Hvilket benchmark der bruges til RS-linjens udregning (SPY eller RSP), og hvordan StockMap-kvadranterne beregnes (RS-linje, RS-momentum, normalisering).
- Kriterier for temaer, og hvornår et tema forlades.
- Kriterier bag bogstavkarakterer og farvekode.
- Faktiske handelslister og tidspunkter, så MSS' resultater ikke kan genskabes.

### 5b. Rettelser efter opslag i udskrifterne

Disse påstande i de forudgående noter holdt ikke ved opslag og er rettet her:

1. "Faktor 3, 5 og 7 testes" – ×10 vises først som overdrivelse, ×7 prøves, og den endelige sammenligning er ×3 og ×5.
2. "Entry: luk over SMA50 på dags- og ugegraf (begge skal være grønne)" – udskriften angiver ikke SMA50 som entry-regel. SMA50 er "normalt" trendlinje og exit-trigger.
3. "Købet sker, når kursen bryder op over trenden (Nvidia, Micron)" – udskriften siger kun, at de kom ind; begrundelsen er ikke angivet.
4. "Nvidia: 378 aktier ved stop 6 %, 174 ved 13-14 %" – hypotetisk illustration i TradingView, ikke en rapporteret handel.
5. "Rheinmetall: holdt ikke i 10 måneder, tab 25 %" – 25 % og 10 måneder er MSS' "hvad hvis de var blevet i den"; de solgte tidligere.
6. "Gennemsnitligt tab -17 %" – passer ikke regnskabsmæssigt med resten; sandsynligvis Whisper-fejl, markeret usikkert.
7. "Dobbelt grøn (MTI), MTX og 20,67 % er fra videoen 'Intro til nye features'" – det er fra "Nye features i MyStockScanner". Intro-videoen nævner dobbelt grøn kort og anbefaler RSP som benchmark.
8. "SPY mod RSP er en modstrid" – nuanceret: SPY er eksempel i StockMap, RSP er MSS' udtrykkelige præference i tre andre videoer.
9. "20,67 % er live-afkast" – porteføljen er delvist bagudfyldt (Nye features 06:44-07:01).
10. "Protector-handlerne er resultater" – videoen er et tilbageblik på handler, ikke en samtidig dokumentation (Protector 00:41-00:47 og løse kurstal).
11. TPI-farver: noterne beskrev dem som én fast kodning; de varierer mellem videoer (gul/lyserød for oversolgt).

---

## 6. RealTrading-videoen (holdes adskilt)

"Derfor køber jeg IKKE Genmab og NKT nu" er **ikke en MSS-video**. Den er fra kanalen RealTrading (præsentator Peter Søndergaard) og bruger ikke MSS' scores eller indikatorer. Kort om metoden:

- Ren teknisk analyse på uge- og dagsgraf: trend, støtte/modstand, kanaler; først markedskontekst (S&P 500, Nasdaq) (02:23-03:30; 06:00-06:30).
- Swing trades fra dage til måneder; ingen nye positioner op til regnskaber og usikre uger (03:52-04:05; 07:40-07:50).
- NKT: kunne købes nær støtte (ca. 28) med stop under seneste bund og mål ved næste modstand (potentiale 2,58 R); præsentatoren tog ikke handlen (09:51-11:05).
- Genmab: køber ikke efter en stigning på ca. 47,5 % på en uge; vil først købe ved et tilbagefald mod tidligere all-time high, tallet er usikkert i udskriften (11:49-13:47).
- Månedsresultater (oktober, usikkert): credit spreads -0,1 R, swing trades ca. -0,6 til -0,7 R (07:57-08:48). Positionsstørrelse nævnes ikke.

Kan testes separat (støtte/modstand + stop under bund + mål i R), men har en helt anden logik end Playbook og bruges ikke i afsnit 7.

---

## 7. Forslag: vores egne testbare regler for "solid bull + entry" (fase 5)

Princip: egne regler, åbent dokumenteret, testet mod basislinjer. Vi gætter ikke MSS' formler. Pseudokode bruger eksisterende kode, hvor den findes (`quality.score_quality`, `candles.trend_context/setups/simulate_trade/forward_returns`); nye navne er markeret med (ny). Alle tærskler er startværdier, der skal vælges ved test, ikke antagelser om MSS.

### 7.1 Univers: "solid"

```
# quality.py: score_quality(fundamental_data) -> QualityResult (total 0-100 eller None)
def er_solid(symbol, dato):
    q = score_quality(fundamentals_asof(symbol, dato))        # (ny) point-in-time-udgave
    return q.total is not None and q.total >= Q_MIN           # Q_MIN i {60, 70}  (MSS siger 60, gerne 70)
# Supplement (valgfri variant): Piotroski-test, ingen negativ EPS-trend, FCF > 0
```

### 7.2 Bull: trend og relativ styrke

```
def er_bull(prices, bench, dato):
    d = prices till dato;  w = resample_week(prices till dato)               # (ny) ugebarer
    dag_ok  = d.Close > sma(d.Close, 200) and sma(d.Close,50) > sma(d.Close,200)  # = trend_context.uptrend (én fælles definition)
    uge_ok  = w.Close > sma(w.Close, 10)                  # (ny) variant A: 10-ugers SMA (ca. 50 handelsdage); variant B: 50-ugers SMA
    rs      = d.Close / bench.Close                                           # (ny) RS-linje
    rs_ok   = rs > sma(rs, 50) and rs_momentum(rs, 8 uger) > 0                 # (ny) variant: kun RS-momentum
    return dag_ok and uge_ok and rs_ok
# bench i {SPY, RSP}; test begge (ét fast benchmark pr. kørsel)
```

### 7.3 Entry: tilbagerekyl + udløser

```
def entry_signal(prices, dato):
    ctx = trend_context(prices)                          # eksisterende: uptrend + pullback
    trig = pattern in {hammer, bullish_engulfing}        # candles.detect_patterns
    trig_b = (close > sma50) and (close.shift(1) <= sma50.shift(1))    # (ny) luk over SMA50 igen efter at have rørt den
    return er_solid and er_bull and ctx.pullback and (trig or trig_b) and not earnings_inden_for(3 dage)
# udførelse: køb næste åbning (som forward_returns), eller købsstop over signaldagens top (setups/simulate_trade)
```

Egne resultater tilsiger lav forventning til candle-udløseren alene (hammer +0,3/+0,5/+0,9 %-point ved 5/10/20 dage over en tilfældig dag; bullish engulfing +0,1/+0,2/+0,5; Inside Bar-udbrud og lukning over top med volumen under basis). Den væsentlige test er derfor, om *kvalitet + bull + RS* tilføjer noget (afsnit 7.6, B og C), ikke candle-mønsteret.

### 7.4 Stop og exit

```
def initial_stop(prices, entry_dag, faktor):
    atr = ATR(10)(prices)                                  # (ny) Wilder eller simpel; test begge
    return entry_pris - faktor * atr                        # faktor i {3, 5};  Supertrend-trailing: stop kun op

def exit_signal(prices, w, position):
    return (low <= trailing_supertrend_stop)               # variant 1: Supertrend ATR(10)x3 eller x5 (trailing)
        or (w.Close < sma_uge_50)                           # variant 2: ugentlig luk under SMA50
        or (d.Close < sma(d.Close,50) and ikke_genvundet_efter 3 dage)    # variant 3 (MSS' "lidt snor")
        or (d.Close < sma(d.Close,200))                     # altid
# fast holdetid (5/10/20/60 dage) bruges kun som basislinje
```

Teknisk note: `simulate_trade` kender i dag et fast stop og en fast holdetid; trailing Supertrend og ugentlig exit kræver en ny funktion (`simulate_trend_trade`, ny). Konservativ dagsdata-regel bevares: rammer entrydagen også stoppet, regnes den som stoppet.

### 7.5 Positionsstørrelse

```
risiko_pr_handel = 0.005 * kapital                          # 0,5 %
antal = risiko_pr_handel / (entry - stop)
position_pct = min(antal * entry / kapital, MAX_POS)        # MAX_POS i {3,2 %, 5 %}  (MSS bruger 2,5-3,2 %)
max_antal_positioner = 30..40
```

Test både (a) fast 2,5-3 % og (b) 0,5 %-risiko med loft, og rapportér, hvor ofte loftet bider.

### 7.6 Backtests der skal køres

Fælles rammer:
- **Univers:** mere end de 20 store aktier – mindst 100-200 aktier på tværs af sektorer og lande. Medtag nedlagte/faldne aktier (survivorship); ellers marker resultaterne som skæve.
- **Periode og split:** træn/vælg på de ældste ca. 60 % af perioden, fastfrys regler, og test én gang på de seneste ca. 40 % (out-of-sample). Gentag som walk-forward (rullende vindue). Ingen parameter må vælges på test-perioden.
- **Omkostninger:** 0,1 % pr. side som nu; følsomhedstest ved 0,25 %. Ingen skat/valuta i første omgang.
- **Basislinjer:** (1) køb på tilfældig dag med samme holdetid; (2) tilfældig dag i samme optrend-/bull-tilstand (isolerer signalets værdi fra trendfilteret); (3) buy-and-hold; (4) equal-weight af universet (≈ RSP) og SPY; (5) en tilfældig positionsstørrelse og -tidspunkt (Monte Carlo) til at vurdere, om resultater kan være tilfældige.
- **Mål:** gennemsnitligt og medianafkast pr. handel, vinderprocent, gennemsnitlig gevinst/tab (R), forventning i R, maks. drawdown, Calmar/Sharpe, omsætning, tid i markedet og andel stoppet ud; bootstrap-konfidensintervaller, fordi signaler overlapper (kendt svaghed i vores første test).
- **Datakrav:** point-in-time-fundamentals. yfinance giver ca. 4 årsregnskaber og kun nuværende `info`, så en historisk kvalitetsscore over 10 år kan ikke genskabes pålideligt uden en anden datakilde (usikkert, hvilken). Indtil da testes bull+entry uden kvalitetsfilter, og kvalitetsfilteret testes kun fremad (paper-trading/log).

Test-matrix (kør i rækkefølge; stop, hvis et trin ikke slår sin basislinje out-of-sample):

| # | Test | Spørgsmål | Sammenlign med |
|---|---|---|---|
| A | Trendfilter alene: dag SMA50>SMA200 og kurs>SMA50 (dag, uge, begge) | Giver "bull" i sig selv noget? | Tilfældig dag, buy-and-hold |
| B | A + RS mod benchmark (SPY vs. RSP; RS-linje over SMA mod RS-momentum) | Tilfører relativ styrke noget? | A |
| C | B + tilbagerekyl-entry (eksisterende `trend_context.pullback`) mod entry uden tilbagerekyl | Er det bedre at vente på tilbagerekyl? | B uden tilbagerekyl |
| D | C + udløser: hammer, bullish engulfing, luk over SMA50 igen, ingen udløser | Skal en udløser overhovedet bruges? | C uden udløser |
| E | Exit-varianter: Supertrend ATR(10)×3, ×5, ugentlig luk<SMA50, 3-dages SMA50-snor, SMA200 + fast holdetid 20/60 dage | Hvilken exit holder bedst på drawdown og forventning? | Fast holdetid |
| F | ATR-periode (10/14/20) og Wilder vs. simpel | Følsomhed | E's bedste |
| G | Størrelse: fast 2,5-3 % mod 0,5 % risiko med loft; maks. 30 mod 40 positioner | Porteføljeeffekt, drawdown | Equal-weight |
| H | Regnskabsfilter: ingen entry de sidste 1-3 dage før regnskab | Reducerer det tab? | Uden filter |
| I | Kvalitet (kun fremadrettet/paper): Q_MIN 60 mod 70 mod ingen | Giver kvalitet bedre bull-resultater? | Uden kvalitet |
| J | Whipsaw-følsomhed: hvor ofte stoppes ud og købes igen (billetprisen MSS nævner) | Hvad koster ind-og-ud? | E |

Rapportér alle varianter, også dem der ikke slår basislinjen (undgå at vælge efter bagklogskab). Mål "bedst" på out-of-sample, justeret for antal prøvede varianter.

---

## 8. Kilder

Alle udskrifter ligger i `C:\AI-Stock-Scanner\data\video-transcripts\`. MSS-videoer:

1. Styr din risiko - Valg af Stop loss niveau
2. Gratis webinar: Mens Novo Nordisk faldt 47,9 %, steg vi 34,48 %
3. Green Hydrogen kollapser! Kunne vi have set det komme?
4. Sådan vælger jeg aktier med MyStockScanner
5. Danske swing-kandidater med MyStockScanner
6. Protector forsikring - Mange små gevinster
7. StockMap - Forklaring 1
8. Nye features i MyStockScanner
9. Nyt i MyStockScanner - Intro til nye features
10. Automatiske porteføljer og hedge mod nedtur
11. Updatering på Tema-performance
12. Velkommen til Temaer
13. Ny feature i MyStockScanner - Short Interest (kun nøgletal, ingen regler)
14. Ny fantastisk feature i MyStockScanner (watchlists/TradingView-eksport)
15. Tradingview gratis i MyStockScanner
16. 3 Stocks to Watch in September (kort, ingen regler)
17. Build a winning Danish stock portfolio (kort, ingen regler)
18. NEVER follow the hype!, Welcome to the Wild West of investing, BUY, SELL, HOLD… OR RUN AWAY, Is it Overrated or underrated, From a superior A+ to a failing F (korte domsvideoer uden brugbare kriterier; sidstnævnte er en ødelagt udskrift)

Andre kilder:
- RealTrading: "Derfor køber jeg IKKE GENMAB og NKT nu! - RLT analyse" (ikke MSS).
- Interne: `docs/QUALITY-MODEL.md`, `TASKS.md`, `stockscanner/candles.py`, `stockscanner/quality.py`.

## 9. Første resultater for A–C (02-11-2026)

Kørt med `scan_cli.py --regimer --periode 15y` på 47 aktier (DK, DE, SE, NO, NL, FR, CH og USA, også tidligere tabere som Ørsted, Bayer, Intel og Boeing). Benchmark RSP med dagen før. Signal ved lukning, køb næste åbning, salg ved lukning efter N dage, 0,1 % kurtage pr. handel. Udvikling til 31-10-2024; urørt periode fra 01-11-2024. Ingen parametre er tunet.

| 60 dage | Udvikling: edge | Udvikling: værste 5 % | Urørt: edge | Urørt: værste 5 % |
|---|---:|---:|---:|---:|
| Alle dage (basis) | 0,00 | −17,8 % | 0,00 | −19,7 % |
| A: optrend | +0,16 | −16,3 % | −0,28 | −18,2 % |
| B: optrend + relativ styrke | +0,48 | −16,1 % | −0,05 | −19,2 % |
| C: optrend + tilbagerekyl | +0,57 | −16,7 % | −0,10 | −18,4 % |
| C: optrend uden tilbagerekyl | −0,45 | −15,7 % | −0,68 | −17,6 % |

Konklusion:
- Trend, relativ styrke og tilbagerekyl giver ingen sikker merafkast ved køb; den lille fordel i udviklingsperioden holder ikke i den urørte periode.
- Trendfilteret mindsker de værste udfald lidt (ca. 1–1,5 %-point ved 60 dage).
- MSS' påståede lave drawdown kommer derfor sandsynligvis fra **exit** (salg ved trendbrud under SMA50/SMA200), ikke fra entry. Næste test: samme køb, men exit ved trendbrud mod fast holdetid – målt på maks. drawdown og afkast.

## 10. Salgsregler på samme køb (punkt 9, 02-11-2026)

Kørt med `scan_cli.py --salg --periode 15y` på 47 aktier. To købsmetoder: MSS' simple StockMap-køb (ugentlig) og trendkøb (luk krydser over SMA50, mens luk > SMA200). Salg er et **brud** (luk krydser ned under gennemsnittet eller Supertrend vender), ikke en tilstand. Salg næste åbning, 0,1 % kurtage pr. handel, urørt periode fra 01-11-2024. %/100d = gennemsnitligt afkast pr. 100 handelsdage i handlen.

| Køb / regel | Udvikling %/100d | Urørt %/100d | Urørt værste 5 % |
|---|---:|---:|---:|
| Trendkøb, Supertrend ×3 | 7,4 | 6,5 | −13,2 % |
| Trendkøb, fast 60 dage | 6,7 | 8,1 | −23,3 % |
| Trendkøb, SMA200 | 7,2 | −2,2 | −13,1 % |
| StockMap-køb, SMA50 | 5,2 | 6,2 | −18,6 % |
| StockMap-køb, hybrid 20/50 | 5,2 | 6,6 | −18,6 % |
| StockMap-køb, StockMap-salg | 5,9 | 3,4 | −32,5 % |
| StockMap-køb, fast 60 dage | 6,0 | 7,9 | −25,3 % |

Konklusion:
- **Supertrend (ATR 10 × 3)** er den mest robuste salgsregel: næsten samme afkast pr. tid som at holde fast, men de værste udfald er ca. 40 % mindre, og det holder i den urørte periode.
- Efter StockMap-køb er **brud på SMA50** (evt. SMA20 ved eksplosive løb) bedre end MSS' eget StockMap-salg.
- SMA200-brud holder ikke i den urørte periode; SMA50-brud efter trendkøb giver for mange falske salg.
- Forbehold: overlappende handler, kun nuværende aktier, ingen portefølje-simulering endnu.

## 11. Porteføljesimulering (punkt 6, 02-11-2026)

`scripts/simulate_portfolio.py`: 296 aktier (DK, US, Europa), 2019-01 → 2026-10, uge for uge, op til 40 lige store positioner, køb på StockMap simpelt køb, salg når Supertrend ×3 vender ned eller StockMap-salg, 0,1 % kurtage pr. handel.

| Variant | CAGR | Største fald | Handler | Vindere |
|---|---:|---:|---:|---:|
| RSP køb-og-hold | 13,6 % | −36,7 % | – | – |
| StockMap alene | 12,5 % | −25,2 % | 6348 | 46 % |
| + MTI-lite | 1,4 % | −8,4 % | 1789 | 44 % |
| + markedsindeks (>50 % over SMA50) | 5,9 % | −19,2 % | 4581 | 43 % |
| + MTI + markedsindeks | 0,7 % | −6,4 % | 1291 | 42 % |

Urørt periode (2024-11 →): StockMap alene 12,2 % mod RSP 13,6 %, største fald −16,4 % mod −15,5 %.

Konklusion: rene kursregler giver omtrent markedets afkast med mindre fald over hele perioden; ekstra filtre gør porteføljen for kontantrig. MSS' egenrapporterede 34 % (2025) kan ikke genskabes med kursregler alene – deres kvalitets- og værdifilter og skønsmæssige udvælgelse kan ikke backtestes ærligt uden point-in-time-regnskaber. Forbehold: overlevelsesbias (kun aktier, der findes i dag).
