# AI-Stock-Scanner — v0.5.0

**Aktuel WordPress-version: v0.5.0**. [Installations- og opdateringsvejledning](docs/WORDPRESS-GITHUB-UPDATE.md). Når releasen er udgivet på `main`, kan [ZIP-filen hentes her](dist/hangar18-ai-stock-scanner-v0.5.0.zip).

Privat dansk WordPress-portefølje + lokal Python/Streamlit-scanner. Ingen ekstra betalte AI-API'er eller abonnementer kræves til grundfunktionerne. Markedsdata fra uofficielle kilder må kun anvendes efter kontrol af de relevante licensvilkår.

## WordPress v0.5.0

- **Venstremenu** på desktop og sammenfoldelig navigation på mobil med Overblik, Portefølje, Watchlist, Aktiescanner, Analyse og Indstillinger.
- Privat **aktie- og ETF-portefølje** med heltalsantal, flere køb af samme papir, redigering, manuel aktuel kurs og CSV-eksport.
- **Investeret, aktuel værdi og gevinst/tab** i både værdipapirets handelsvaluta og DKK. Mulighed for at angive **Betalt i alt (DKK)**, så købets effektive omregningskurs og faktiske anskaffelsessum anvendes. ECB-referencekurs bruges til vejledende dagsomregning. Manglende kurser markeres som skøn eller ukendte.
- Privat watchlist og valgfrie Yahoo Finance-candlesticks (eksperimentel kilde; **slået fra som standard**).
- Lokale scannersnapshots til WordPress via HTTPS, højst 50 værdipapirer, filtrering efter marked, aktie/ETF, teknisk signal og minimumscore.
- Analysefane med fordeling af tekniske scorer og **manuelt indtastede bull/base/bear-prisscenarier (EPS × P/E)**. Der udgives **ikke opdigtede fundamentale kvalitet-, moat- eller value-scorer** eller Kronos-prognoser.
- Negen understøttede markeder: Danmark, Tyskland, Sverige, Norge, USA, Frankrig, Holland, Spanien og Finland. Eksempler er *ikke* hele børsuniverset.

**Data bevares ved opdatering:** Porteføljeposter og watchlists ligger som WordPress-brugermetadata, scannerresultater som site-options — ikke i pluginmappen. Test dog en opdatering på staging, og tag backup før produktionsopdatering.

Gå til **AI Stock Scanner → Opdateringer** i WordPress-administrationen, eller upload den versionsmærkede ZIP via Plugins. Hovedmenuen har **Oversigt**, **Opdateringer** og **Forbindelse**. Den offentlige GitHub-updater kræver **intet GitHub-token**. Den lokale Python-updater kan separat kræve et administratortoken som applikationsbeskyttelse, men det er ikke et GitHub Access Token.

## Lokal Python-scanner

**Forudsætninger:** Python 3.11+, Windows/macOS/Linux, Pythonpakker fra `requirements.txt`.

```powershell
git clone https://github.com/phenixdk2020/AI-Stock-Scanner.git
cd AI-Stock-Scanner
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

```powershell
.\.venv\Scripts\python.exe scan_cli.py --tickers "NOVO-B.CO,ASML.AS,SAN.MC,NOKIA.HE,VWCE.DE"
.\.venv\Scripts\python.exe -m stockscanner.site_sync --check-auth
.\.venv\Scripts\python.exe -m stockscanner.site_sync --demo --preview
```

WordPress-synkronisering bruger `ASC_WP_SITE_URL`, `ASC_WP_USER` og `ASC_WP_APP_PASSWORD` som miljøvariabler. Brug en særskilt, begrænset WP-bruger. Upload af rigtige forskningsscores kræver bekræftet ret til databrug (`--confirm-data-rights`). **Ollama kører kun lokalt**, ingen åbne porte til hjemmenetværket.

Den gennemsigtige **tekniske score** anvender SMA50/200, RSI14, MACD, 21-dages afkast og volumen (20/20/20/20/10/10 point). Score er ikke en købsanbefaling eller et mål for en akties fundamentale kvalitet. Historiske data kommer fra yfinance/Yahoo, er ikke garanteret aktuelle og er ikke en licenseret realtids-API.

## Tests og repository

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions kontrollerer også PHP-syntaks, DKK-beregninger, WordPress-opdatering og flere porteføljekøb.

- [Opdateringsguide](docs/WORDPRESS-GITHUB-UPDATE.md)
- [Lokal scanner / WordPress-synkronisering](docs/PHASE-1-2-SETUP.md)
- [Dropbox → GitHub forskningsfiler](docs/DROPBOX-GITHUB-SYNC.md)
- [MyStockScanner-gennemgang](docs/Dropbox/MyStockScanner-gennemgang-2026-11-01.md)
- [MyStockScanner-funktionstest](docs/Dropbox/MyStockScanner-funktionstest-2026-11-01.md)

**Historiske releases** (v0.1.0–v0.4.4) ligger i `dist/`. Den nye v0.5.0 erstatter ikke automatisk en installation, før den eksplicit opdateres. Live-deployment på `aktier.hangar18.dk` er **ikke verificeret** ved udgivelse.
