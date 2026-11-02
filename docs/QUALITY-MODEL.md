# Kvalitetsmodel (fase 1–2)

Vores **egen**, gennemsigtige kvalitetsscore for aktier, bygget på offentligt kendt finansteori
(ROIC, Piotroski F-score, Altman Z m.fl.). Den er **ikke** en kopi af MyStockScanners score og
**ikke** ensbetydende med den: deres formler er ikke offentlige, og vi påstår ingen lighed.
Scoren er en **screening, ikke en købsanbefaling eller investeringsrådgivning**.

Kode: `stockscanner/fundamentals.py` (hentning, normalisering) og `stockscanner/quality.py` (model).

```powershell
.\.venv\Scripts\python.exe scan_cli.py --kvalitet --tickers NOVO-B.CO,MSFT
```

I Streamlit-appen: vælg en aktie under "Detaljer" og klik på **Hent regnskabstal og beregn kvalitet**.

## Data

- Kilde: `yfinance` (uofficiel Yahoo Finance-integration): årsregnskab (resultat, balance, cashflow) og `info`.
- Normaliseres til regnskabsår (nyeste først) med 21 standardfelter. yfinance-rækkelabels varierer, så hvert
  felt har flere kandidatlabels (tabellen `LABELS` i koden). Investeringer (capex) gemmes som negativt tal;
  fri cashflow = driftscashflow + capex, hvis den ikke er oplyst. EBIT afledes kun af resultat før skat +
  renteudgifter, hvis begge findes.
- **Manglende data forbliver `None`** og vises som "mangler". Der opfindes aldrig regnskabstal. Den eneste antagelse i modellen er skattesatsen i ROIC: kan den effektive sats ikke beregnes (skat eller resultat før skat mangler, eller resultat før skat ≤ 0), bruges **22 %**, og det fremgår af begrundelsen.
- Aktieantal hentes kun fra balancen ("Ordinary Shares Number", ellers "Share Issued"); der er ingen reserve fra resultatopgørelsen. Hvilken label der blev brugt, gemmes pr. år, og aktieudstedelse sammenlignes kun, når begge år har samme label.
- Cache: SQLite-tabellen `fundamentals` (en række pr. symbol, standard 7 dage). `scans`-tabellen er uændret.

## Målinger og formler

Alle på nyeste regnskabsår, medmindre andet er angivet. Balancestørrelser er ultimo år (ikke gennemsnit).

| Måling | Formel |
|---|---|
| ROIC | NOPAT / (gæld + egenkapital − kontanter); NOPAT = EBIT × (1 − skattesats). Skattesats = skat / resultat før skat, klemt til 0–35 %; hvis den ikke kan beregnes, **antages 22 %** |
| ROE | Resultat / egenkapital (egenkapital skal være > 0) |
| ROA | Resultat / aktiver |
| ROCE | EBIT / (aktiver − kortfristet gæld) |
| Bruttomargin | Bruttoresultat / omsætning |
| Driftsmargin | Driftsresultat (ellers EBIT) / omsætning |
| Driftsmargin-stabilitet | Standardafvigelse (stikprøve) af driftsmargin over de tilgængelige år; **kræver ≥ 3 år** |
| Omsætningsvækst | CAGR fra ældste til nyeste år med omsætning, over det **faktisk forløbne antal år** ud fra regnskabsdatoerne ((nyeste − ældste dato) / 365,25), så huller i data ikke forvrider tallet; **kræver ≥ 3 år med omsætning** |
| FCF-margin | Fri cashflow / omsætning |
| Cash conversion | Fri cashflow / resultat (kun hvis resultat > 0) |
| Likviditetsgrad | Omsætningsaktiver / kortfristet gæld |
| Nettogæld / EBITDA | (Gæld − kontanter) / EBITDA. EBITDA ≤ 0: score 100 ved nettokasse, ellers 0 |
| Rentedækning | EBIT / \|renteudgifter\|. Renteudgifter = 0 giver 100 |
| Piotroski F-score | 9 standardtests mellem nyeste og forrige år (se nedenfor); **kræver 2 år** |
| Altman Z | Original 1968-formel: 1,2·AK/A + 1,4·OR/A + 3,3·EBIT/A + 0,6·Markedsværdi/Gæld + 1,0·Omsætning/A |

**Piotroski** (1 point pr. bestået test, nyeste år Y0, forrige Y1, ældste Y2, ultimoaktiver A). Standardformer:

| # | Test | Kræver |
|---|---|---|
| 1 | ROA > 0, hvor ROA = resultat(Y0) / A(Y1) (aktiver ved årets **start**) | 2 år |
| 2 | Driftscashflow(Y0) > 0 | 1 år |
| 3 | ROA steget: ROA(Y0) > ROA(Y1), hvor ROA(Y1) = resultat(Y1) / A(Y2) | **3 år** |
| 4 | Driftscashflow > resultat (Y0) | 1 år |
| 5 | Langfristet gæld / gennemsnitlige aktiver faldet (Y0 mod Y1; gns. = (A slut + A start)/2) | **3 år** |
| 6 | Likviditetsgrad steget (Y0 mod Y1) | 2 år |
| 7 | Ingen stigning i aktieantal (Y0 ≤ Y1), kun hvis begge år har aktieantal fra **samme** label | 2 år |
| 8 | Bruttomargin steget (Y0 mod Y1) | 2 år |
| 9 | Aktivomsætning steget: omsætning(Y0)/A(Y1) > omsætning(Y1)/A(Y2) | **3 år** |

En test uden fuldt datagrundlag er **ikke beregnelig** (springes over, tæller hverken som bestået eller dumpet).
Med kun 2 regnskabsår kan test 3, 5 og 9 altså ikke køre. Score = beståede / beregnelige × 100 og kræver mindst
5 beregnelige tests; begrundelsen i appen/CLI angiver hvilke tests der bestod og hvilke der ikke var beregnelige.
Langfristet gæld hentes fra "Long Term Debt" / "Long Term Debt And Capital Lease Obligation".

**Altman Z** bruger *aktuel* markedsværdi (`marketCap`) som egenkapitalværdi, mod totale forpligtelser. Springes over
hvis kursvaluta og regnskabsvaluta er forskellige (så er tallene ikke sammenlignelige) og for finansielle selskaber.
Zoner (Altman): < 1,81 nødlidende, 1,81–2,99 gråzone, > 2,99 sikker.

## Tærskler (point 0–100, lineær interpolation, klemt ved yderpunkterne)

| Måling | (værdi → point) |
|---|---|
| ROIC | 0 % → 0, 10 % → 50, 25 % → 80, 40 % → 100 |
| ROE | 0 % → 0, 12 % → 50, 30 % → 80, 50 % → 100 |
| ROA | 0 % → 0, 5 % → 50, 12 % → 80, 20 % → 100 |
| ROCE | 0 % → 0, 12 % → 50, 30 % → 80, 50 % → 100 |
| Bruttomargin | 10 % → 0, 35 % → 50, 60 % → 80, 80 % → 100 |
| Driftsmargin | 0 % → 0, 12 % → 50, 25 % → 80, 40 % → 100 |
| Margin-stabilitet (std.afv., lavere er bedre) | 2 pp → 100, 5 pp → 60, 10 pp → 30, 20 pp → 0 |
| Omsætningsvækst (CAGR) | −5 % → 0, 0 % → 30, 5 % → 60, 15 % → 100 |
| FCF-margin | 0 % → 0, 8 % → 50, 20 % → 100 |
| Cash conversion | 0 → 0, 0,8 → 50, 1,2 → 100 |
| Likviditetsgrad | 0,5 → 0, 1,0 → 40, 1,5 → 70, 2,5 → 100 |
| Nettogæld/EBITDA (lavere er bedre) | ≤ 0 → 100, 2 → 70, 3 → 50, 5 → 10, ≥ 7 → 0 |
| Rentedækning | 1 → 0, 3 → 40, 8 → 80, 15 → 100 |
| Altman Z | 1,0 → 0, 1,81 → 30, 2,99 → 70, 4,0 → 100 |
| Piotroski | beståede / beregnelige tests × 100 |

Lønsomhedstærsklerne har et ekstra trin (80 point) før 100, så fremragende ikke blot er det samme som god. Tærsklerne er konservative, **absolutte** valg truffet af os og kan justeres i `THRESHOLDS` i `quality.py`.

## Vægte (fire søjler)

| Søjle | Vægt | Målinger |
|---|---:|---|
| Lønsomhed | 35 | ROIC, ROE, ROA, ROCE, bruttomargin, driftsmargin |
| Stabilitet og vækst | 25 | Margin-stabilitet, omsætningsvækst |
| Cashflow | 20 | FCF-margin, cash conversion |
| Balance | 20 | Likviditetsgrad, nettogæld/EBITDA, rentedækning, Altman Z, Piotroski |

Søjlescore = gennemsnit af de tilgængelige målingers point. Samlet score = vægtet gennemsnit af de søjler, der har
data. Etiket: **≥ 80 Stærk, ≥ 60 God, ≥ 40 Middel, ellers Svag.**

## Dækningsregel

Hver søjles vægt fordeles ligeligt på søjlens *relevante* målinger. Dækning = den dækkede andel af vægten i de søjler, der har relevante målinger (en søjle uden relevante målinger udgår af både vægtning og dækning). **Under 60 % dækning er samlet score `None` med status "Utilstrækkelige data"**; målinger og
manglende felter vises stadig. Målinger der springes over fordi de ikke er relevante (finans) tæller ikke som mangler.

## Finansielle selskaber

Finans afgøres af **branchen (yfinance `industry`), ikke sektoren**: branchen skal starte med "Banks", "Insurance"
(dog ikke "Insurance Brokers"), "Capital Markets", "Asset Management", "Mortgage Finance" eller "Financial Conglomerates".
Fx har Visa sektor "Financial Services" men branchen "Credit Services" og får derfor den fulde model.
Finansielle selskaber markeres **"begrænset (finans)"**. ROIC, ROCE, bruttomargin, likviditetsgrad, nettogæld/EBITDA,
Altman Z, rentedækning (renter er bankens driftsomkostning), FCF-margin og cash conversion (cashflow er meningsløst
for banker) springes over. Modellen bygger her på ROE, ROA, driftsmargin, stabilitet, vækst og Piotroski. Søjlen
Cashflow har ingen relevante målinger og udgår af vægtningen.

## Begrænsninger

- yfinance giver typisk kun **ca. 4 årsregnskaber**; stabilitet og CAGR hviler derfor på få år.
- Kilden er **uofficiel**: tal kan mangle, være forsinkede, genudgivne eller have skiftende rækkelabels.
- **Nordiske small caps** har ofte ufuldstændige regnskaber, så dækningsreglen giver oftere "Utilstrækkelige data".
- Regnskabs- og kursvaluta kan være forskellige (fx ADR'er); Altman springes da over.
- Absolutte tærskler: ingen sammenligning med branche/peers – **sektorrelativ scoring er en senere fase**.
- Ingen værdiansættelse (P/E, EV/EBIT m.fl.) og ingen timing i denne fase.
- Ingen backtest af, om høj score har givet bedre afkast.

## Ikke investeringsrådgivning

Scoren er en regelbaseret screening ud fra historiske, uofficielle regnskabstal. Den er ikke en købs- eller
salgsanbefaling og ingen prognose for kursudviklingen.
