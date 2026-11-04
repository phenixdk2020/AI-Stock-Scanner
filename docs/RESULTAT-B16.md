# B-16: TPI fuld metode (analog) mod TPI-lite – resultat

Dato: 2026-11-03. Kode: `stockscanner/tpi_analog.py`, `scripts/study_b16.py`, `tests/test_tpi_analog.py`. Historisk test, IKKE en købsanbefaling.

## Metode

- **Analog:** hver uge beskrives af seks tal fra aktiens egne ugekurser (4-/13-/26-ugers afkast, afstand til 40-ugers gennemsnit, gennemsnittets hældning over 10 uger, volatilitet over 13 uger), skaleret med fortidens spredning. De k=20 mest ligne uger i samme aktie, hvis udfald (4 uger frem) var afsluttet før nu, giver scoren = deres gennemsnitlige afkast. Min. 80 analoger. Ingen fremtid i scoren (testet: ændrede fremtidskurser flytter ikke tidligere scorer).
- **Tilstand:** scorens percentil i aktiens egne seneste 260 scorer: top 20 % = oversolgt, bund 20 % = overkøbt, resten neutral. Lang trend grøn = den samme som i TPI-lite. Parametre (k, funktioner, tærskler) er valgt på forhånd og IKKE tunet.
- **Sammenligning:** 277 aktier fra `data/universe.txt` (20 års historik, 18 uden kursdata udeladt), samme (aktie, uge)-mængde for begge (2010-05 – 2026-10, 222.104 aktie-uger). Signal ved ugens lukning, køb næste dags åbning, 0,1 % pr. vej. Udvikling = signal og udfald før 2024-11-01; urørt = signaler fra 2024-11-01. MSS-reglen: lang grøn + oversolgt, hold 130 handelsdage.

## Resultater (afkast i %, efter omkostninger)

Alle uger: 5/20/65/130 d = 0,15 / 1,09 / 3,87 / 8,15 (udvikling) og 0,19 / 1,14 / 4,33 / 9,95 (urørt).

| MSS-regel (lang grøn + oversolgt, 130 d) | TPI-lite | TPI-analog |
|---|---:|---:|
| Udvikling: n / snit / median / andel positiv | 11.623 / 9,05 / 7,25 / 67,0 % | 18.072 / 8,90 / 6,17 / 64,1 % |
| Udvikling: merafkast mod alle uger | +0,91 | +0,75 |
| Urørt: n / snit / median / andel positiv | 1.490 / 13,75 / 11,04 / 71,3 % | 2.331 / 12,18 / 8,81 / 66,2 % |
| Urørt: merafkast mod alle uger | +3,81 | +2,23 |
| Urørt: merafkast mod "lang grøn" alene | +2,14 | +0,57 |

Rang-IC (oversolgthed mod senere afkast, samlet over aktier):

| Periode | Model | 5 d | 20 d | 65 d | 130 d |
|---|---|---:|---:|---:|---:|
| Udvikling | lite | 0,018 | 0,034 | 0,016 | 0,013 |
| Udvikling | analog | 0,004 | 0,008 | 0,008 | 0,011 |
| Urørt | lite | 0,020 | 0,045 | 0,053 | 0,031 |
| Urørt | analog | 0,001 | 0,012 | 0,028 | 0,035 |

Grupper, urørt (130 d): lite lang grøn/oversolgt 13,75 mod lang grøn/overkøbt 11,90 og lang rød/neutral 6,63; analog lang grøn/oversolgt 12,18 mod lang grøn/neutral 11,69 og overkøbt 10,59. Kortere horisonter (5/20 d) viser i begge modeller kun få tiendedele procent forskel mellem grupperne. Fulde tabeller: kør `scripts/study_b16.py`.

## Konklusion (ærlig)

1. **Analog slår ikke TPI-lite udenfor stikprøve.** Reglen giver lidt lavere afkast (12,2 mod 13,8 %), mindre merafkast mod lang grøn alene (+0,6 mod +2,1 point), og scoren har lavere rang-IC på 5–65 d (næsten nul). Kun ved 130 d er analog marginalt over (0,035 mod 0,031) – inden for støj.
2. **Edge er svag i begge.** Næsten hele reglens afkast kommer fra "lang grøn" (trend), ikke fra oversolgt-delen. Merafkast mod alle uger i udviklingsperioden er under 1 point på 130 d for begge. MSS' "0,9 % pr. 5 dage" findes ikke her (0,2–0,3 %).
3. **Forbehold:** (a) urørt periode er kun ca. to år i et stærkt marked, og kun 79 forskellige signaluger, så de mange observationer er stærkt overlappende og korrelerede på tværs af aktier – ingen signifikanstest er lavet; (b) universet er nutidens tickers (overlevelsesbias), hvilket løfter alle tal ens; (c) analog bruger kun ugekurser og seks funktioner, k=20; en anden opsætning kunne give andet, men en søgning her ville bruge den urørte periode op; (d) dags-rækken i TPI er ikke bygget.
4. **Anbefaling: erstat IKKE TPI-lite med analog.** Analogen er dyrere (kører minutter pr. univers), mere uigennemsigtig og viser ingen forbedring. Behold TPI-lite som et svagt trendfilter; lad B-16 lukke som "ingen gevinst". Genåbn kun hvis der kommer flere MSS-observationer (TPI-farver på kendte datoer) at kalibrere mod.
