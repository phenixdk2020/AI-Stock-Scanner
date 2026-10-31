# Hangar18.dk – WordPress-installation og Update

## Status

AI-Stock-Scanner er endnu en Python/Streamlit-applikation, ikke en installeret
WordPress-plugin. Den lokale updater i Streamlit trækker fra det private
GitHub-repository via maskinens egne Git-legitimationsoplysninger.

**Denne fil er en teknisk implementeringsplan, ikke en påstand om at
WordPress-plugin eller deployment allerede findes.**

## Mål

- Webfrontend på hangar18.dk under WordPress, mobilvenlig.
- Alle godkendte indloggede brugere kan se scanningerne (subscriber/read).
- Kun WordPress-administrator må opdatere plugin, konfigurere datakilder og
  ændre følsomme indstillinger.
- Samme flow som de eksisterende Hangar18 WordPress-projekter:
  **Tjek GitHub-opdatering → Backup → Opdater nu → Verificér → Rollback**.
- Opdateringer må ikke deaktivere plugin eller slette gemte data.
- Ingen løbende betaling for nye API'er eller tjenester.

## Arkitektur

1. Python-scanneren kører på en administreret Windows/Linux-maskine med
   gratis markedsdata og lokal Ollama.
2. Et separat WordPress-plugin viser senest modtagne scannerresultater.
3. Dataoverførsel skal være autoriseret: HTTPS, server-side credentials,
   snævre REST-rettigheder, payload-validering og replay-beskyttelse.
   Ingen Ollama-endpoints eller Python-kommandoer må udstilles åbent.
4. Data leveres ved planlagt push fra scannermaskinen eller en anden sikkert
   etableret kanal. Ingen PHP-side skal eksekvere Git eller shell på webhotellet.
5. WordPress gemmer brugerindstillinger/scanresultater i database og ikke i
   pluginets kodefolder, så de overlever opdatering.

## Installerbar WordPress-pakke og versionering

Der skal bygges et WordPress-plugin med en stabil mappe/slug:
ai-stock-scanner/ai-stock-scanner.php.

Første installation: upload versioneret ZIP gennem WordPress Plugins.
Senere opdateringer: WordPress' native plugin-updater med følgende kontroller:

- versionsnummer i PHP-header og manifest stemmer
- fast tilladt GitHub-repository og allowlisted ZIP-download-URL
- SHA-256-verifikation af hentet ZIP før installation
- kun administrators rettighed med WordPress nonce/capability check
- backup af plugin og relevante data, med mulighed for gendannelse
- rollback ved mislykket opdatering
- plugins forbliver aktive efter WordPress-kernens midlertidige deaktivering
- separate regressionstests for update-flow og reaktivering

**Privat repository:** Et offentligt raw.githubusercontent.com-update.json
og et offentligt ZIP-link kan ikke bruges direkte. Vælg ved implementering
enten en begrænset autentificeret, server-side GitHub-distributionskanal
eller udgiv de signerede/hashed releasepakker i en særskilt publiceret
distributionskanal. GitHub-token må aldrig indgå i frontend-JavaScript,
kildekode, git-commits eller almindelige plugin-indstillinger.

## Udrulningskontrol

1. Valider PHP-version, WordPress-version og hostingmulighed for REST.
2. Installer på staging-kopi af hangar18.dk før produktionsinstallation.
3. Verificér shortcode/page, login, brugerrettigheder og data-import.
4. Kør dry-run backup og update-test, også når en plugin er aktiveret.
5. Kontroller rollback og at brugerdata fortsat findes.
6. Først derefter aktivér den synlige opdateringsknap på produktion.

## Markedsscope

Dækker Danmark, Tyskland, Sverige, Norge og USA. De aktuelle
eksempel-tickere i stockscanner/markets.py repræsenterer ikke alle aktier.
En fuld børsunivers-scanner kræver verificerede, opdaterede aktielister og
datakildens tilladte forbrugsniveau.

## Fra det kinesiske open-source projekt

Kan bruge de dokumenterede idéer om sektorrangering, relativ volumen,
tendens, og overophedningsadvarsler. Kinesiske Tushare-moneysflow-tal
må ikke repræsenteres som sammenlignelige data for de fem markeder.
