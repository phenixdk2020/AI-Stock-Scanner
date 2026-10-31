# AI-Stock-Scanner V1

En **lokal, dansk aktiescanner** bygget i Python med Streamlit-dashboard, historiske kurser fra yfinance, teknisk score, SQLite-historik og valgfri lokal Ollama-analyse.

**Ingen betalte API-nøgler er nødvendige.** Projektet udfører **ikke** automatisk handel og giver ikke personlige investeringsanbefalinger.

## Funktioner

- Danmark og udlandet, eksempelvis NOVO-B.CO, DSV.CO, VWS.CO, MSFT, NVDA, AAPL.
- 0–100-point teknisk score baseret på SMA50/200, RSI14, MACD, 21-dages kursudvikling og volumen.
- Dansk dashboard med graf, watchlist, eksport til semikolonsepareret CSV og forklaring af indikatorerne.
- Gemmer scanninger i lokal SQLite-database under data/scans.sqlite3.
- Kommandolinjeværktøj til scanninger via Windows Opgavestyring.
- Valgfri dansk AI-forklaring gennem Ollama på localhost:11434.
- Offline enhedstests med syntetiske kursdata.

## Installation (Windows PowerShell)

Forudsætning: **Python 3.11 eller nyere**. Kør fra projektmappen:

~~~powershell
git clone https://github.com/phenixdk2020/AI-Stock-Scanner.git
cd AI-Stock-Scanner
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
~~~

Åbn adressen, som Streamlit viser (normalt http://localhost:8501).

Hvis PowerShell blokerer aktivering af virtuelt miljø, kan du undlade Activate.ps1 og i stedet bruge:

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
~~~

## Kommandolinje og planlagt scanning

~~~powershell
.\.venv\Scripts\python.exe scan_cli.py --tickers "NOVO-B.CO,DSV.CO,MSFT,NVDA" --csv data\latest.csv
~~~

Argumentet --tickers er valgfrit; uden dette bruges den gemte watchlist eller standardsymbolerne. Exitcode 0 betyder mindst én vellykket scanning, 1 betyder ingen vellykkede scanninger og 2 betyder ugyldig tickerliste. Fejl for enkelte aktier vises i JSON-output.

Du kan oprette en **daglig opgave i Windows Opgavestyring** med programmet fra .venv\Scripts\python.exe, argumenterne fra kommandoen ovenfor og projektmappen som Start i. Der oprettes ikke en betalt GitHub Actions-workflow eller anden cloud-tjeneste.

## Ollama (valgfri)

Installer og start Ollama lokalt, og sørg for at en model er hentet. Dashboardet bruger som standard qwen3.5:9b, men du kan vælge enhver installeret model. AI-funktionen sender kun resultatet af den valgte scanning til http://127.0.0.1:11434/api/generate; ingen betalt ekstern AI-API.

## Tests

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

Testene bruger ingen markeds-API og kan køres uden internet, når pakkerne er installeret.

## Scoreregler

| Indikator | Point |
|---|---:|
| Sidste kurs over SMA50 | 20 |
| SMA50 over SMA200 | 20 |
| RSI14 mellem 45 og 70 | 20 |
| MACD over signallinjen | 20 |
| Positiv kursudvikling over 21 handelsdage | 10 |
| Dagens volumen mindst gennemsnittet af de seneste 20 dage | 10 |
| **Maksimum** | **100** |

80–100 = Interessant, 60–79 = Hold øje, 0–59 = Afvent.

Score er blot en **gennemsigtig teknisk filtermodel**, ikke en sandsynlighed eller et bevis på undervurdering. Der er ingen fundamental analyse, backtest, nyhedsdata eller realtidsgaranti i V1.

## Datakilder og forbehold

yfinance er en **uofficiel** integration til Yahoo Finance. Historiske data kan være forsinkede, forkert justerede, utilgængelige eller begrænset af udbyderen. Respektér datakildens vilkår; denne løsning er tænkt til **privat research**, ikke redistribuering eller kommerciel realtime-markedsdata. yfinance kan ændre API, så datakilder bør isoleres i stockscanner/market_data.py.

Daglige scanninger viser **justerede** lukkekurser, som kan afvige fra de ikke-justerede børskurser. Databasen opbevares kun lokalt og ignoreres af Git. Der foretages ingen automatiske køb eller salg.

## Projektstruktur

- app.py: Streamlit-webdashboard.
- scan_cli.py: batchscanning, JSON-output og CSV-eksport.
- stockscanner/core.py: indikatorer, scoring og validering.
- stockscanner/market_data.py: dataadapter til yfinance.
- stockscanner/storage.py: SQLite og watchlist.
- stockscanner/ollama.py: valgfri lokal AI-forklaring.
- tests/: offline enhedstests.

## Plan for næste version

Fundamental analyse, udvidede filtre, dataadapter til flere børser og udbydere, egentlige alarmer og backtest med transaktionsomkostninger. Ingen af disse V2-funktioner er implementeret i V1.
