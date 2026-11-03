# B-10: De fire algostrategier (MSS) – resultat 2026-11-03

Historisk test og papirsporing, IKKE en købsanbefaling.

## Hvad der er bygget

- `stockscanner/strategies.py`: rene rangeringsfunktioner (top 15, eller 5) fra universets faktortabel
  (`universe.percentiles` + TPI-lite-tilstand). Vores tolkning af MSS' korte beskrivelse, ikke deres formel:
  - Quality Momentum: gennemsnit af quality- og momentum-percentil.
  - TPI Plus: quality ≥ 60, TPI-lite oversolgt og lang trend grøn, rangeret efter quality (kan give under 15).
  - Value Momentum: (100 − value + momentum) / 2, dvs. LAV value-score og høj momentum ("omvendt value").
  - Value Quality: gennemsnit af value- og quality-percentil.
- `scripts/study_b10.py`: bagtest af de prisbaserede dele. `scripts/strategies_monthly.py`: månedlig papirsporing.
- `tests/test_strategies.py`: 9 offline tests (hele suiten: 262 grønne).

## Hvad kan bagtestes ærligt

Kun de prisbaserede dele. Quality og Value kræver regnskaber, som de var dengang (point-in-time); vi har kun
dagens regnskaber, så en bagtest af Quality Momentum, Value Momentum og Value Quality ville bruge fremtidig
viden (look-ahead) og vises derfor IKKE. Det samme gælder TPI Plus' quality-led. Testet er:

1. Momentum alene (percentil af 1/3/6/12-måneders afkast + stabilitet, som `scores.momentum_factors`), som
   stand-in for den momentum-halvdel, de tre momentum-strategier deler.
2. TPI-lite "oversolgt i lang optrend" alene, som stand-in for TPI Plus uden quality.

Opsætning: første handelsdag hver måned, signal kun fra lukkekurser til og med dagen før, køb til åbningskurs,
lige vægt, udskiftning hver måned, 1,5 %/år omkostninger (0,125 %/md, MSS' tal), benchmark RSP. Univers
`data/universe.txt`: 295 af 316 aktier med nok historik (USA, Norden, Europa), 15 års data, 167 måneder
(nov. 2011 – nov. 2026). Udvikling til 2024-10-31 (143 md), urørt fra 2024-11-01 (24 md).

## Tal (CAGR, maks. drawdown; RSP = benchmark samme periode)

| Strategi (top 15) | Udvikling | Urørt | Hele |
|---|---|---|---|
| Momentum (kurs) | 24,23 %, DD −20 % | 24,20 %, DD −22 % | 24,22 %, DD −22 % |
| TPI-lite oversolgt + lang grøn | 9,5 %, DD −24 % | 16,8 %, DD −12 % | 10,5 %, DD −24 % |
| Lige vægtet univers (uden omkostn.) | 17,9 % | 16,1 % | 17,6 % |
| RSP | 12,6 % | 13,2 % | 12,7 % |

De tre momentum-tal er næsten ens (24,23 / 24,20 / 24,22 %), men er kontrolleret: udsnittene er forskellige (143, 24 og 167 måneder), og TPI-lite- og RSP-rækkerne varierer som forventet. Det er et tilfælde, ikke en fejl; i den urørte periode er maks. DD og sejrsandel (50 % mod 57 %) forskellige. En test i `tests/test_strategies.py` låser CAGR pr. periode.

Momentum slår RSP i 56 % af månederne (urørt 50 %); udskiftning ca. 62 %/md. TPI-lite-varianten har i snit kun
11 valg og 14 måneder uden et eneste valg (kontanter), udskiftning ca. 93 %/md, og slår RSP i 47 % af månederne.

Med 5 aktier i stedet for 15: momentum 16,7 % (udvikling) / 30,8 % (urørt) / 18,7 % (hele), maks. DD −34 %;
TPI-lite 9,9 % / −6,5 % / 7,4 %. Altså meget større udsving og ingen robust forskel – 5 stk. er mest støj.

## Ærlig konklusion

- Momentum alene gav ca. 24 %/år mod RSP 12,7 % – i samme størrelsesorden som MSS' backtest (ca. 20 %/år),
  og det holdt i den urørte periode (24,2 %). Men en stor del skyldes UNIVERSET: lige vægtet univers giver
  17,6 % mod RSP 12,7 %, fordi universet kun består af aktier, der findes i dag (overlevelsesbias), er
  småcap-tungt (mange danske) og aldrig har haft aktier, der blev slettet fra børsen. Momentums egen
  merværdi ligger derfor på ca. 6–7 point over det lige vægtede univers, ikke 11 point over RSP.
- Ingen valutaomregning (afkast i lokal valuta) og 21 aktier manglede data. Omkostninger er en flad
  1,5 %/år, ikke udskiftningsbaseret; med ca. 60 % månedlig udskiftning kan faktiske omkostninger i små
  papirer blive højere.
- TPI-lite oversolgt+lang grøn alene var i udviklingsperioden svagere end RSP (9,5 % mod 12,6 %) og
  kun bedre i den korte urørte periode (24 mdr., 16,8 %); top 5 gav −6,5 % i den urørte periode. Vores
  bud på TPI er altså ikke bevist som selvstændig strategi; i TPI Plus er det quality, der skal bære den,
  og det kan ikke testes bagud.
- De fire MSS-strategier som helhed kan IKKE valideres eller afvises ud fra disse tal. MSS' YTD-tal
  (QM 15,1 %, TPI+ 22,1 %, VM 14 %, VQ 20,5 % mod RSP 15,3 %) er deres egne, urevisionerede og for én periode.

## Fremadrettet sporing (det eneste ærlige test af quality/value)

`scripts/strategies_monthly.py` køres første handelsdag hver måned: rangerer universet (`universe.load()`,
kræver cache under 14 dage), tilføjer månedens valg og indgangskurs (seneste lukkekurs) til
`data/strategier/<strategi>.csv` (semikolon; `RSP_indgang.csv` gemmer RSP-kursen ved hver måneds start) og
viser afkast pr. valgmåned mod RSP. Idempotent pr. måned. Første kørsel 2026-11-03:

- Quality Momentum: 15 aktier (CTAS, MO, V, MA, LLY …), Value Momentum: 15, Value Quality: 15 (mange danske
  småcap/value-navne), TPI Plus: kun 9 (ASML, MU, NVDA, AMD, CSCO …), fordi få aktier samtidig er
  oversolgte, i lang optrend og har quality ≥ 60.
- Kort sagt: efter 12 månedlige kørsler kan man se, om hver strategi slår RSP uden look-ahead. Først efter
  mindst 2–3 år og flere end én markedstype siger det noget. Salg sker ved næste månedsskifte (ikke
  indbygget i scriptet: afkast måles pr. valgmåned, lige vægt, uden omkostninger – træk ca. 1,5 %/år fra).
- Tolkningsforbehold: universets faktorer er en 316-aktiers cache, ikke MSS' fulde region; percentiler
  rangeres mod hele universet (ikke pr. region). Rangeringerne er vores gæt på MSS' regler.

Kør igen: `.venv/Scripts/python scripts/study_b10.py [--n 5]` (cache i `data/cache_b10`).
