# Resultat B-07 og B-11: sektorbekræftelse af StockMap og MTI sektor-del

Kørt 03-11-2026 med `scripts/study_b07_b11.py` (kode: `stockscanner/sector_rs.py`, tests: `tests/test_sector_rs.py`, 9 grønne). Historisk test, IKKE en købsanbefaling. Ikke koblet på CLI eller hjemmeside.

## Metode
- Univers: `data/universe.txt` (316 tickere, 295 med kendt sektor og hentbare kurser; 17 uden sektor, bl.a. ETF'er, og ca. 18 ikke hentbare, fx ATLA.CO). 15 års dagskurser, 0,1 % pr. side i omkostning, urørt periode fra 2024-11-01 (købsdato), resten er udvikling.
- Køb: MSS-lignende StockMap simpelt køb mod RSP (som `exits.stockmap_entries`), samme `simulate()`/`summarize()` som øvrige studier; fire salgsregler (StockMap, Supertrend x3, SMA50, Fast 60 dage). Overlap mellem handler er tilladt som i de øvrige studier.
- **B-07 (sektor op):** aktiens sektor-ETF's StockMap-pil (samme `points_up`-regel, samme parametre) peger op ved signalugen, mod RSP (USA) eller STOXX Europe 600 `EXSA.DE` (Europa/Norden).
- **B-11 (MTI-sektor grøn):** aktie / sektor-ETF over EMA20 (dag) og EMA10 (uge) samtidig, samme logik som `mti_lite.mti_state`, men som tidsserie så det kan slås op på signaldagen (test viser identisk resultat med `mti_state` ved ugens slutning). `mti_lite` er uændret.
- Sektorkort: `info['sector']`/`['industry']` fra yfinance, cachet i `data/sector_map.json`. USA: SPDR XLK/XLF/XLV/XLY/XLP/XLE/XLI/XLB/XLU/XLRE/XLC.
- **Europa: der findes et brugbart gratis sæt.** iShares STOXX Europe 600-sektor-ETF'er på XETRA (EXV1.DE banker, EXV3.DE tech, EXH1.DE olie/gas, EXV4.DE sundhed, EXH4.DE industri, EXV6.DE råstoffer, EXV5.DE biler, EXH3.DE mad/drikke, EXH7.DE personlig/husholdning, EXV7.DE kemi, EXH9.DE forsyning, EXV8.DE byggeri, EXH5.DE forsikring, EXH6.DE medier, EXV2.DE telekom, EXH8.DE detail, EXI5.DE ejendom) plus EXSA.DE som bred benchmark. Alle 18 serier verificeret med 15 års data. Det er derfor ikke US-ETF'er som proxy for Europa. Begrænsninger: Yahoos GICS-lignende sektorer matches grovt mod ICB-ETF'erne (kapitalforvaltere ender under banker, forbrugsvarer fordeles ud fra branchenøgleord); ETF'erne er i EUR mens aktierne er i DKK/SEK/NOK/CHF/GBP, så valuta smitter ind i den relative styrke (som den også gør mod hjemmeindeks).
- Alle varianter sammenlignes på samme grundlag (21.421 af 21.787 køb hvor begge sektorsignaler kan beregnes), så XLRE/XLC's korte historik ikke forskyder noget.

## Resultater (StockMap-køb, 295 aktier)
Andel af køb: sektor op 58 %, MTI-sektor grøn 29 %, begge 15 %.

Snit % pr. handel / win % / profit factor:

| Periode | Variant | Handler | StockMap-salg | Supertrend x3 | SMA50 | Fast 60 dage |
|---|---|---|---|---|---|---|
| Udvikling | uden filter | 17.979 | 5,5 / 58 / 2,33 | 3,8 / 49 / 2,11 | 2,4 / 47 / 1,97 | 3,6 / 58 / 1,91 |
| Udvikling | sektor op | 10.502 | 5,6 / 59 / 2,45 | 3,6 / 50 / 2,13 | 2,0 / 47 / 1,88 | 3,6 / 59 / 1,97 |
| Udvikling | MTI-sektor grøn | 5.281 | 5,8 / 59 / 2,69 | 3,2 / 46 / 2,11 | 2,0 / 41 / 1,96 | 4,2 / 60 / 2,28 |
| Udvikling | begge | 2.852 | 5,4 / 59 / 2,56 | 2,8 / 45 / 1,95 | 1,8 / 40 / 1,80 | 3,8 / 59 / 2,13 |
| Urørt | uden filter | 2.831 | 4,3 / 55 / 2,01 | 2,7 / 47 / 1,70 | 1,6 / 48 / 1,62 | 4,1 / 57 / 1,94 |
| Urørt | sektor op | 1.568 | 4,9 / 55 / 2,20 | 3,3 / 47 / 1,89 | 1,9 / 49 / 1,79 | 4,3 / 58 / 2,04 |
| Urørt | MTI-sektor grøn | 733 | 3,4 / 51 / 1,79 | 2,4 / 42 / 1,63 | 1,2 / 38 / 1,48 | 5,1 / 59 / 2,34 |
| Urørt | begge | 358 | 3,6 / 49 / 1,80 | 3,2 / 42 / 1,81 | 1,5 / 38 / 1,58 | 5,8 / 59 / 2,55 |

(Handlerantal i urørt pr. regel varierer lidt, fx 3.070 for Supertrend; tallet i tabellen er StockMap-reglens. Fuld tabel med median, dage, %/100d og værste 5 % er i scriptets output.)

Forskel i snit % mellem bekræftede og afviste køb (Welch-t; handler overlapper og er klyngede, så t overdriver signifikansen):

| Filter | Periode | StockMap-salg | Supertrend x3 | SMA50 | Fast 60 dage |
|---|---|---|---|---|---|
| Sektor op | Udvikling | +0,4 (t 0,9) | -0,5 (t -1,1) | -0,8 (t -2,1) | +0,2 (t 0,6) |
| Sektor op | Urørt | +1,4 (t 1,6) | +1,4 (t 2,1) | +0,6 (t 1,5) | +0,3 (t 0,5) |
| MTI-sektor grøn | Udvikling | +0,4 (t 1,0) | -0,8 (t -2,3) | -0,5 (t -1,5) | +0,9 (t 2,9) |
| MTI-sektor grøn | Urørt | -1,2 (t -1,3) | -0,4 (t -0,6) | -0,5 (t -1,0) | +1,3 (t 1,6) |

## Konklusion
- **B-07 (sektorbekræftelse): ikke overbevisende.** Filtret fjerner 42 % af købene, men gevinsten pr. handel (StockMap-salg) ændrer sig kun fra 5,5 til 5,6 % i udviklingsperioden og fra 4,3 til 4,9 % i urørt. Retningen er positiv for StockMap-salgsreglen i begge perioder, men størrelsen er inden for støjen (t under 2 med optimistisk t), og for SMA50 og Supertrend er den negativ i udvikling og positiv i urørt. Det harmonerer med MSS' egen udtalelse (QTS 0:53:01-0:53:15) om at sektorretning næsten ingen effekt har på rene købssignaler. Win-rate og profit factor løftes en anelse (PF 2,33 til 2,45; 2,01 til 2,20), men på et mindre antal handler.
- **B-11 (MTI sektor grøn): inkonsistent, anbefales ikke som filter.** Med StockMap-salg giver det +0,4 i udvikling og -1,2 i urørt; med Supertrend og SMA50 er tegnet negativt i begge perioder. Kun "Fast 60 dage" er positiv i begge (+0,9 og +1,3), og der halverer filteret kun antal handler uden at ændre vinderrate meget. Det er en tidsmæssig momentum-effekt (aktier der allerede løber fra sektoren), ikke en bekræftelse af StockMap-signalet. "Begge" er værre end hver for sig i urørt for StockMap-salg (win 49 %).
- **Risikoprofil:** MTI-sektor grøn forbedrer konsekvent "Værste 5 %" (fx -29,9 til -24,8 i udvikling for StockMap-salg, -21,2 til -14,1 for Supertrend), altså lidt færre dybe tab, men også lavere holdetid i SMA/Supertrend-reglerne (flere hurtige udgange). Det er den mest robuste observation, men ikke et afkastløft.
- **Anbefaling:** brug det ikke som hårdt krav i listen eller på siden. Hvis sektoren vises, så som information (sektor-ETF's pil og om aktien er dobbelt grøn mod sektoren) uden at filtrere køb væk. Sektor op kan evt. vises som en ekstra "medvind"-markering, som MSS selv kalder en tendens, men beviset her er svagt. Ingen ændring i `playbook.py`/`scan_cli.py` foreslås på dette grundlag.

## Forbehold
- Universet er nutidens aktier (overlevelsesbias), mest danske (154 af 316) og dermed mange små/ikke-likvide navne; europæisk sektormapping er grov, og EUR/lokal valuta forurener den relative styrke.
- StockMap-køb uden positionstilstand giver mange overlappende, korrelerede handler (ca. 74 pr. aktie over 15 år), så t-værdier er for optimistiske og de reelle usikkerheder større end vist.
- Urørt periode (fra 2024-11-01) har kun 2,8 tusind handler og er markedsmæssigt én regime; forskelle på 1 point er ikke at skelne fra tilfældighed.
- Parametre er ikke tunet til denne test (standard StockMap, EMA20/10); ingen kalibrering blev forsøgt for at undgå overfit.
- Ikke testet: sektorfilter på handelsniveau pr. land, og sektorens kvadrant (kun pilens retning).
