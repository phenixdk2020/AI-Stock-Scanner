# AI-Stock-Scanner V1

> **WordPress v0.3.0 – privat portefølje (2026-11-01):** [WordPress ZIP](dist/hangar18-ai-stock-scanner-v0.3.0.zip). Brug WordPress' almindelige login. Under **AI Stock Scanner → Oversigt** kan en administrator trykke **Opret porteføljeside og sæt som forside** (den eksisterende forside ændres kun ved dette klik). Den personlige portefølje lagrer hvert køb på den indloggede WordPress-bruger, inkl. antal, købskurs, dato og valuta; den viser aktuelt manuel kurs og gevinst/tab pr. valutatype. Flere køb af samme aktie understøttes. Automatisk Yahoo-kurshentning er **slået fra som standard** og kan aktiveres til begrænset privat afprøvning under **AI Stock Scanner → Forbindelse**. Det er en uofficiel integration; priserne kan være forsinkede, og datavilkår skal vurderes. Ingen afhængighed af, at den lokale PC kører. Alternativ shortcode: `[ai_stock_home]` eller `[ai_stock_portfolio]`. Undgå at bruge scannerens Application Password til almindeligt login.


> **Aktuel WordPress-version: v0.2.5.** Løser hosting-miljøer der fjerner HTTP `Authorization` ved at bruge en krypteret HTTPS-forbindelse med plugin-specifik reserveheader og WordPress' egen Application Password-verifikation. [Download v0.2.5 ZIP](dist/hangar18-ai-stock-scanner-v0.2.5.zip). Efter WordPress-opdatering: kør `git pull --ff-only` i `C:\AI-Stock-Scanner`, og test med `.\.venv\Scripts\python.exe -m stockscanner.site_sync --check-auth`. Hvis det virker, kan du sende demo med `--demo`. Ingen ændring af `.htaccess` er normalt nødvendig. Hvis webhotellet også fjerner den ekstra header, skal proxyen dog rettes hos webhotellet.


> **Aktuel WordPress-plugin: v0.2.2.** Efter repositoryet blev gjort offentligt, er GitHub-opdatering **tokenfri**. Den defekte v0.2.0 ZIP må ikke bruges. [Download v0.2.2](dist/hangar18-ai-stock-scanner-v0.2.2.zip) og se [den opdaterede installationsvejledning](docs/WORDPRESS-GITHUB-UPDATE.md). Tidligere afsnit om privat repository og v0.2.0 nedenfor er historiske.


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


## V1.1: Update, fem aktiemarkeder og versionering

Streamlit-dashboardet har en **Update – GitHub** sektion med
**Tjek GitHub-opdatering** og **Backup og opdater nu**. Den er beregnet til
den lokale Python-installation (Windows eller anden maskine).

**Vigtigt:** Repoet er privat. Derfor bruger opdateringen Git Credential
Manager / SSH fra den eksisterende Git-klon, ikke et offentligt downloadlink
og ikke en GitHub API-nøgle indlagt i programmet.

I Windows PowerShell (inden appen startes):

~~~powershell
$env:STOCKSCANNER_ADMIN_TOKEN = Read-Host "Vælg langt administratortoken"
.\.venv\Scripts\python.exe -m streamlit run app.py
~~~

Token skal have mindst 20 tegn. Indstil det kun på serveren/maskinen, ikke i
GitHub, en WordPress-side eller et offentligt script.

**Sikker opdatering:** Kontrollerer trusted GitHub-origin, main-branch, ren
arbejdskopi og fast-forward fra origin/main. Før opdatering tages en
SQLite-konsistent kopi af data/scans.sqlite3 samt kopi af data/watchlist.txt.
ZIP-sikkerhedskopier ligger i backups/ og bliver ikke committed. En opdatering
skifter kun Git-sporede filer; genstart Streamlit bagefter. Hvis Git ikke er
installeret, privat adgang mangler eller der er lokale ændringer, afvises
opdateringen. Automatisk rollback af kode er endnu ikke implementeret.

**WordPress/hangar18.dk:** Denne updater opdaterer kun Python/Streamlit.
Den kan ikke opdatere en WordPress-plugin eller installere en Python-proces
på dit webhotel. Ved senere WordPress-integration bygger vi separat plugin,
versioneret ZIP, SHA-256-manifest og native WordPress-opdatering svarende
til Madplan. Private downloadadresser kræver autentificeret deployment
eller en separat godkendt distributionskanal.

### Markeder

Sidebar kan indsætte eksempler fra de fem valgte markeder:
Danmark (.CO), Tyskland (.DE), Sverige (.ST), Norge (.OL), USA (typisk symbol
uden børssuffiks). Tickers er kun et lille, redigerbart udvalg; ikke en
komplet liste over alle børsnoterede selskaber. Scoren er teknisk og ikke
en investeringsanbefaling.


### Sektoroverblik inspireret af open-source scanner

AI-Stock-Scanner viser nu gennemsnitsscore, 21-dages afkast, relativ volumen,
andel over SMA50 og en enkel sektortilstand for **de scannede aktier**.
Tilgangen er inspireret af sektor-først-analysen i det MIT-licenserede
hyan1985/ai-stock-scanner-projekt, men modellen er selvstændigt skrevet og
benytter ikke Tushare. Sektortilknytningen er manuelt defineret for de
20 eksempelaktier. Ukendte symboler mærkes "Ikke kategoriseret".

**Bemærk:** Hvis kun én eller to aktier i en sektor er valgt, er tallene
ikke repræsentative for hele sektoren. Status er en heuristik, ikke en
investeringsanbefaling eller en måling af nettokapitalstrømme.

## Fase 1 + 2 (november 2026): Lokal motor og WordPress-dashboard

**Ny installationsguide:** [docs/PHASE-1-2-SETUP.md](docs/PHASE-1-2-SETUP.md)

Fase 1 indeholder en lokal diagnostik (`python -m stockscanner.doctor --live --ollama`) og et sikkert, valgfrit WordPress-synkroniseringsmodul (`python -m stockscanner.site_sync --demo`).

Fase 2 indeholder den første version af en loginbeskyttet WordPress-plugin med shortcode `[ai_stock_scanner]` og et REST-endpoint, der kræver et særskilt WordPress Application Password. Den lokale PC **pusher** validerede tekniske researchresultater til hjemmesiden over HTTPS. Ollama er fortsat kun tilgængelig på PC'en; ingen porte på hjemmenetværket skal åbnes.

**WordPress-plugin v0.1.0:** [Download installations-ZIP fra GitHub](dist/hangar18-ai-stock-scanner-v0.1.0.zip). Du kan også bygge den i en lokal klon med `python scripts/build_wp_package.py`.

**Afgrænsning:** Subdomæne og WordPress er ikke oprettet eller installeret fra ChatGPT; den lokale PC og et live-webhotel er ikke end-to-end-testet. WordPress-opdatering i v0.1.0 udføres med versionsstyret ZIP, ikke endnu med Madplans automatiske opdaterings- og rollback-funktioner. Publikation af Yahoo/yfinance-afledte signaler kræver rettighedsvurdering; derfor er første forbindelsestest baseret på tydeligt mærkede demodata.


## WordPress-plugin v0.2.0 – privat GitHub-update og genaktivering

WordPress-delen har nu en **GitHub Update**-funktion under **Værktøjer → AI Stock Scanner**. Den kan hente nye versioner fra det **private** GitHub-repository, verificere SHA-256 og genaktivere et plugin, der var aktivt før opdateringen. Se [komplet vejledning](docs/WORDPRESS-GITHUB-UPDATE.md) og [installations-ZIP v0.2.0](dist/hangar18-ai-stock-scanner-v0.2.0.zip).

Fordi repoet er privat, kræver WordPress en **fine-grained GitHub-token med Contents: Read-only**, konfigureret i serverens `wp-config.php` som `ASC_GITHUB_TOKEN`. Token må ikke committes eller vises i frontend. WordPress bruger sin **midlertidige** kodebackup ved opdatering; permanent manuel rollback er endnu ikke implementeret. v0.1.0 skal opgraderes **én gang manuelt** via ZIP, før pluginets egen opdateringsknap er tilgængelig.

**Status:** ZIP og kode er oprettet i GitHub. Installation og genaktivering er endnu ikke testet på et rigtigt WordPress-webhotel.
