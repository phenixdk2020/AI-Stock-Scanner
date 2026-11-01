# Hangar18 – WordPress-installation og opdatering (v0.5.2)

**Status:** WordPress-plugin, GitHub-updater og versionsstyret ZIP-distribution er implementeret i repositoryet. Den faktiske pluginversion installeret på webhotellet kan **ikke** verificeres fra kildekoden alene.

Plugin: `wordpress/hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php`.
Versionsmanifest: `update.json`.
Aktuel releasepakke: `dist/hangar18-ai-stock-scanner-v0.5.2.zip`.
Repository: offentligt `phenixdk2020/AI-Stock-Scanner`.

WordPress-administration: **AI Stock Scanner → Oversigt / Opdateringer / Forbindelse**. Updateren kræver administratorrettighed, nonce, SHA-256- og ZIP-verifikation og genaktiverer efter opdatering, hvis pluginet var aktivt. Der kræves **ikke** GitHub API-token.

Data opbevares særskilt i WordPress' database, ikke i pluginmappen. Hver bruger har sin egen købshistorik og watchlist. v0.5.2 tilføjer sidebar, ETF og ni markeder samt screeningsfiltre og manuelle værdiansættelsesscenarier.

**Sikker releaseprocedure:** Kør tests → byg versionsmærket ZIP → opdater manifest → tag fuld backup → test på staging → installer og kontrollér aktiv status, login, køb, DKK-beregning, ETF'er og sync → udrul til produktion. Native rollback er ikke det samme som en permanent manuel rollbackfunktion, så bevar en ekstern backup.

Markedsdata skal bruges i overensstemmelse med leverandørvilkår. Der er intet nyt betalt API eller abonnement. WordPress skal aldrig kontakte den lokale Ollama-server fra internettet.


**Dansk aktiekatalog v0.5.2:** 141 historiske, CC0-markerede danske instrumenter fra 2025 med søgning og administratorstyret CSV-opdatering. Dette er ikke en officiel live-børsliste; ticker/ISIN og aktiv notering skal verificeres.


**v0.5.2:** Sticky venstremenu, dateret CSV-baseret aktiekatalog-sammenligning og ikke-destruktiv status 'ikke genfundet'. Intet automatisk Nordnet/Yahoo-scraping eller licenseret live-liste er indført.
