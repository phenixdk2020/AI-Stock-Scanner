# AI-Stock-Scanner – lokal Python og WordPress

**Aktuel WordPress-release: v0.5.0.** Denne guide erstatter ældre instruktioner om privat repository, tokenkrav og administration under Værktøjer. Se [WordPress-opdatering](WORDPRESS-GITHUB-UPDATE.md).

## Arkitektur

- Lokal Python/Streamlit-scanner med SQLite, yfinance og valgfri Ollama. Kører på din PC og sender højst 50 forskningsresultater ad gangen, når du beder den om det.
- WordPress-plugin på `aktier.hangar18.dk`, med privat portefølje, ETF-køb, personlig watchlist, DKK-konvertering og scanner/analysesider. Gemte køb og seneste snapshot er serverdata og kræver ikke en tændt PC.
- Scanner-REST: `/wp-json/ai-stock-scanner/v1/snapshot`, HTTPS og Application Password på en teknisk WP-bruger. Ingen ekstern Ollama-port.
- Markeder: DK, DE, SE, NO, USA, FR, NL, ES, FI. Eksempler er ikke et komplet børsunivers. Opdateringskilden er et **offentligt** GitHub-repository uden adgangstoken.

## Lokal installation (PowerShell)

```powershell
git clone https://github.com/phenixdk2020/AI-Stock-Scanner.git
cd AI-Stock-Scanner
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m stockscanner.doctor
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Opdater en eksisterende ren Git-klon med `git pull --ff-only`; lav backup af lokale data og sammensmelt egne ændringer først, hvis den er modificeret.

## WordPress

Installér plugin-ZIP via **Plugins → Tilføj nyt → Upload plugin** og kontrollér aktivering. Administratoren finder **AI Stock Scanner → Oversigt / Opdateringer / Forbindelse**. Opret startside med `[ai_stock_home]`, eller indsæt `[ai_stock_scanner]`, `[ai_stock_portfolio]`, `[ai_stock_watchlist]` eller `[ai_stock_analysis]` på separate sider.

Gem synkroniseringens brugernavn/Application Password som miljøvariabler på PC'en:

```powershell
$env:ASC_WP_SITE_URL = "https://aktier.hangar18.dk"
$env:ASC_WP_USER = "DIN_SYNC_BRUGER"
$env:ASC_WP_APP_PASSWORD = Read-Host "Application Password"
.\.venv\Scripts\python.exe -m stockscanner.site_sync --check-auth
.\.venv\Scripts\python.exe -m stockscanner.site_sync --demo
```

Rigtige data skal kun synkroniseres, når du har gennemgået rettighederne til afledte markedsdata; `--confirm-data-rights` er påkrævet. Python og Ollama fungerer ikke på webhotellet; de sidst uploadede resultater bliver stående, når PC'en er slukket.

## Begrænsninger

Ingen licenseret livekursgaranti, ingen genererede fundamentale Q/V/M-scorer, ingen automatisk køb/salg og ingen automatisk Kronos-forecast. Manuelle bull/base/bear-scenarier er blot EPS × P/E. Alle udregninger skal vises med tydelig kilde, dato og valuta.

**Live-installation kan ikke verificeres ud fra GitHub-koden**. Test login, kurser, dataoverlevelse og updater direkte på WordPress før produktionsbrug.
