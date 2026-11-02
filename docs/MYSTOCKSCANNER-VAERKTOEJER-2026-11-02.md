# MyStockScanner-værktøjerne: hvad vi ved, hvad der er hemmeligt, og hvordan vi bygger egne åbne udgaver

Dato: 02-11-2026. Status: arbejdsdokument til de næste faser (timing, værdi, kalibrering mod MSS).

**Ikke investeringsrådgivning.** Dokumentet beskriver, hvad MyStockScanners (MSS) videoer og skærmbilleder *siger* om deres værktøjer, og hvordan vi kan bygge og teste vores egne, åbne modeller. Intet her er en købs- eller salgsanbefaling; aktienavne er kun kalibreringseksempler. MSS' formler er ikke offentlige, og vi kopierer dem ikke (vi har ikke set kode). Vi gætter en funktion ud fra den adfærd, der kan observeres, og måler, hvor tæt vi kommer. **Alle MSS-afkast, vinderrater og backtests i dokumentet er egenrapporterede/backtest, ikke verificerede.**

Tidligere analyse (metode, entry/exit, "3-point playbook", egenrapporterede resultater) står i `docs/MYSTOCKSCANNER-BULL-ENTRY-2026-11-02.md` og gentages ikke. Vores nuværende kvalitetsmodel står i `docs/QUALITY-MODEL.md` og `stockscanner/quality.py`.

---

## 0. Læsevejledning

**Kilder.** Whisper-udskrifter i `data/video-transcripts/` (tidsstempler `h:mm:ss` eller `mm:ss`), Haiku-udtræk (G1-G10), `data/mss_video_observations.csv` (435 rækker) og `data/mss_observations.csv` (9 rækker fra Allans prøveperiode, 29.-30.10.2026). Haiku-noterne havde fejl; hvor to noter modsagde hinanden, eller noget virkede overraskende, er det slået op i udskriften (se afsnit 2).

**Forkortelser for videoer** (dato i titlen er sikker; ellers er den et skøn, markeret "usikkert"):

| Kort | Video | Dato |
|---|---|---|
| BK | Begynderkursus | ukendt, 2025-26 (usikkert) |
| WEB | Webinar om MSS-platformen | ca. 2023 (usikkert) |
| TPI24 | Gratis webinar 5-3-24 (nye features) | 05.03.2024 |
| NF | Nye features i MSS (egne indikatorer i TradingView) | ca. sensommer 2025 (usikkert) |
| L8 | MSS Live 8-10-25 | 08.10.2025 |
| LW | MSS LIVE Webinar (dansk) | 21.01.2026 |
| QA26 | MSS Q&A dansk | 18.02.2026 |
| BW | Begynder-webinar | 04.03.2026 |
| SM1 | StockMap - Forklaring 1 | ca. maj 2026 (usikkert) |
| NYT | Nyt i MSS - Intro til nye features (explorer, StockMap, MTX) | ca. maj 2026 (usikkert) |
| RISK | Styr din risiko - valg af stop loss | slut maj 2026 (usikkert) |
| QTS | Q&A for medlemmer: sæt turbo på din timing score | ca. aug-sep 2026 (usikkert) |
| PREM | Eksklusivt snig-premiere af nyt site | midt okt 2026 (site lanceres 19.10.2026) |
| TEMA1/2 | Velkommen til Temaer / Updatering på tema-performance | maj / aug 2026 (usikkert) |
| ALGO1-3 | Algostrategier sept-okt 2024 / Algo update 7.11.24 / Algo marts 2025 | 2024-25 |
| MIX | Introvideo 4, strategy mixer | usikkert |
| DSK | Danske swing-kandidater | usikkert |
| PAN, VT, REG, SAAB, SIGA, SI | Pandora-valuegraf, Value Traps, regressionslinje, Saab, SIGA, Short Interest | usikkert |

**Vigtig begrænsning for kalibrering.** Vores datakilde (yfinance) giver *aktuelle* analytikerestimater og kun de seneste ca. 4 årsregnskaber, ikke historiske snapshots. Derfor gælder:
- **Prisbaserede værktøjer** (StockMap, TPI, MTI, glidende gennemsnit, Supertrend, regressionskanal) kan kalibreres på alle datoer i videoerne, for kursdata findes historisk.
- **Fundamentalbaserede værktøjer** (Quality, Value, PEG) kan kun sammenlignes ordentligt på observationer, der er lavet *nu*, dvs. Allans prøveperiode og fremtidige skærmbilleder. Videotallene fra jan.-mar. 2026 bruges til at tjekke formlens *struktur* (regnestykker) og grove niveauer, ikke point for point.

---

## 1. Overblik

| Værktøj | Kendt | Hemmeligt | Rækker i CSV | Plads i byggeplan |
|---|---|---|---|---|
| Quality score | skala (percentil), delmål, brugsgrænse 60-65 | vægte, percentilregel, univers | 20 numeriske (10 med dato) + 9 | 3 |
| Value / værdikanal / værdiscore | formel EPS x P/E, tre scenarier, score-definition | hvordan bear/base/bull-P/E vælges | ca. 68 (27 med scenarier) | 1 |
| PEG, implicit P/E | definition og grænse (<2-2,5) | hvilken vækst og hvilket år | 14 PEG + 4 implicit-P/E | indgår i 1 |
| StockMap + simpelt køb/salg | RRG-lignende, RSP, EMA, kvadranter, vinkelregler | præcise parametre ("lidt mere kompliceret") | 18 + 9 vinkler | 2 |
| TPI | navn, tre tidsrammer, farver, statistisk idé | formel | 26 (6 med dato) | senere |
| MTI | navn, relativ mod indeks/sektorer, dag + uge | formel | 12 (9 med dato) | 5 |
| MTX | navn, absolut, én af/på-tilstand | alt | 0 | senere |
| Timingzoner | seks tilstande, backtest-statistik | stærk/overbevisning (fabrikshemmelighed) | 32 + 9 | 2 |
| Glidende gennemsnit | 20/50/200, regler | tærskler for "snor" | 25 | 4 |
| Supertrend | ATR 10 x 3 eller 5 | - | 3 | 4 |
| Regressionskanal | +/-2 std., Pearson R | automatisk startpunkt | 4 | 4 |
| Strategy mixer + algo | fire strategier, månedlig, 25 % hver | rangeringsregler | 26 | ikke nu |
| Porteføljeregler | 2,2-3 % pr. aktie, risiko pr. handel | - | ca. 25 | 4 |
| Temaer, short interest | definitioner | udvælgelse af temaer | ca. 3 | ikke nu |

---

## 2. Rettelser efter opslag i udskrifterne

Haiku-noterne er rettet på disse punkter. De vigtigste først.

1. **Navne på indikatorerne.** TPI = *Turning Point Indicator* (DSK 02:49; NF 03:58; NYT 06:20), MTI = *Momentum Trend Indicator*, **MTX = *Momentum Trend Explosion*** (NYT 07:52-07:56). Noterne skrev "ukendt" for TPI og havde slet ikke navnet på MTX. "DAWS/DAOUS/DAVS", "UMTI/UG-TPI/UTPI" er Whisper-fejl for *Dags-* og *Uge-* (NF 04:15-04:35).
2. **MTI er en relativ indikator**, ikke en generel "momentum og trend"-måler: den måler kursen mod en række indeks og sektorer og bliver grøn, når aktien klarer sig bedre (NYT 07:14-07:48). "Dobbelt grøn" er én og samme indikator på dagsgraf og ugegraf (NF 05:07-05:22), ikke to forskellige indikatorer (G4 læste "DAWS-MTI og UMTI" som to).
3. **StockMaps akser** var byttet om i G6. Vandret akse = relativ styrke (100 = benchmark, højre = bedre end benchmark), lodret akse = momentum *i* den relative styrke. Fire felter med uret: Leading (grøn, øverst til højre), Weakening (gul, nederst til højre), Lagging (rød, nederst til venstre), Improving (blå, øverst til venstre) (SM1 01:30-03:30, 06:00-07:58). Det passer med PREM 0:34:43-0:35:46.
4. **Benchmark = RSP bekræftet** (PREM 0:34:53; QTS 0:11:33; NYT 10:21), ikke "usikkert" som i G5. SPY bruges kun i den første forklaringsvideo (SM1 01:53). Backtest-universet hedder "S&P 1500" (Whisper: "SRP 1500", PREM 0:47:41). EMA er deres eget valg, SMA kan vælges (PREM 0:36:38-0:36:43; QTS 0:56:37-0:57:20).
5. **Simpelt køb og salg, præcist** (QTS 0:30:37-0:32:49, 1:05:02-1:05:41): køb = aktien står i gul eller rød og pilen går fra at pege nedad til at pege opad over 270 grader (kl. 9); om den fortsætter mod venstre eller højre er ligegyldigt. Salg = pilen peger ned mellem 180 og 270 grader *og* står i en anden kvadrant end den, hvor der blev købt. Signal ved fredagens lukning, handel mandag. SM1 08:11 siger dog, at værktøjet oprindeligt blev brugt til at finde bunde, ikke som signalmaskine; reglerne kom efter backtest.
6. **To forskellige "value"-scorer.** (a) Den gamle Value score: percentil af P/E, P/B, P/S, EV/EBITDA m.fl. mod land og region (DSK 08:35-08:51, fx 86 i DK og 91 i Europa). (b) Den nye værdiansættelsesscore: aktiekursens placering i værdikanalen, 100 på den røde linje, 0 på den øverste (grønne) linje, kan blive over 100 og under 0 (PREM 0:20:04-0:21:10 og 0:24:28-0:25:03; QTS 0:58:19-0:58:43). G5 kaldte skalaen "usikker"; den er en lineær interpolation. Der findes også en "min egen" udgave med brugerens justerede P/E.
7. **20 eller 21 dages gennemsnit.** 20 dage (rød) siges eksplicit to gange (QA26 0:11:56; LW 0:32:59). 21 står kun én gang, i en tilråbt formulering (BW 0:51:32). Vi bruger 20.
8. **Timingzonernes navne.** Udskrifterne nævner salg, hold, køb, stærk køb og conviction buy (PREM 0:22:36-0:22:50; 0:33:25). "Neutral", "Købszone", "Stærk købszone", "Købszone med overbevisning" og "Behold" er de navne, der faktisk står i appen i Allans prøveperiode (`mss_observations.csv`). "Salgszone" er ikke set i prøven (usikkert, men forventeligt).
9. **MSS-score** (samlet score) lader til at være gennemsnittet af Quality, Value og Moat: alle 9 observationer i prøven passer inden for afrunding (fejl 0,0-0,7). G5/G6 skrev blot "en kombination". Gammel "stock score" var gennemsnit af value, quality og momentum (WEB 0:12:53).
10. **Apple-scenarier i VT 0:04:04-0:04:14**: "bear -7,4, base ca. 20, bull 4,45 %". Bull er sandsynligvis 44,5 % (Whisper har tabt et ciffer; usikkert). G8 markerede kun tallet som uklart.
11. **Backtest starter 2003, ikke kun 2019.** Teamet siger, at de oprindelige tests går tilbage til 2003 med næsten samme tal, men rapporterer kun 2019-2026 pga. survivorship bias (QTS 0:18:58-0:19:17). G5 skrev "nævnt men ikke brugt"; det er rigtigt, at tallene vises fra 2019.
12. **Tre engelske korte klip er ikke MSS-værktøjer** (VWAP-filtre, "12.000 grafer" fra et andet site, "Discovery, not scoring"). De er udeladt fra al kalibrering.
13. **Dato-spor, der kan bruges:** 13. marts 2026 og 31. juli 2026 er begge fredage, hvilket passer med "signal fredag, handel mandag" (QTS 0:09:18 og 1:00:52-1:02:15). 31. maj er fredag i 2024 (SIGA/TPI, usikkert hvilket år).

---

## 3. Værktøjerne

### 3.1 Quality score

**1. Hvad vi ved**
- Skala 0-100 som *percentil* mod sammenligningsuniverset; 100 = top 1 % (BK 0:33:32-0:33:53; LW 0:20:00-0:20:26). Vises som landescore og regionsscore (fx Danmark og Europa) (Introvideo 1 0:07:45-0:08:05). GN Store Nord: 59 mod Danmark ("top 40 %") og 70 mod Europa ("top tredjedel") (GN-video 0:00:58-0:01:04).
- Delmål, der nævnes: EPS-trend, omsætningsvækst, driftsmargin, ROCE og ROE, free cash flow (helst stigende), rentedækning, current ratio, PEG, analytikernes EPS-revisioner over 1 uge, 1 og 3 måneder (BW 0:16:48-0:17:05), og i naboboksene Piotroski (health) og Altman (PB 0:01:21-0:02:55). Årlige regnskaber plus estimater. Delbokse farves grøn/grå/rød/lyserød; pil i grønt = opfyldt.
- Grænser: samlet score 60-65 eller derover som "gider læse videre" (BK 0:34:24; QA26 0:06:26; QTS 0:58:07); delkrav: PEG under 2 (op til 2,5-3), ROCE/ROE mindst ca. 12 (LW: ROCE 8-12), rentedækning over 5-7, current ratio over 1, negativ EPS eller FCF er udelukkelse (BK 0:41:33, 0:48:41; LW 0:26:46-0:28:12, 0:51:16-0:51:22).
- Branchen er ligegyldig i første trin, kun tallene tæller (LW 0:23:52-0:24:18); en branchescore er planlagt (WEB; TPI24 0:43:05).
- Observerede niveauer i CSV: Novo 99-100, Visa 99, Apple 99, TSM 98, Amazon 99, ISS 87, Royal Unibrew 89, Pandora 93, Netcompany 81, Skov 78, Rheinmetall 87, Carlsberg 59, NKT 58, DFDS 48, Vestas 39, Shape Robotics 37, Nokian Tyres 23.

**2. Hemmeligt/ukendt.** Vægte, om percentilen tages pr. delmål eller på en samlet rå score, universets sammensætning (50-80.000 aktier ifølge BW 0:06:51 og 0:43:13, inkl. små selskaber), behandling af banker, om scoren er sektorrelativ (udsagnet "branchen er ligegyldig" taler imod). Forklaringsvideo er lovet (BK 0:33:05), men ikke set i materialet.

**3. Vores kandidat-formel.** Vores model er *absolut* (tærskeltabeller), MSS' er *relativ*. Mindste skridt:

```python
q_raw = score_quality(fd).total                         # nuværende 0-100, tærskelbaseret
q_pct = 100 * percentile_rank(q_raw, universe_q_raw)    # univers: land | region | indeks-sæt
# variant B, tættere på beskrivelsen: percentil pr. delmål, vægtet, og percentil igen
q_pct_B = pct_rank(sum(w[m] * pct_rank(metric[m]) for m in DELMAAL))
DELMAAL += ["eps_trend", "peg", "analyst_revision_3m"]  # mangler i vores model i dag
```
Univers kan ikke blive 50-80.000 aktier; brug indeksmedlemmer (C25/OMX, STOXX 600-udsnit, S&P 500) og accepter, at *niveauet* ikke kan matche, kun *rangordenen*. Kortlæg bagefter med monoton (isotonisk) regression.

**4. Kalibrering.** 20 numeriske videotal (10 med eksakt dato: ISS, Nokian, "Plejt" 18.02.2026; Royal Unibrew, Pandora 04.03.2026; TSM, Novo, Rheinmetall, Shape, Amazon 21.01.2026) + 9 fra prøven = ca. 29 par. Metrikker: Spearman (mål over 0,7, bootstrap-interval fordi n er lille), gennemsnitlig absolut afvigelse efter isotonisk kort, andel på korrekt side af grænsen 60 (mål over 80 %). Fortegnstest: europæisk percentil bør være højere end dansk for danske aktier (GN 59/70 og Matas value 86/91 peger begge den vej). Videotallene kan kun bruges groft (se begrænsningen i afsnit 0); prøvetallene fra 29.-30.10. er de bedste.

### 3.2 Moat, MSS-score og øvrige scorer (kort, fordi de hænger sammen med Quality)

- **Moat** (0-100): marginernes niveau og udvikling plus balancestyrke (PREM 0:26:01-0:28:24; LW). Moat 5 er svag. Formlen er ukendt. Kandidat: gennemsnit af percentiler for bruttomargin-niveau, driftsmargin-trend (5 år) og margin-stabilitet fra `quality.py` plus gældsandel; kalibreres mod de 9 prøverækker (Moat 70-93).
- **MSS-score**: se rettelse 9. Kandidat: `round((quality + value + moat) / 3)`; mål: gennemsnitlig absolut fejl under 0,5 på de 9 rækker (i dag 0,26). Det giver os den samlede score gratis, så snart de tre delscorer er der. Hvilken value-score der indgår (percentil eller kanal, evt. afkortet ved 100), afgøres af prøven.
- **Momentum-score**: nævnes kun som "god bevægelse" (BW 0:11:41). Kandidat: percentil af 12-1-måneders afkast. Ingen kalibrering mulig i dag.
- **Piotroski og Altman**: vises, uden formel (BK; WEB). Vi har begge i `quality.py` (standardformlerne).
- **Bogstavkarakterer A-F** vises i en kort video (Whisper-teksten er næsten ubrugelig, usikkert). Kortlægning mod MSS-score bør fanges på skærmbillede.

### 3.3 Value score og værdikanal (valuegraf)

**1. Hvad vi ved**
- Grundformel: kurs = EPS x P/E (BK 0:57:15; WEB 0:56:06-0:56:24). Kanalen = analytikernes gennemsnitlige EPS for de næste 1-3 år (standard 2) x tre P/E-værdier: bear, base, bull (QA26 0:10:00-0:10:31; BW 0:20:43-0:21:03; LW 0:29:20-0:31:00). Estimaterne røres ikke, kun P/E (QA26 0:10:00).
- P/E-forslagene tager udgangspunkt i historiske gennemsnit over 3, 5 og 10 år, analytikernes målkurs (implicit P/E = målkurs / forventet EPS) og aktuel P/E; brugeren kan justere, og systemet vælger "forholdsvis stabilt" (BK 1:03:44-1:04:26; LW 0:39:29-0:39:43; USA-budget 0:10:56-0:12:02). Eksempler på forslag: Micron 14/18/23; Apple 22/31,5/38 (historik 18-37); Vestas 18/23/28; GN 16-24; CoreCivic 16/20/24; Nvidia 31-47; ISS 12 til ca. 20; Pandora 14-21 (3/5/10-årsgennemsnit 20,8/15,5/17,4, aktuel 8,6).
- Output: kursniveau og potentiale i procent pr. scenarie, årligt afkast (CAGR) og en sammenligningslinje for risikofri rente (3 eller 5 %) (WEB 1:00:29-1:01:13). Kanalen flytter sig, når estimaterne ændres (BW 0:45:19).
- **Regnestykket er lineært i P/E.** Vestas: P/E 18/23/28 giver +32/+69/+105 %; 23/18 = 1,28 og 1,69/1,32 = 1,28; 28/23 = 1,22 og 2,05/1,69 = 1,21. CoreCivic: 16/20/24 giver +8/+35/+62 %; 1,35/1,08 = 1,25 = 20/16. Apple 22/38 giver -35/+11 % (38/22 = 1,73 mod 1,11/0,65 = 1,71). Det bekræfter, at *kun P/E varierer* mellem scenarierne.
- Zoner: nederste halvdel af kanalen = billig, øverste = dyr (BW 0:24:16; LW 0:30:06). Krav i deres praksis: base-upside mindst 2-4 gange bear-nedside (LW 0:30:53-0:31:00; Netcompany/5 danske 0:05:55); worst case omkring minus 35 % er et nej (BW 0:45:45-0:45:57). Fallgruber: value trap, hvis estimaterne falder (VT); bull-scenariet bør ikke elskes (QTS 0:30:01).
- **Værdiansættelsesscore:** se rettelse 6. Over 60 betyder "nederste del" (QTS 0:58:19-0:58:43); filtre på 80-90 nævnes (PREM 0:21:38). Nvidia 100 (system) mod 167 (egen indstilling), AMD -96.
- Planlagt: branche- og sektorgennemsnit for P/E og vækst (WEB 1:13:34-1:14:20; Ny fantastisk feature 05:00-05:40). EPS-baseret er standard; cash flow eller sales kan vælges for selskaber uden overskud (WEB 0:59:20).

**2. Hemmeligt/ukendt.** Præcis regel for bear/base/bull-P/E; hvilket EPS-år der bruges til *score* (i dag vs. horisont); hvordan kanalen tegnes for fortiden (historisk EPS x P/E-linjer); hvordan manglende estimater håndteres; om "systemets" score er afkortet ved 100 i listevisningen (prøvens højeste værdi er netop 100, usikkert).

**3. Vores kandidat-formel**

```python
def value_channel(price, eps, pe_hist, pe_now, target_px, horizon=2, rf=0.03):
    # eps = {1: konsensus-EPS næste regnskabsår, 2: året efter}; pe_hist = {"3y":..,"5y":..,"10y":..}
    pe_impl = target_px / eps[1]                                  # implicit P/E (BK 1:07:41)
    cands   = [pe_hist["3y"], pe_hist["5y"], pe_hist["10y"], pe_impl]
    base, bear, bull = median(cands), 0.9 * min(cands), max(cands)   # STARTGÆT, kalibreres (se 4.)
    px   = {k: eps[horizon] * pe for k, pe in zip(("bear","base","bull"), (bear, base, bull))}
    up   = {k: v / price - 1 for k, v in px.items()}
    cagr = {k: (1 + u) ** (1 / horizon) - 1 for k, u in up.items()}
    # værdiansættelsesscore: 100 på bear-linjen, 0 på bull-linjen, lineær, ikke afkortet
    score_A = 100 * (px["bull"] - price) / (px["bull"] - px["bear"])          # linjer ved horisonten
    score_B = 100 * (L_bull_i_dag - price) / (L_bull_i_dag - L_bear_i_dag)    # linjer i dag (EPS interpoleret)
    asym    = up["base"] / max(1e-9, -min(up["bear"], 0.0))                   # MSS-praksis: mindst 2-4
    return up, cagr, score_A, score_B, asym, (1 + rf) ** horizon - 1
```
Data: yfinance `earnings_estimate`/`eps_trend` (0y og +1y), `analyst_price_targets`, kurshistorik og årlig EPS til 3/5/10-års P/E. P/E-reglen er den løse del; start med reglen ovenfor og tune på de omkring 10 videotriplets, hvor både P/E-historik og scenarier står i teksten (Pandora, Apple, Micron, Nvidia, Novo, Netcompany, GN).

**4. Kalibrering**
- *Struktur* (billig og skarp): genskab upside-procenterne i teksten ud fra EPS, kurs og P/E. Ca. 27 rækker har bear/base/bull-tal; mål: afvigelse under 2 procentpoint, når kurs og EPS er kendt (typisk skal den implicitte EPS/kurs-kvotient først regnes baglæns, som vist for Vestas).
- *P/E-reglen*: fejl i P/E-forslag (bear/base/bull) på de ca. 10 triplets; metrik: gennemsnitlig absolut procentfejl pr. niveau (mål under 15 %) og at rækkefølgen bear < base < bull holder.
- *Score*: de 9 prøverækker (Value 38-100) og de seks score-rækker i videoerne. Rangkorrelation og, for variant A mod B, hvilken der rammer >100-tilfælde (prøvens maksimum 100 antyder afkortning).
- *Asymmetri-kravet*: andel af aktier i prøven, der opfylder "base >= 3 x |bear|", set mod MSS' valg af eksempler.

### 3.4 PEG og implicit P/E

**1. Hvad vi ved.** PEG = P/E divideret med forventet EPS-vækst, "næste år" i USA-budget-videoen (0:07:20-0:07:30); under 2 er godt, 2-2,5 accepteres, nogle gange 3 (BK 0:41:31-0:41:39; LW 0:23:08). Manglende PEG ved negativ P/E eller uden vækstestimat (PB). Observerede: Visa 1,6; Barrick 0,28; Vestas 0,8; Skov 0,5; CoreCivic 0,5; GN 0,1; Amazon "langt under 2". LW 0:44:38 nævner PEG "helt nede på 1" for Rheinmetall, i modstrid med "under 2,5" lidt før (usikkert, kan være en anden vækstdefinition). Implicit P/E: Novo 32 (målkurs 929,81), Visa 27,7 (målkurs 310) (BK 1:05:12-1:07:41; 1:29:20-1:29:25).
**2. Ukendt.** Vækstdefinition (næste års vækst eller to års CAGR), trailing eller forward P/E, tilfælde med negativ vækst.
**3. Kandidat.**
```python
pe_fwd  = price / eps[1]
growth  = (eps[1] / eps_ttm - 1) * 100                 # variant A; B: CAGR af eps[0..2]
peg     = pe_fwd / growth if growth > 0 else None
pe_impl = target_px / eps[1]
```
**4. Kalibrering.** 14 PEG-rækker (8 har tal) og 4 implicit-P/E-rækker. Metrik: samme side af grænsen 2 (ja/nej) og rangorden; implicit P/E skal kunne genskabes til inden for 1 P/E-punkt, når målkurs og EPS er kendt. Få data, men billigt; kan kun testes på friske tal (Allans trial).

### 3.5 StockMap (timing score, købs- og salgssignal)

**1. Hvad vi ved**
- **Hvad den måler:** aktiens (eller landets, sektorens, industrigruppens) *relative* styrke mod et benchmark, standard RSP, og momentum i den relative styrke. Vandret akse: relativ styrke, 100 = benchmark; lodret: momentum i den; "slangen" er hale af ugentlige punkter rundt om midten (SM1 01:05-03:30; PREM 0:34:36-0:35:46). Kan sættes på enkeltaktier, ETF'er, råvarer, watchlists, sektorer, lande og regioner (SM1 00:31-00:46; PREM 0:41:03-0:43:00).
- **Tidsramme og udglatning:** ugentlige punkter; halelængde 8-12 uger som standard, justerbar op til 52 uger (SM1 08:47-08:55; PREM 0:36:23-0:36:35); gennemsnitstype EMA (valgt) eller SMA (PREM 0:36:38-0:36:43). Beregningen er "bygget over en lang række forskellige glidende gennemsnit" (QTS 0:35:03-0:35:08) og "lidt mere kompliceret" end den simple relative styrke (SM1 10:55-11:01). Sektorer og industrigrupper opdateres ugentligt, aktier natligt (PREM 0:29:55).
- **Retning:** pilens vinkel i kompasgrader, 0/360 op, 90 højre, 180 ned, 270 venstre (PREM 0:29:11-0:29:26).
- **Farver/kvadranter:** grøn (Leading), gul (Weakening), rød (Lagging), blå (Improving). Bevægelsen går med uret.
- **Simpelt køb/salg:** se rettelse 5. Fredag lukker, mandag handles (QTS 0:09:48; 0:39:10-0:39:28). Salg kræver kvadrantskift. Eksit er nu kun dette signal, ikke 50-dages gennemsnittet eller fast stop (QTS 0:33:13-0:35:21).
- **Backtest, simpelt køb (egenrapporteret, 2019-2026, S&P 1500 + andre):** vinderrate ca. 64-65 %, profit factor 2,25, gennemsnit 5,33 % pr. handel, holdetid ca. 18 uger, ca. tre handler pr. år (QTS 0:18:35-0:20:27). Europa 600: ca. 60 % og PF 1,6; S&P 500: ca. 65 %; Nasdaq ca. 67 %; Russell 2000 ca. 55 %; Sverige 63,5 % og PF 2,2 (PREM 0:49:03-0:53:55). Test af sektor- og landeretning viser næsten ingen effekt på rene købssignaler (QTS 0:53:01-0:53:15), men "medvind" (land + sektor + industri samme vej) nævnes som tendens (PREM 0:43:54-0:44:13).
- **Eksempler med datoer:** Genmab simpelt køb fredag 13.03.2026, 76,04 % lukke-til-lukke og 79,62 % fra mandagens åbning (QTS 0:09:18-0:09:41); HMS Networks salgssignal fredag 31.07.2026, solgt mandag, ca. -2 % (QTS 1:00:52-1:02:15); Texas Instruments: gennemløb af 2022-markedet med halen startende ca. 23.12.2021, køb "i bunden" og 9,2 % til toppen (købsdato ikke sagt; PREM 0:37:08-0:37:32), og et nyere signal, +4,45 % indtil videre (PREM 0:40:18); oktober 2026-tilstande: Nvidia grøn og pil ned, industrigruppen Semiconductors gul og ned, IT-sektoren grøn og ned, Sverige/Belgien/Frankrig begynder at pege op, Tyskland kører mod højre, UK ned, Volvo svagt op i grøn (PREM 0:29:01-0:29:46; 0:41:35-0:43:00).

**2. Hemmeligt/ukendt.** Præcise vinduer (RS-gennemsnit, momentumvindue, vinkelvindue), den "lange række glidende gennemsnit", normaliseringen, hvor mange uger "pilen" regnes over, og om signalet tester én fredag eller kræver flere. Værktøjet er lagt til grund for stærk køb og overbevisning (se 3.9), og de to sidste er fabrikshemmeligheder.

**3. Vores kandidat-formel** (afviger fra `mss_compare.stockmap_angle`, som bruger daglige data med 50/10/5-dages vinduer; MSS er ugentligt):

```python
def stockmap_weekly(close_d, bench_d, n_x=26, n_y=10, k=2, kind="ema"):
    w  = close_d.resample("W-FRI").last()
    b  = bench_d.resample("W-FRI").last().reindex(w.index, method="ffill")   # RSP som standard
    rs = w / b
    ma = (lambda s, n: s.ewm(span=n, adjust=False).mean()) if kind == "ema" else (lambda s, n: s.rolling(n).mean())
    x  = 100 * rs / ma(rs, n_x)                   # RS-niveau, 100 = benchmark
    y  = 100 * x / ma(x, n_y)                     # momentum i RS (alt.: 100 + (x - x.shift(m)))
    dx, dy  = x.diff(k), y.diff(k)
    heading = np.degrees(np.arctan2(dx, dy)) % 360    # 0 = op (kl. 12), 90 = højre, 270 = venstre
    quad = np.select([(x>=100)&(y>=100), (x>=100)&(y<100), (x<100)&(y<100)],
                     ["groen", "gul", "roed"], default="blaa")
    return x, y, heading, quad

down = (heading >= 180) & (heading < 270)
up   = (heading >= 270) | (heading < 90)
buy  = down.shift(1) & up & quad.isin(["gul", "roed"])        # fredag lukker -> mandag åbning
sell = (open_buy_quad != quad) & down                           # efter åbent køb: ny kvadrant og pil ned-venstre
```
Parameterraster til kalibrering: `n_x` {10, 14, 20, 26, 40}, `n_y` {4, 6, 10}, `k` {1, 2, 3}, EMA/SMA, og et "multi-MA"-gennemsnit af flere EMA'er. Benchmark RSP for alle universer (også Europa), som MSS.

**4. Kalibrering**
- *Vinkel*: de 9 prøvevinkler (datoer 29.-30.10.2026): median vinkelforskel og andel inden for 45 grader, som `mss_compare.summary()` allerede beregner (mål: median under 30 grader, andel over 70 %). Med n=9 er det kun en sundhedstjek.
- *Kvadrant og retning* i oktober 2026-eksemplerne (ca. 10 tilstande: Nvidia, Semiconductors, IT-sektor, Sverige, Tyskland, UK, Belgien, Frankrig, Volvo, Sverige industrials). Metrik: andel korrekte (kvadrant + op/ned). Data findes for datoerne ca. 12.-16.10.2026.
- *Signaldatoer*: Genmab køb fredag 13.03.2026 og HMS salg fredag 31.07.2026, hver med +/-1 uge som tolerance (hit/miss); de to er de eneste sikre datoer (Texas Instruments' dato er ikke sagt). Det er for lidt, så skærmbilleder af signalhistorik (afsnit 6) er det vigtigste at få.
- *Aggregeret replikering* (sanity, ikke mål): vinderrate 60-67 %, profit factor 1,6-2,25, gennemsnitlig handel 5-5,3 %, holdetid ca. 18 uger, ca. 3 handler pr. aktie pr. år, på S&P 500 og Europa 2019-2026. Vi har survivorship bias, MSS har den delvist også.
- Eksisterende vinkelkode og `regimes.relative_strength` (RS-linje over eget 50-dagesgennemsnit, benchmark forskudt én dag) kan genbruges til sammenligning.

### 3.6 TPI (Turning Point Indicator)

**1. Hvad vi ved**
- En *statistikindikator*, ikke en prognose: for hver aktie sammenholdes nuværende mønster med dens egen historie (ca. 20 år) (BK 1:31:15-1:32:20); den kan ikke programmeres i TradingView, fordi den bruger MSS' egne data (WEB 0:44:07-0:45:09). Kører i en tilpasset TradingView-udgave med tre rækker: TPI-trend (lang, ugebasis), UG-TPI (uge) og DAG-TPI (NF 03:54-04:44; WEB 0:45:14-0:45:18).
- Tilstande, to farveskemaer over tid: *nyere* (NYT 06:26-07:08; BK 1:30:37-1:31:31): lang rød = fortsat ned, lang grøn = op; gul = oversolgt/akkumulering, skifter den til grøn er der større chance for op; grå = overkøbt, skifter den til rød større chance for ned. *Ældre* (WEB 0:49:39-0:50:00; DSK 02:01-02:13; TPI24): mørkegrøn/lysegrøn/lyserød/mørkerød, hvor lyserød = oversolgt akkumulering og lysegrøn = overkøbt akkumulering; lang bar kun grøn/rød.
- **Triple green** (lang + uge + dag grønne) = køb, salg når ugen bliver rød (WEB 0:46:35-0:47:06; PAN 0:02:01); alternativt lang grøn + kort række i oversolgt (BK 1:35:04-1:35:21). Køber ikke, så længe den lange er rød (DSK 02:36-02:45; Vestas 0:06:18). Kursen skal være over 10-ugers (=50 dages) gennemsnit (WEB 0:46:26). En "TPI swing trades"-screener findes: 2 danske hits i WEB, 4 i DSK; kriterierne er ikke oplyst (observeret: lang grøn + uge/dag i oversolgt) (WEB 0:13:19-0:13:49; DSK 04:45-05:09).
- Ingen procenter eller tærskler i noget materiale.

**2. Hemmeligt/ukendt.** Alt kvantitativt: hvilke features der matches, matchvindue, hvor "oversolgt" begynder, hvornår en bar skifter farve. Navnet i sig selv antyder vendepunkter, men beskrivelsen er trendfølgende (lang bar).

**3. Kandidat (to trin, billigste først)**
```python
# trin 1: trendstatus uden statistik
lang_groen = (sma(close_w, 10) > sma(close_w, 40)) & (sma(close_w, 40).diff(4) > 0)   # ~ SMA50 over SMA200
# trin 2: egen-historik-percentil som oversolgt/overkøbt
z   = (close / sma(close, 50) - 1)                         # afstand til gennemsnit
pct = z.rolling(5 * 252, min_periods=500).rank(pct=True)   # aktiens egen historie
oversolgt, overkoebt = pct < 0.10, pct > 0.90
# skifte: gul -> groen når pct krydser op over 0.10 og 3-dages afkast > 0; omvendt for grå -> rød
# trin 3 (hvis det kan betale sig): nærmeste-nabo-analogier i aktiens egen historie (k=50) og fremtidigt afkast
```
**4. Kalibrering.** 26 rækker (6 med dato). Tilstandstjek: Tesla 05.03.2024 (lang ned; uge op men overkøbt; dag ned og overkøbt), Genmab triple green ved kurs 2750 og uge rød ved 3200 (WEB 0:47:52), Pandora triple green ved ca. 590 (PAN), SIGA gul/grøn fredag 31. maj (7-8 % op på lidt over en uge, SIGA 0:08:01-0:08:25; usikkert år, 2024 er en fredag). Metrik (to lag): (a) tilstandsoverensstemmelse på de ca. 10 daterede punkter, (b) vigtigere: giver *vores* triple green / oversolgt-til-grøn en positiv edge i `regimes.regime_backtest` (hit rate og edge mod alle dage, 5/20/60 dage, urørt periode)? Vi kan ikke "ramme" en hemmelig formel; vi kan måle, om en åben variant er nyttig.

### 3.7 MTI (Momentum Trend Indicator)

**1. Hvad vi ved**
- Måler *aktiens kurs mod en række andre ting* (indeks, sektorer) og bliver grøn, når aktien løber hurtigere end dem (NYT 07:14-07:48). Kører på dagsgraf og ugegraf (to kopier af samme indikator) (NF 05:07-05:22; LW 0:32:19-0:32:37; QA26 0:11:12). "Dobbelt grøn" = dag + uge grøn = entry-betingelse sammen med glidende gennemsnit; ugerød = overordnet trend ned, kortvarig dagsgrøn er kun swing (NF 05:33-06:00; QA26 0:19:51). Skifter dagligt (LW 0:53:57). "Dobbelt rød" meget af tiden = ikke køb (MSFT i QA26).
- Indgår i stærk køb og overbevisning, med MTX og TPI (PREM 0:50:35-0:50:53). Kan screenes (NYT 05:12).
- Observationer: TSM, Rheinmetall, Barrick dobbelt grøn og Amazon dag rød (21.01.2026); Micron grøn/grøn, MSFT mest dobbelt rød, Glencore og Rio Tinto dobbelt grøn (18.02.2026); Nvidia og FCX dobbelt grøn, Novo dobbelt rød (04.03.2026) (CSV).

**2. Hemmeligt.** Benchmark-sættet, hvordan "bedre" afgøres (niveau, hældning, krydsning), vinduer for dag/uge, tærskel for flertal. Formlen er en del af fabrikshemmeligheden (PREM 0:50:47).

**3. Kandidat**
```python
BENCH = ["SPY", "RSP", sektor_etf(ticker), lokalt_indeks(ticker)]       # sæt tilpasses markedet
def mti(close, tf, n):                      # tf "D" eller "W", n = 50 (D) / 10 (W)
    c = close if tf == "D" else close.resample("W-FRI").last()
    gron = [ (c / b_tf) > (c / b_tf).rolling(n).mean() for b_tf in bench_series(tf) ]
    return sum(gron) >= 3                   # flertal; alt.: gennemsnit af RS-hældning > 0
dobbelt_groen = mti(c, "D", 50) & mti(c, "W", 10)
```
**4. Kalibrering.** 12 MTI-rækker (9 dateret, 11 uafhængige tilstande ovenfor). Metrik: andel korrekte tilstande (grøn/rød pr. tidsramme), mål mindst 9 af 11; derudover forward-afkast efter "dobbelt grøn" mod alle dage i `regimes`. Parametre vælges på halvdelen af punkterne og testes på resten.

### 3.8 MTX (Momentum Trend Explosion)

**1. Hvad vi ved.** Ny (NYT, ca. maj 2026). Absolut, ikke relativ: "en lang række faktorer" afgør, om aktien trender/løber stærkt og om en eksplosion kan være på vej; kun to tilstande, grøn baggrund i diagrammet ved køb, ellers hvid; ingen garanti for stigning (NYT 07:50-08:32). Bruges sammen med MTI som "ekstra rygstød" (NYT 08:46-08:54), skifter til hvid, når trenden holder pause. Skal kunne screenes (NYT 09:34). Indgår i stærk køb/overbevisning (PREM 0:50:35). Der er en visningsfejl (stor graf) i NYT 06:00.
**2. Ukendt.** Alt andet; ingen observationer i CSV.
**3. Kandidat (pladsholder, tæt på `candles.detect_patterns`):** kursen over SMA50 og SMA200, 20-dages-høj brudt på volumen mindst 1,5 x snit, ATR-ekspansion (ATR(5)/ATR(20) over 1,1) og positiv 20-dages relativ styrke. Kun nyttig som ekstra filter i konviktions-stigen (3.9).
**4. Kalibrering.** Ingen data. Kræver skærmbilleder af MTX på/af (afsnit 6) eller screener-lister over "MTX grøn" for flere dage; så ville dette kunne måles som klassifikation.

### 3.9 Timingzoner (timing score)

**1. Hvad vi ved**
- Tilstande, der vises i appen: Neutral (ingen aktiv signal), Behold, Købszone (simpelt køb), Stærk købszone, Købszone med overbevisning (conviction buy); Salgszone forventet (PREM 0:22:36-0:22:50; 0:33:25; prøven). Buy = ren StockMap; stærk køb og overbevisning "blander andre ting ind" (TPI, MTI, MTX), og reglerne er en **fabrikshemmelighed** (PREM 0:50:12-0:50:58; QTS 0:22:16-0:22:44). Opdateres hver nat (PREM 1:03:35). Timingzonen ændrer sig til "at handle langsommere", fordi markedet er zigzag og stop-ud er dyrt (PREM 0:23:04-0:23:45).
- Egenrapporteret backtest 2019-2026 pr. niveau (PREM 0:48:26-0:53:55): *Europa 600*: køb ca. 60 % vindere, PF 1,6; overbevisning 240 handler, 79,4 %, PF ca. 4, holdetid 17-21 uger. *S&P 500*: køb ca. 65 %; overbevisning 351 handler, ca. 78 %, PF 6,6, ca. 20 uger, 18 % i snit pr. handel (statistisk). *Sverige*: køb 63,5 %, PF 2,2, 5,2 % i snit. Der er "rigeligt" simple køb, men langt færre stærke og overbevisende.
- Modelportefølje (154 handler siden 1.1.2025): med simpelt salg lagt til gav test 77,4 % vindere i 2025 og 66 % i 2026 mod under 50 % og 37,2 % med den gamle exit (PREM 1:04:46-1:05:59).
- Prøvens vinkelmønster (9 rækker, ikke tickers): *Købszone, Stærk og Overbevisning* har alle pil opad (vinkler i intervallet 298-45 grader); *Behold* har 242-245 (nedad mod venstre); *Neutral* har 201, 247 og 88. Samme vinkel kan altså give Behold eller Neutral, så tilstanden afhænger af historikken (åben position eller ej), ikke kun af nuværende pil.

**2. Hemmeligt/ukendt.** Udløsere for stærk og overbevisning, hvor længe en Købszone gælder efter signalet, om Behold er "åben position uden frisk signal", og hvordan Salgszone kommer ind.

**3. Kandidat**
```python
state = "Neutral"
for t in weeks:                                    # fredag lukker
    if buy[t]:      state, since = "Købszone", t
    elif state in ("Købszone","Behold") and sell[t]:   state = "Salgszone"
    elif state == "Købszone" and t - since >= N_FRISK:  state = "Behold"   # N_FRISK 4-8 uger, gæt
    elif state == "Salgszone" and t - sell_t >= 1:     state = "Neutral"
# stigen (kun gæt): stærk = Købszone & mti_dobbelt_groen & tpi_ikke_overkoebt
#                   overbevisning = stærk & mtx_groen & (quality_pct >= 60 eller trend > SMA200)
```
**4. Kalibrering.** (a) 9 prøverækker: tilstandsoverensstemmelse (lav styrke, men kan afvise forkerte N_FRISK); (b) screener-lister (afsnit 6) giver hundreder af labels pr. dag; (c) *stigens form*: antal og vinderrate skal følge MSS' mønster, dvs. overbevisning færre end 1/10 af køb og 10-20 procentpoint højere vinderrate; vi skal ikke ramme 79 %, men vise, at en åben stige har samme monotoni; (d) Mandagsåbning for handel, kurtage og slippage som i `regimes.forward_returns`.

### 3.10 Glidende gennemsnit (20/50/200 og 10 uger)

**1. Hvad vi ved.** Standard i deres grafer: 20 dage (rød), 50 dage (grøn), 200 dage (sort) (QA26 0:11:56-0:12:20; LW 0:32:53-0:33:21); 10-ugers gennemsnit svarer til 50 dage (WEB 0:46:26). Egen "Multi Moving Average"-indikator med frit valg af SMA/EMA og længder, og en automatisk støtte/modstand-indikator (rød over kurs, grøn under, grå midt i) (NF 01:48-03:44).
- **Regler (spring 2026):** kurs over 200 dage er "kardinalregel" for køb, helst også over 50 dage med højere toppe og bunde (LW 0:32:53-0:33:21; QA26); 50-dages-brud er første alarm og stopklods, 200-dages-brud er ud, 20 dage bruges i meget hurtige løb (Micron: brud på 20 dage efter ca. 13 % fald, 17-18 % over 50 dage) (QA26 0:13:50-0:15:04; BW 0:51:47-0:53:04). "Snor", hvis 200 dage og et støtteområde ligger lige under (Nvidia, QA26 0:47:43-0:48:03). 190 eller 220 dage gør ikke forskel (BW 0:25:25). Kursen skal ligge over 200 dage ved køb (BW; LW).
- **Ændring (efterår 2026):** 50-dages-exit er opgivet til fordel for StockMap-salgssignalet, fordi faste stops koster mere i det nuværende marked (QTS 0:33:13-0:35:21). RISK (slut maj 2026) bruger endnu 50 dage.
**2. Ukendt.** Hvor stor "snor" der gives, præcis hvornår 20 dage vælges frem for 50.
**3. Kandidat.** Allerede delvist i `candles.trend_context` (SMA50/SMA200). Tilføj SMA20 og en exit-motor med tre regler: A) ud ved lukning under SMA50, B) ud ved lukning under SMA20 når kursen står mere end 15 % over SMA50, C) ud under SMA200 uanset; "snor" = ingen exit, hvis lav ligger inden for 2 % af SMA200 eller et pivot-støtteområde.
**4. Kalibrering.** 25 rækker; kun få med både dato og niveau (Micron 20-dages brud, 18.02.2026; Glencore 6-7 % og Rio Tinto 11 % over stopklods; Novo solgt ved SMA50-brud omkring 850-860 (BW); Rheinmetall solgt jul-aug 2025). Metrik: falder vores regel A/B på samme uge (+/-1 uge) som deres? Mål: 4 af 5. Større værdi: backtest af A/B/C mod fast hold i `regimes`/`candles.trade_backtest` (drawdown, hit rate).

### 3.11 Supertrend

**1. Hvad vi ved.** Volatilitetsstop: gennemsnitlig daglig bevægelse (ATR) over 10 perioder, ganget med en faktor, 3 (smal) eller 5 (bred) (SAAB 0:14:58-0:15:09; RISK 11:09-14:15). Flytter sig op med kursen; kan lægges som alarm i TradingView. Nvidia-eksemplet: ATR x 10 holdt aktien i hele trenden, men gav 36 % ned fra toppen; x 3 og x 5 lå ca. 6 % og 13-14 % fra kursen ved indgang (RISK 12:12-15:50). På 4-timers-graf og 10-perioders gennemsnit lå stoppet 8-9 % væk, mod ca. 20 % på dagsgraf (SAAB 0:11:03-0:12:37). Bred stop kræver mindre position: samme risiko (0,5 % af kapitalen) gav 378 aktier med tæt stop og 174 med bredt (RISK 14:42-16:00).
**2. Ukendt.** Intet hemmeligt; standardindikator ("ikke en vi har fundet på").
**3. Kandidat.**
```python
atr  = tr.ewm(alpha=1/10, adjust=False).mean()                # Wilder, TradingView ta.supertrend(3, 10)
upper, lower = hl2 + f*atr, hl2 - f*atr                       # f = 3 eller 5; lås bånd (ratchet)
stop_pct = f * atr / close                                    # afstand til stop
shares   = (capital * risk_pct) / (entry - stop)              # risk_pct = 0,5 %
```
**4. Kalibrering.** 3 rækker. Reproducér procentafstande (6 % og 13-14 % for Nvidia med f=3/5 på det daglige billede, hvis datoen findes) og tjek, at positionsstørrelsen skalerer omvendt med afstanden (rent regneark). Backtest: stoptype (SMA50 / Supertrend 3 / 5) mod drawdown og afkast, med samme indgange.

### 3.12 Regressionskanal

**1. Hvad vi ved.** TradingView-værktøjet "Regression Trend", tegnet manuelt (REG; DSK 06:01-06:33). Midterlinje = bedste rette linje gennem kurserne i udsnittet; øvre og nedre linje = +/-2 standardafvigelser, som skal rumme mindst ca. 95 % af punkterne. Ugegraf foretrækkes, helst et halvt år eller mere. Pearsons R viser, hvor godt linjen passer: over 0,9 ønskes, 0,95 er godt; typisk 0,7-1 (REG 0:12:54-0:13:30; eksempler 0,987 og 0,53). Linjen flytter sig ved nye data. Købsidé: bunden af kanalen = billig; brud over øvre linje, lille tilbagefald og bekræftelse; stop-loss, hvis det ikke går op (REG 0:08:03-0:09:03). Metoden er subjektiv og et sandsynlighedsværktøj.
**2. Ukendt.** Intet hemmeligt, men startpunktet vælges af øjet, og der findes ingen automatisk udgave i materialet.
**3. Kandidat.**
```python
def reg_channel(close_w, n):                         # n uger bagud
    y = np.log(close_w[-n:]); x = np.arange(n)
    b, a = np.polyfit(x, y, 1); res = y - (a + b * x); s = res.std(ddof=2)
    r = np.corrcoef(x, y)[0, 1]
    return {"mid": a+b*x, "up": a+b*x+2*s, "lo": a+b*x-2*s, "R": r, "pos": (y[-1]-(a+b*x[-1]))/s}
# automatisk start: vælg n i {26, 52, 104} med højeste R og R >= 0,9
```
**4. Kalibrering.** 4 rækker (Ambea købt ved 50 efter brud; R 0,987 og 0,53 uden sikker aktie). Praktisk: tjek, at 2-sigma-båndet rummer over 90 % af uge-lukkekurser, og at R-fordelingen for aktier i trend ligger 0,7-1. Kan bruges som "plads i kanalen" (pos) i et kandidatskærm.

### 3.13 Strategy mixer og de fire algostrategier

**1. Hvad vi ved.** Fire regelbaserede porteføljer på amerikanske aktier (EU eksperimentel): *Quality Momentum* (høj kvalitet + højt momentum), *TPI Plus* (kvalitet + TPI-indikator, i praksis tilbagefald/oversolgt i kvalitetsaktier), *Value Momentum* (omvendt: meget lav value-score + højt momentum, "hype") og *Value Quality* (høj value + høj kvalitet) (MIX 0:02:46-0:03:32; ALGO1 0:00:51-0:01:01, 0:04:04-0:04:10). Rangering af de bedste N (15 pr. strategi som standard, 5 for små konti) (ALGO1 0:10:54; MIX 0:04:43). Standard 25 % pr. strategi, rebalancering første handelsdag hver måned, én opdatering om dagen, brøkaktier valgfri (MIX 0:03:37-0:04:21). Benchmark RSP (ALGO3 0:05:14). Handelsomkostninger ca. 1-1,5 % pr. år trukket fra i backtest (ALGO2 0:05:14). Backtest 25 år (2000-2003 udeladt som outliers), ca. 20 % pr. år fra 2004; live-tracking siden 1.1.2024; 15-20 % pr. år i backtest og "nogenlunde" det samme live (QTS 0:45:30-0:45:54). Egenrapporterede tal: helår 2023 23,5 %, 2024 20,6 %; YTD 2024-11-07 QM 15,2 / TPI Plus 31,8 / VM 22 / VQ 19 %; 2022 (backtest) QM -25 %, TPI Plus +12 %; YTD marts 2025 omkring nul (ALGO2-3).
**2. Hemmeligt.** Tærskler og rangeringsvægte; definitionen af momentum og TPI-trigger; sektorloft.
**3. Kandidat.**
```python
rank = lambda s: s.rank(pct=True)
QM  = rank(quality) + rank(momentum)
VM  = (1 - rank(value)) + rank(momentum)       # omvendt value
VQ  = rank(value) + rank(quality)
TPIP = rank(quality)[tpi_oversold & lang_groen]
portfolio = equal_weight(top_n(QM,15), top_n(TPIP,15), top_n(VM,15), top_n(VQ,15))   # månedlig rebalancering
```
**4. Kalibrering.** 26 rækker, men uden point-in-time-fundamentaler (yfinance) bliver en backtest forudindtaget. Brug kun: rækkefølgen af de fire strategier i nov. 2024 (TPI Plus bedst, QM svagest) som svag sundhedstjek, og antal unikke aktier (43 ved 15 pr. strategi, 18 ved 5; MIX 0:04:46-0:06:01). Lav prioritet.

### 3.14 Porteføljeregler (positionsstørrelse, drawdown, exit)

**1. Hvad vi ved.**
- Størrelse: ca. 2,2-3 % pr. aktie, op til ca. 40 aktier (BW 0:09:47-0:10:27; LW 0:35:04; QA26 0:48:07), så et fald på 20 % koster ca. en halv procent af porteføljen. Start med en kvart eller halv position og læg på ved bekræftelse (BK 1:39:05; SIGA 0:06:48-0:07:03). Øg ikke en faldende aktie.
- Risiko pr. handel kan fastsættes som procent af kapitalen / stopafstand (RISK 14:42-16:00).
- Stop: ingen automatiske stop-ordrer ("håndholdt"), fordi gap efter regnskab ellers rammer værst (QA26 0:50:09-0:52:29; BW 0:36:44-0:37:04); alarmer i TradingView. Ingen køb tæt på regnskab, men efter (BW; LW 0:20:33-0:20:48 usikkert begrundelse).
- Mål og egenrapporterede tal: maks. drawdown under 10 % (7-8 % rapporteret) mod 23 % for markedet i samme periode (RISK 04:30-05:14); gennemsnitlig vinder ca. +22-23 %, taber ca. -6,4 % (LW 0:35:40; RISK 06:21-06:36, taberen nævnes som "17", sandsynligvis en hørefejl, usikkert); vinderrate normalt 55-65 %, i perioder 37-50 %. Beslutningen om exit skal være den samme hver gang (RISK 19:45-20:41).
- Statistik i porteføljesiden: afkast, CAGR, Sharpe og Sortino (over 1 er glimrende), max drawdown, volatilitet, beta, alpha (Introvideo 3 0:03:34-0:04:31).
- Hedge med indeksoptioner ved nedtursmodel (50-70 % af faldet) er uden for algoritmerne (ALGO1 0:07:26-0:08:25).
**2. Ukendt.** Modellen bag nedturs-pil og makro-model (ALGO1; swing-video); sektorbegrænsninger.
**3. Kandidat.**
```python
size_pct   = min(0.03, risk_pct / stop_pct)             # 0,5 % risiko; loft 3 %
n_pos_max  = 40
tranche    = [0.25, 0.25, 0.50]                          # kvart position først; resten ved bekræftelse
dd_alarm   = portfolio_dd < -0.10
```
**4. Kalibrering.** Ca. 25 rækker, mest statistik. Metrik ved backtest af egne regler: maks. drawdown og andel af handler med taber under -8 %; ikke at ramme MSS' tal. Indgår i byggeplan 4.

### 3.15 Temaer og short interest (kort)

- **Short interest** (kun amerikanske aktier, SI): andel af tilgængelige aktier, der er shortet, og *short ratio* = hvor mange dages gennemsnitsomsætning der skal til for at dække. Eksempler: Nvidia 1,3 % og 0,8 dag; GameStop 10 % og 5,7 dage (SI 00:38-04:22). Ingen signalregel nævnt. Kandidat: `shortPercentOfFloat` og `shortRatio` fra yfinance (gratis); kalibrering med de to eksempler giver kun en størrelsesorden, så verifikation kræver friske tal.
- **Temaer:** et nyt tema om ugen med underemner, aktieliste og en egen graf, "som om temaet var en industrigruppe" (TEMA1 00:16-02:52). Udvælgelse: medier plus StockMap (ETF'er/industrier, der går fra rød/Lagging til blå/Improving) mod RSP; aktier skal stadig opfylde 3-point playbook (TEMA2 01:35-03:38; 06:39). Eksempler med egenrapporterede afkast siden maj/august 2026 (guldminer-ETF ca. +35 %, software +12 %, fintech +9 %, S&P ca. +2 %) (TEMA2 04:43-05:30). Kandidat: lige-vægtet tema-indeks mod RSP + StockMap på indekset. Ingen CSV-data at kalibrere mod; ikke et første skridt.

---

## 4. Fælles kalibreringsramme

**Data i dag.** `mss_video_observations.csv`: 435 rækker, 146 med eksakt dato (hovedsageligt 21.01.2026: 47, 18.02.2026: 28, 04.03.2026: 26, 05.03.2024: 16, 08.10.2025: 14); resten "optagelsesdato" eller grove tidsrum. `mss_observations.csv`: 9 fulde rækker (29.-30.10.2026) med Quality, Value, Moat, MSS-score, timingzone og StockMap-vinkel. Kun disse 9 har alle felter.

**Tre typer test, billigst først:**
1. *Regnestykker* (ingen data nødvendig): upside-procenter, implicit P/E, positionsstørrelse, MSS-score = middel af tre. Skal passe, ellers har vi misforstået formlen.
2. *Tilstandstjek på kendte datoer*: er aktien grøn/rød, i hvilken kvadrant, hvilken retning (MTI, TPI, StockMap, glidende gennemsnit). Kursdata findes historisk.
3. *Rangkorrelation og kantsammenligning på friske snapshots* (Quality, Value, zone, vinkel). Kræver nye observationer med samme dato som vores dataindhentning.

**Metrikker:** vinkelforskel (median og andel inden for 45 grader), ramt signaldato +/-1 uge, Spearman, gennemsnitlig absolut afvigelse efter isotonisk kort, andel korrekte tilstande, og for tidsværktøjer: edge mod alle dage med den urørte slutperiode som i `regimes.regime_backtest`.

**Faldgruber.** (1) Survivorship bias i vores indeksmedlemslister; (2) look-ahead: brug kun lukning, der var kendt (benchmark forskudt som i `regimes.relative_strength`); (3) europæiske aktier mod RSP, som lukker senere samme dag; (4) små stikprøver: bootstrap-intervaller, ikke enkeltprocenter; (5) MSS' egne tal er backtest og udvalgte eksempler; vores mål er adfærd, ikke at matche afkast.

---

## 5. Prioriteret byggeplan (top 5)

| # | Hvad | Hvorfor først | Indsats | Observationer | Færdig når |
|---|---|---|---|---|---|
| 1 | **Værdikanal + værdiscore + PEG** (`valuechannel.py`) | Formlen er næsten fuldt specificeret og kan checkes med regnestykker; flest rækker (ca. 68, 27 med scenarier) | 2-3 dage | 68 + 14 PEG | Upside-procenter genskabes inden for 2 procentpoint på Vestas/CoreCivic/Apple/Micron; score A/B valgt mod prøven |
| 2 | **StockMap (ugentlig) + simpelt køb/salg + zone-tilstandsmaskine** (`stockmap.py`, udvid `mss_compare`) | Kernen i deres timing; kan kalibreres på tidligere datoer; genbruger `regimes` | 3-5 dage | 18 + 9 vinkler + 2 sikre signaldatoer | Median vinkelforskel under 30 grader; Genmab køb og HMS salg inden for +/-1 uge; aggregeret vinderrate 60-67 % på S&P 500/Europa |
| 3 | **Quality-percentil + Moat + MSS-score = middel** (`quality.py`) | Lav indsats oven på eksisterende model; MSS-scoren giver sig selv | 1-2 dage | 20 + 9 (+ nye) | Spearman over 0,7 mod prøven; MSS-score fejl under 0,5 |
| 4 | **Regelpakke: SMA20/50/200-exit, Supertrend (10, 3/5), regressionskanal (+/-2 sigma, R), risikobaseret positionsstørrelse** | Helt deterministiske, få afhængigheder, udvider `candles`/`regimes` med exit- og risikodel | 2-3 dage | ca. 35 | Exit-regler testet mod fast hold (drawdown, hit rate); afstande 6 % / 13-14 % reproduceret |
| 5 | **MTI-lite (relativ styrke mod flere benchmarks, dag + uge, dobbelt grøn)** | Bruges i alle deres signaler (stærk/overbevisning) og i playbook; 12 rækker | 2 dage | 12 | Mindst 9 af 11 tilstande korrekte; positiv edge mod alle dage |

Udskudt: TPI (statistisk, ingen tærskler), MTX (ingen observationer), strategy mixer/algo (kræver point-in-time-fundamentaler), temaer og short interest (lille værdi nu). Zone-stigen (stærk/overbevisning) bygges som et gæt oven på 2 og 5, når labels fra screener-lister er indsamlet.

---

## 6. Data Allan bør indsamle i den resterende MSS-prøveperiode

Prioriteret efter værdi pr. minut. Alt som skærmbilleder (datoer synlige) plus CSV, hvor det kan lade sig gøre; ét fælles ark pr. dag.

1. **Watchlist-eksport dagligt.** Eksporten til TradingView er kun tickers, ikke scorer. Bed derfor om skærmbillede af tabelvisningen (Quality, Value, Moat, MSS-score, timingzone, StockMap-pil og kvadrant) for en fast liste på 40-60 aktier: ca. 15 danske, 15 europæiske, 20 amerikanske, plus RSP og en indeks-ETF. Samme liste hver fredag aften (signaldagen) og mandag morgen (efter natopdatering). Mål: 10 fredage = 500+ labeled rækker.
2. **Screener-lister som labels.** Kør screeneren med *kun overbevisning*, *stærk køb og overbevisning* og *alle køb* for USA, Europa og Skandinavien; gem tickerlisterne og antal. Gør det samme for "TPI swing trades", MTI dobbelt grøn, MTX grøn og StockMap blå, når de kan screenes (NYT 09:34, 13:34). Gentag over 3 uger: giver både labels og signaldatoer for hundredvis af aktier.
3. **Signalhistorik og StockMap med benchmark.** For ca. 20 aktier (inkl. Genmab, HMS Networks, Texas Instruments, Nvidia, Volvo): StockMap på maksimal halelængde (op til 52 uger) med synlig indstilling (benchmark, EMA/SMA, hale) og "expand"-visningen med købs-/salgsmarkører og afkastboksen (PREM 0:37:14; QTS 0:08:08-0:10:00). Skærmbillede af hver, samt af indstillingspanelet.
4. **Værdikanal-siden** for 15 aktier: hele grafen med de tre P/E-værdier (rød/blå/grøn), potentiale i procent, EPS-estimatbokse, målkurs, 3/5/10-års P/E og begge værdiscorer (system og "min"). Samme aktier som i punkt 1, så vi kan sammenligne med yfinance samme dag.
5. **Kvalitetsbokse** (summary): alle delbokse med farve og tal for 10 aktier, både land- og regionsscore. Plus hele C25 (eller en anden fuld liste) på én dag: 25 punkter giver en rigtig rangkorrelation.
6. **TPI- og MTI-/MTX-rækker** på 10 aktier ugentligt: farven (gul/grå eller lyserød/lysegrøn; MSS ændrer skema), lang/uge/dag, MTI dag/uge, MTX til/fra. Noter, hvilket farveskema der vises.
7. **Hjælpetekster.** Skærmbilleder af alle "?"-forklaringer og hjælpesektionen (NYT 00:32-00:56) for Quality-delmål, farvegrænser, StockMap og timingzoner; MSS har lovet gennemsigtig forklaring.
8. **Skema til hver observation:** dato og klokkeslæt, ticker (og børs), værktøj, værdi eller tilstand, tidsramme, benchmark, opdateringstidspunkt. Tilføj kolonner i `mss_observations.csv`: `value_system`, `value_own`, `mti_dag`, `mti_uge`, `tpi_lang`, `tpi_uge`, `tpi_dag`, `mtx`, `kvadrant`, `benchmark`, `hale_uger`, `ma_type`.

---

## 7. Forbehold

- Alle tal fra MSS er egenrapporterede eller backtests og er ikke kontrolleret af os. Vinderrater på 78-80 % for "overbevisning" kommer fra et lille udsnit af signaler og kan ikke forventes i drift.
- Whisper-udskrifter har hørefejl; hvor et tal er uklart, står "(usikkert)". Videoernes datoer er skøn, medmindre de står i titlen.
- Vores modeller er screening og forskning, ikke rådgivning. Ingen købs- eller salgsanbefaling; aktienavne er kalibreringspunkter.
- Dokumentet må ikke bruges som facitliste for at ændre en test, til den bliver grøn. Hvis en kalibrering ikke lykkes, skal modellen dokumenteres som afvigende, ikke tunes til resultatet.
