# Resultat B-15: Kalibrér mod facitlisten

Kørt 03-11-2026 med `scripts/calibrate_b15.py` (hjælpere i `stockscanner/calibration.py`, tests i `tests/test_calibration.py`).
Facit: `data/mss_video_observations.csv` (1180 rækker, rettes aldrig). Rådata fra kørslen: `data/b15_resultater.csv`
(én række pr. sammenligning), `data/b15_rapport.md` (alle forvekslingstabeller og misses), navnetabel `data/b15_ticker_map.csv`
(kan rettes i hånden; kørslen bevarer rettelser). `data/` er gitignoreret, så de tre filer ligger kun lokalt.
Screening og historisk test, IKKE en købsanbefaling.

## Kort konklusion

- **Stemmer med MSS:** TPI-lite lang trend (8 af 9) og MTI-lite "dobbelt grøn" (11 af 12). Begge slår både tilfældighed og "gæt altid den hyppigste" (p = 0,02 og 0,015), men n er lille.
- **Kan ikke afgøres:** StockMap (kun 2 kvadrant/pil-rækker og 2 signalrækker med dato), TPI uge oversolgt/overkøbt (3 rækker, alle Tesla fra samme billede, 0 af 3), værdikanalens billig/dyr (5 rækker), regressionskanal (5 af 10, ikke bedre end baseline).
- **Stemmer dårligt:** regressionskanalens brud (kun 1 af 6 brud-udsagn rammes; "inde i kanalen" rammes 4 af 4) og de gamle zone-/trendmodel-rækker fra 2019–21 (5 af 9).
- **Løst sammenlignet:** Quality-percentil rangkorrelation 0,53 (n = 13, gns. afvigelse 13 point); P/E-niveau median-forhold 1,03, men rangkorrelation kun 0,37 (n = 8).
- **Ret ikke formler ud fra dette.** Det eneste, facitlisten robust siger, er at to værktøjer ikke er forkerte. Resten mangler data, ikke nødvendigvis modelkvalitet.

## Tragt: hvorfor så få sammenligninger

| Trin | Rækker |
|---|---|
| Facitlisten | 1180 |
| Brugbar dato (fuld dato 302, kun år-måned 274, optagelsesdato fra videotitel 1) | 577 |
| Selskab (ikke portefølje, strategi, indeks, land) | 420 |
| Med sikker ticker | 366 |
| Kan testes mod en model vi har (tilstand + værktøj + data) | cirka 60 |

- **Datoer:** "ukendt", "2024 (usikkert)", "2019-2026 (backtest)" mv. er kasseret. "YYYY-MM" bliver den 15. i måneden; "optagelsesdato" bruger videoens dato fra titlen ("13-6-24"). Upræcise datoer prøves også ±1–3 uger og vises som "lenient".
- **Navne:** 107 navne i `data/b15_ticker_map.csv`. 25 rækker uden ticker (fx Tall Brothers, Shape Robotics, Seloxid, Montage Group), 29 rækker med gættet ticker udeladt (forvanskede transskriptionsnavne som Plejt, Alcabello, Kemomatic, Celan Pharma; yfinance-søgning bruges kun som forslag og tæller ikke). Ingen kursdata på Yahoo for Fingerprint, Lundbeck (LUN.CO) og SimCorp.
- **Ingen look-ahead:** alle vores værdier beregnes på kurser skåret ved datoen (ugebarer kun hvis ugen er afsluttet). Analytikertal findes kun for i dag, så værdikanalen testes med P/E-kanalen alene (trailing P/E, min/max af 1/3/5/10/20-års median, som `valuation.value_channel`).
- **Rækker er ikke uafhængige:** flere rækker kommer fra samme billede (3 Tesla-rækker, flere Novo-rækker). Udvælgelsen er MSS' egne eksempler, typisk købskandidater, så grøn/dobbelt grøn er hyppigere end i et tilfældigt udsnit; derfor vises også baseline.

## Hit-rater pr. værktøj

"Tilfældig" = forventet hit-rate hvis vores kategori var uafhængig af MSS' med samme fordelinger. "Altid-hyppigste" = hit-rate ved altid at gætte MSS' hyppigste kategori. p = ensidig binomialtest mod "tilfældig".

| Værktøj | Delmåling | n | Hit | Hit-rate | Lenient | Tilfældig | Altid-hyppigste | p |
|---|---|---|---|---|---|---|---|---|
| MTI-lite | dobbelt grøn / ikke | 12 | 11 | 92 % | 92 % | 58 % | 75 % | 0,015 |
| TPI-lite | lang trend grøn/rød | 9 | 8 | 89 % | 89 % | 49 % | 56 % | 0,018 |
| TPI-lite | uge oversolgt/overkøbt | 3 | 0 | 0 % | 0 % | 0 % | 67 % | – |
| StockMap | kvadrant | 2 | 1 | 50 % | 50 % | 50 % | 100 % | – |
| StockMap | pil op/ned | 2 | 1 | 50 % | 100 % | 50 % | 50 % | – |
| StockMap | købssignal (nu / seneste 12 uger) | 2 | 2 | 100 % | 100 % | – | – | – |
| Regressionskanal | uden for / inde | 10 | 5 | 50 % | 50 % | 37 % | 40 % | 0,29 |
| Værdikanal (P/E-kanal) | billig/dyr, kanalposition | 5 | 3 | 60 % | – | 44 % | 60 % | 0,39 |
| Værdikanal | billig/dyr, egen P/E-percentil | 5 | 3 | 60 % | – | 44 % | 60 % | 0,39 |
| 200-dages gns. (kontrol) | over/under | 4 | 3 | 75 % | 75 % | 75 % | 100 % | – |
| Zone/trendmodel 2019–21 mod TPI-lang (udforskende) | grøn/rød | 9 | 5 | 56 % | 78 % | 51 % | 56 % | 0,52 |

Under n ≈ 10 er et hit-rate ikke et resultat, kun en indikation.

### Forvekslingstabeller (række = MSS, kolonne = vores)

MTI-lite:

| | dobbelt grøn | ikke dobbelt |
|---|---|---|
| dobbelt grøn | 8 | 1 |
| ikke dobbelt | 0 | 3 |

TPI-lite lang trend:

| | grøn | rød |
|---|---|---|
| grøn | 4 | 1 |
| rød | 0 | 4 |

TPI-lite uge (alle vores = neutral): MSS overkøbt 2, MSS oversolgt 1.

Regressionskanal:

| | inde | over | under |
|---|---|---|---|
| inde | 4 | 0 | 0 |
| over | 2 | 0 | 1 |
| under | 1 | 1 | 1 |

StockMap kvadrant: MSS grøn (leading) 2 gange, vores leading 1 og lagging 1. Pil: MSS ned 1 (rammet), MSS op 1 (vi sagde ned; rammer ved lenient).

### Notable misses

- **MTI-lite:** Nvidia 2026-03-04, MSS "dobbelt grøn" (timing, dag), vi dobbelt-ikke-grøn.
- **TPI lang:** Target 2024-01-24, MSS grøn trend med oversolgt akkumulering, vi rød.
- **TPI uge:** Tesla 2024-03-05, alle tre MSS-udsagn (to gange overkøbt, én gang oversolgt "tidligere i perioden") kommer fra samme billede og er indbyrdes modstridende; vores ugetilstand er neutral. Ikke et brugbart fejlsignal.
- **StockMap:** Volvo ca. oktober 2026, MSS "svagt begyndt at tippe op i grøn", vi rød kvadrant og pil ned (pilen rammer ved ±3 uger). Nvidia (grøn, pil ned) rammes.
- **Regressionskanal:** Vestas 2024-11-12 (MSS brud op, vi under), DSV 2024-03-31 (MSS skud op, vi inde), Genmab 2019 (MSS brud op, vi inde), Ørsted 2021 (MSS brud ned, vi inde), Pandora 2021-11 (MSS brud ned, vi over). Dagskanal 126 dage og ugekanal 52 uger, 2 sigma, er gæt; MSS' vindue kendes ikke.
- **Værdikanal:** Royal Unibrew 2026-03-04 (MSS "blå zone = billig", vores P/E 19,3 i den dyre ende af kanalen), Nvidia 2026-03-04 ("nederste halvdel = billig", vores P/E 62 over egen median), Mattel 2024-10-29 (MSS billig; vores P/E 33 mod en faktisk P/E på ca. 12–13, sandsynligvis datafejl i EPS-historikken, ikke modelfejl), Novo 2026-03-04 ("dyr zone ved toppen" beskriver tidligere top, mens vores P/E var 10,7).
- **Quality:** Amazon 2026-01-21, MSS 99, vores 37. Novo ligger systematisk 12–13 point under MSS' 99–100 (loftseffekt i percentilerne).

## Numeriske sammenligninger

- **P/E nu** (n = 8): median vores/MSS 1,03, 6 af 8 inden for ±25 %, rangkorrelation 0,37. Største afvigelser: FL Smith 2024-03 (MSS 18, vores 39,6), Genmab 2024-03 (MSS 48, vores 32,3), Amazon 2026-01 (MSS 35,5, vores 41,8). MSS bruger tilsyneladende ikke trailing P/E på årsregnskab hele tiden (forward eller TTM), så en løs overensstemmelse er forventelig.
- **P/E-gennemsnit 3/5/10 år:** 0 sammenlignelige; yfinance giver kun ca. 4 års regnskaber uden for USA, så historikken er for kort.
- **Quality-percentil (løst):** n = 13, rangkorrelation 0,53, gns. afvigelse 13 point. Vores tal er dagens `universe_factors` (rangeret pr. region), MSS' er fra videoens dato, så det kan kun læses som styrken af sammenhængen. Tidligere kalibrering (`quality_rank.py`: 115 høstede scorer) gav 0,73; 0,53 på 13 punkter med mange gentagelser af Novo er ikke i strid med det. Value-score har kun tekstudsagn i facitlisten ("lidt nede", "ikke særlig høj"), ingen tal.

## Hvad vi ikke kan teste, og hvorfor

- StockMap-industrigruppe, sektor og land (kræver sektor-/landeindeks, ingen i vores modul), "dag"-tilstande i TPI (TPI-lite har kun ugeniveau), swing-signaler og porteføljeafkast, samt alle rækker uden dato (de fleste af de 1180).
- Værdikanalens analytikerscenarier (bear/base/bull-procenter): analytikertal findes kun for i dag.

## Anbefalinger

1. **Behold TPI-lite lang trend og MTI-lite uændret.** De stemmer med MSS i det omfang facitlisten kan måle det.
2. **Rør ikke StockMap-parametrene ud fra B-15.** To rækker er ikke et grundlag. Brug i stedet `data/mss_observations.csv` (vinkler) og `mss_signal_observations.csv`, og tilføj nye datoerede StockMap-aflæsninger (ticker, dato, kvadrant, pil) til facitlisten.
3. **Regressionskanal:** hvis kanalen skal ligne MSS' brud, skal vindue og sigma afprøves (63/126/252 dage, ugekanal) mod en lille, ny og renset liste med datoerede brud. Nuværende 126 dage og 2 sigma rammer ikke bruddene.
4. **Værdikanal:** den kan ikke kalibreres historisk uden længere EPS-historik uden for USA. Gem fremover et ugentligt snapshot af `universe_factors.csv` og værdikanalens input, så næste kalibrering er point-in-time (også for Quality-percentiler).
5. **Facitlisten:** hver observation bør have ISO-dato, ticker og én kategorisk tilstand (kvadrant, pil, grøn/rød, billig/dyr). Det ville gøre n 5–10 gange større end de cirka 60 sammenligninger her.
6. **Datakvalitet:** Mattel-P/E (33 mod faktisk ca. 12–13) tyder på fejl i EPS-udtrækket for nogle amerikanske aktier; bør undersøges i `valuation.fetch_inputs`, før værdikanal-tal bruges som facit.

## Kørsel

```
.venv/Scripts/python scripts/calibrate_b15.py            # henter og cacher kurser i data/cache_b15
.venv/Scripts/python scripts/calibrate_b15.py --ingen-net  # kun cache
.venv/Scripts/python -m unittest tests.test_calibration
```
