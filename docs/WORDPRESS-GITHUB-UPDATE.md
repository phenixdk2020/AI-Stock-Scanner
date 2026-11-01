# WordPress – aktuel opdateringsvejledning (v0.5.1)

> Dette er den aktuelle installationsguide. Ældre ZIP-versioner under `dist/` er historik. Vær særlig opmærksom på den tidligere fejlformaterede v0.2.0, som **ikke** må installeres.

## Installation

1. Tag en backup af WordPress-databasen og pluginfilerne, og prøv helst på staging.
2. Hent `dist/hangar18-ai-stock-scanner-v0.5.1.zip` fra den udgivne `main`-branch.
3. Åbn WordPress → **Plugins → Tilføj nyt → Upload plugin**. Vælg ZIP, og erstat den nuværende pluginversion, hvis WordPress spørger.
4. Kontrollér, at **Hangar18 AI Stock Scanner v0.5.1** er aktivt.
5. Gå til **AI Stock Scanner → Oversigt**, og vælg om nødvendigt **Opret porteføljeside og sæt som forside**. Dette skal gøres eksplicit; opdateringen ændrer ikke automatisk forsiden.
6. Åbn forsiden som almindelig bruger. Venstremenuen har Overblik, Portefølje, **Danske aktier**, Watchlist, Aktiescanner, Analyse og Indstillinger. På mobil åbnes den fra **Menu**.
7. Åbn **Danske aktier** og søg efter Harboe. Det medfølgende åbne CC0-katalog rummer 141 historiske 2025-noteringer; fuld nutidig børsdækning er ikke garanteret. Administrator kan hente opdateringer eller importere en ny licenseret CSV.
8. Kontrollér, at tidligere køb, DKK-beløb og watchlist stadig er der. Prøv også et nyt ETF-køb (heltal) og et scannerfilter.

## Pluginets egen opdatering

I **AI Stock Scanner → Opdateringer** vælg **Tjek GitHub-opdatering** → **Backup og opdater plugin**. Updateren henter den offentlige versionsmanifest `update.json` og ZIP via `raw.githubusercontent.com`, kontrollerer SHA-256 og ZIP-stier og håndterer genaktivering.

**Der kræves ikke `ASC_GITHUB_TOKEN`.** Repositoryet er offentligt. GitHub-updateren er uafhængig af det lokale Python/Streamlit-updateværktøj og WordPress' Application Password til sikker datasynkronisering.

## Forbindelse til lokal scanner

Konfigurér en WordPress-bruger med rollen **AI Stock Scanner Sync Agent**. Opret Application Password på denne bruger og send scannerresultater via HTTPS fra din Windows-PC. Under **AI Stock Scanner → Forbindelse** kan du kontrollere data og kurskilder.

Test fra `C:\AI-Stock-Scanner`:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m stockscanner.site_sync --check-auth
.\.venv\Scripts\python.exe -m stockscanner.site_sync --demo --preview
```

Private data bliver i WordPress-brugermetadata. Markedsdataleverandøren Yahoo er uofficiel og **deaktiveret som standard**. Livekursers tidsforsinkelse er ikke garanteret 15 minutter; kursens faktiske tidsstempel vises, når data findes. ECB anvendes til vejledende valutakurser, som normalt opdateres på bankdage.

## Validering og begrænsninger

Kør `python -m unittest discover -s tests -v`, `php -l` på pluginfiler og PHP-integrationstests på staging. `update.json`, plugin-header og ZIP-checksum skal matche.

Tidligere køb/salg, udbyttehistorik, fundamental score, automatiske Kronos-forudsigelser og licenseret 15-minutters markedsfeed er **ikke alle implementeret**. Vurder ikke platformen som fuldt handelssystem.

**Produktionsstatus:** GitHub kan vise, at releasekode og ZIP findes. Det beviser ikke, at pluginet er installeret på `aktier.hangar18.dk`. Kontrollér det i WordPress' pluginliste.
