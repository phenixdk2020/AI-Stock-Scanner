# AI-Stock-Scanner – fase 1 + 2: lokal motor og WordPress

> **OPDATERING 2026-11-01:** Brug **v0.2.2** i stedet for v0.1.0/v0.2.0. GitHub er nu **offentligt**; WordPress GitHub-updateren kræver **ikke** token. Den første v0.2.0 ZIP var fejlformateret. Hent [v0.2.2 ZIP](../dist/hangar18-ai-stock-scanner-v0.2.2.zip) og følg [den aktuelle GitHub-update-guide](WORDPRESS-GITHUB-UPDATE.md). Ældre installationsafsnit nedenfor er bevaret som historik.


**Status:** Kode ligger i GitHub. WordPress-plugin er kildekode med en versionsstyret ZIP-bygger; installation på Hangar18 er **ikke** udført. Vi kan ikke logge på din PC eller webhotel fra denne chat.

## Overblik

1. **Windows / Lenovo**: Python/Streamlit scanner aktier med eksisterende yfinance-adapter, SQLite gemmer historik, Ollama forklarer en valgt scanning lokalt på localhost:11434.
2. **WordPress** på en mulig `aktier.hangar18.dk`: selvstændig plugin med shortcode `[ai_stock_scanner]`, loginbeskyttet tabel og kun de **senest modtagne** tekniske scores.
3. **Envejs data-push**: Windows Python sender et valideret snapshot over HTTPS til et privat REST-endpoint. WordPress kan hverken køre kode på PC'en eller kontakte Ollama. Ingen åbne porte på privatnetværket.

**Fase 2 leverer ikke** automatisk opgavekø/AI-forespørgsler fra hjemmesiden endnu. Det er næste udviklingstrin, efter sikker basisforbindelse er testet.

## Fase 1 – Windows

Kræver Python 3.11+, Git for Windows, privat GitHub-adgang og valgfrit Ollama.

PowerShell i en mappe, hvor du ønsker projektet:

~~~powershell
git clone https://github.com/phenixdk2020/AI-Stock-Scanner.git
cd AI-Stock-Scanner
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Miljøkontrol uden markedskald
.\.venv\Scripts\python.exe -m stockscanner.doctor

# Live-kurser i fem markeder (kræver internet og datakilde)
.\.venv\Scripts\python.exe -m stockscanner.doctor --live

# Kontrol af lokalt Ollama (start Ollama først)
.\.venv\Scripts\python.exe -m stockscanner.doctor --ollama

# Start lokalt dashboard
.\.venv\Scripts\python.exe -m streamlit run app.py
~~~

Ollama bruges via `http://127.0.0.1:11434/api/generate`; den eksisterende `stockscanner/ollama.py` bruger som standard `qwen3.5:9b`. Du kan vælge en anden model i Streamlit. Modellen skal være installeret lokalt på din PC.

Test scanning fra kommandolinjen:

~~~powershell
.\.venv\Scripts\python.exe scan_cli.py --tickers "NOVO-B.CO,SAP.DE,VOLV-B.ST,EQNR.OL,MSFT" --csv data\latest.csv
~~~

Bemærk: live-data kan fejle, fx ved netværk, tickerændringer og rate limiting. Der er ikke udført live-end-to-end-test på din PC fra denne chat.

## Fase 2 – pluginpakke

WordPress-plugin ligger i `wordpress/hangar18-ai-stock-scanner/`.

Byg installationspakken i Git-klonen (ingen ekstra Python-afhængigheder):

~~~powershell
.\.venv\Scripts\python.exe scripts\build_wp_package.py
~~~

Det opretter:
- `dist/hangar18-ai-stock-scanner-v0.1.0.zip`
- `dist/hangar18-ai-stock-scanner-v0.1.0.json` (SHA-256 og versionsmetadata)

Installer ZIP via **WordPress → Plugins → Tilføj nyt → Upload plugin** på et **testsite** med HTTPS. Version 0.1.0 indeholder ikke automatisk GitHub-opdatering. Nye versioner kan installeres gennem WordPress' almindelige ZIP-opgraderingsfunktion. Det er bevidst **ikke** Madplans fulde GitHub Update/rollback endnu, da projektets GitHub-repository er privat og kræver en sikker distributionskanal.

Aktivér plugin, og opret en side på dit subdomæne. Indsæt:

~~~text
[ai_stock_scanner]
~~~

Kun **indloggede WordPress-brugere** ser data. Sidens besøgende uden login får en loginhenvisning. Undtag dashboardsiden fra almindelig fuldside-cache på webhotel/CDN, så indlogget indhold ikke caches offentligt.

**Vigtigt:** Der er ikke oprettet noget subdomæne i DNS, WordPress-installation eller plugin-aktivitet på dit webhotel.

## Opret forbindelsesbruger på WordPress

Efter aktivering oprettes rollen **AI Stock Scanner Sync Agent** med kun rettighederne `read` og `asc_sync`. Via **Brugere → Tilføj ny** opretter du en separat teknisk bruger med denne rolle; brug ikke din administrator til daglig synkronisering.

På den tekniske brugers profil: opret et **Application Password** (navn fx `AI-Stock-Scanner-PC`). Dette er *ikke* dit WordPress-loginpassword.

Installér helst på HTTPS; kontrollér at webhotellet videresender `Authorization`-headeren korrekt til WordPress. Lad aldrig Application Password indgå i GitHub, wp-sider eller frontend JavaScript.

### Første forbindelse: demo uden markedsdata

Sæt værdierne i en PowerShell-session (ikke i en .ps1-fil i GitHub):

~~~powershell
$env:ASC_WP_SITE_URL = "https://aktier.hangar18.dk"
$env:ASC_WP_USER = "DIN_SYNC_BRUGER"
$env:ASC_WP_APP_PASSWORD = Read-Host "WordPress Application Password"

# Tjek demo-snapshot uden at sende noget
.\.venv\Scripts\python.exe -m stockscanner.site_sync --demo --preview

# Send tydeligt mærkede DEMODATA til WordPress
.\.venv\Scripts\python.exe -m stockscanner.site_sync --demo
~~~

Åbn herefter WordPress-siden med en almindelig bruger; du skal se 2 **demodata**-rækker. Under **Værktøjer → AI Stock Scanner** ses dato/tid for seneste synkronisering. API-endpoint:

~~~text
POST https://aktier.hangar18.dk/wp-json/ai-stock-scanner/v1/snapshot
~~~

Afviser uautoriseret adgang, fejlformater, for store payloads, gentagelser og gamle data.

### Rigtige scanninger – kun hvis licensforhold er kontrolleret

Det eksisterende yfinance/Yahoo-feed er uofficielt og må ikke antages at give ret til offentliggørelse eller videredistribution, heller ikke af alle afledte data.

**Kør derfor ikke rigtige uploads til WordPress, før datalicenserne er vurderet.** Lokal research i Streamlit kan bruges uafhængigt. Den eksplicitte sikkerhedsbremse for rigtige uploads er:

~~~powershell
# Lokal forhåndsvisning
.\.venv\Scripts\python.exe -m stockscanner.site_sync --preview

# Kun når der er verificerede publiceringsrettigheder
.\.venv\Scripts\python.exe -m stockscanner.site_sync --confirm-data-rights
~~~

Aktuel WordPress-visning indeholder kun ticker, land, handelsdato, teknisk score og signal; **ikke** fuld kurshistorik, rå OHLCV eller AI-fortællinger.

## Tests

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

PHP kan lintes lokalt med `php -l wordpress/hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php`, hvis PHP findes. End-to-end-test på test-WordPress med korrekt Application Password og HTTPS er nødvendig før produktionsbrug.

## Begrænsninger og næste etaper

- Ingen funktion, der sender ny AI-analyse fra webhotel til PC, i v0.1.0.
- Ingen fuld Quality/Value-scoring eller store globale aktieuniverser.
- Ingen automatiske GitHub-opdateringer af WordPress-plugin (kun ZIP-opdatering).
- Ingen økonomiske API-abonnementer kræves til grundkoden.
- Kurser kan være forsinkede, fejlbehæftede eller utilgængelige.
- WordPress skal selv være installeret og konfigureret på subdomænet.
- Windows Task Scheduler for daglige scan/sync kan først sættes op efter end-to-end test og licensafklaring.

**Sikkerhedsarkitektur:** Lokal Ollama-poret `11434` og Streamlit `8501` skal ikke eksponeres mod internettet.


## Opdatering – nyt i WordPress-plugin v0.2.0

Den oprindelige beskrivelse af v0.1.0 ovenfor er historik. **v0.2.0** har en GitHub-updater til det private repository, med administratorstyring, sikker token i `wp-config.php`, SHA-256, WordPress' indbyggede midlertidige backup og genaktivering efter opdatering. Installér [v0.2.0 ZIP](../dist/hangar18-ai-stock-scanner-v0.2.0.zip) i stedet for v0.1.0, og følg [WordPress GitHub Update-guiden](WORDPRESS-GITHUB-UPDATE.md).

En installation af v0.1.0 kræver **første manuelle ZIP-opgradering** til v0.2.0, hvorefter GitHub-knappen er tilgængelig. En permanent manuel rollback-funktion er ikke færdigbygget.
