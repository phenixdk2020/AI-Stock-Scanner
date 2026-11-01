# WordPress GitHub-opdatering – AI Stock Scanner v0.2.0

**Status:** Kode og installations-ZIP publiceret i det **private** GitHub-repository. Der er ikke foretaget en installation på dit WordPress-webhotel eller udført en liveopdatering.

## Hvad fungerer

- Administrator får under **Værktøjer → AI Stock Scanner** knapperne **Tjek GitHub-opdatering** og **Backup og opdater plugin**.
- Versionstjek henter `update.json` via GitHub API med server-side adgang til **det private repository**.
- Downloader kun den versionerede ZIP fra den låste GitHub-sti og verificerer **SHA-256**, versionsheader, pluginnavn og ZIP-mappestruktur.
- Anvender WordPress' indbyggede `Plugin_Upgrader`, som siden WordPress 6.3 har **midlertidig kodebackup og automatisk gendannelse ved installationsfejl**.
- Registrerer om pluginet var aktivt **før** WordPress midlertidigt deaktiverer det, og genaktiverer det bagefter. Hvis pluginet var inaktivt, aktiveres det ikke uden videre.
- Scannerresultater er gemt i WordPress-databasen, ikke i pluginmappen, og bevares under almindelig kodeopdatering.
- WordPress' almindelige Plugins-side kan også registrere en nyere version via `Update URI` og den registrerede updater.
- Automatisk baggrundsopdatering er **slået fra**. Administrator skal selv starte opdateringen.

**Bemærk:** WordPress kan midlertidigt deaktivere pluginet under udskiftning af filer. Mekanismen betyder, at det **bliver genaktiveret ved vellykket opdatering**, ikke at den interne midlertidige deaktivering aldrig forekommer. En PHP-fatal eller serverfejl kan stadig kræve manuel gendannelse. Brug derfor staging først.

## Første installation eller opgradering fra v0.1.0

v0.1.0 har **ikke** nogen GitHub-updater. Hvis v0.1.0 allerede er installeret, opgradér **første gang manuelt** via ZIP og WordPress' erstatningsfunktion:

`dist/hangar18-ai-stock-scanner-v0.2.0.zip`

Åbn WordPress → Plugins → Tilføj nyt → Upload plugin, upload ZIP og vælg at erstatte den eksisterende version. Hvis pluginet utilsigtet er inaktivt bagefter, aktivér det manuelt denne første gang. Fra v0.2.0 vil nye versioner kunne hentes inde fra pluginet.

## GitHub-token i wp-config.php

Repositoryet er privat. Derfor fungerer den offentlige raw.githubusercontent.com-løsning fra Madplan **ikke** direkte.

1. Opret et **fine-grained Personal Access Token** på GitHub.
2. Vælg **kun repositoryet `phenixdk2020/AI-Stock-Scanner`**.
3. Vælg repository permission **Contents: Read-only** (Metadata read gives standard access).
4. Vælg en passende udløbsdato, og roter token før udløb.
5. Tilføj følgende i WordPress' `wp-config.php` på serveren, **over** linjen som indlæser `wp-settings.php`:

~~~php
define('ASC_GITHUB_TOKEN', 'INDSAET_DIT_READONLY_GITHUB_TOKEN_HER');
~~~

Læg **aldrig** token i GitHub, pluginfilerne, en WordPress-side eller JavaScript. Lad den kun være i serverens `wp-config.php` og begræns adgang til filen.

GitHub API'et kræver adgang over HTTPS udgående fra webhotellet. Der er ingen ekstra abonnementsbetaling for selve denne løsning.

## Sådan opdaterer du fremover

1. Udvikl pluginet i GitHub under `wordpress/hangar18-ai-stock-scanner/`.
2. Hæv versionsnummeret i både plugin-headeren og `ASC_PLUGIN_VERSION`.
3. Byg en versionsmærket ZIP med `python scripts/build_wp_package.py`.
4. Publicér den under `dist/hangar18-ai-stock-scanner-vX.Y.Z.zip`.
5. Opdatér repositoryets `update.json` med samme version, `package_path` og ZIP-filens faktiske SHA-256. Dette kan automatiseres via en separat **manuel** GitHub Actions-workflow senere, men kræver ikke et betalt API.
6. På WordPress vælg **Værktøjer → AI Stock Scanner → Tjek GitHub-opdatering → Backup og opdater plugin**.

Manifestet har formen:

~~~json
{
  "name": "Hangar18 AI Stock Scanner",
  "slug": "hangar18-ai-stock-scanner",
  "version": "0.2.0",
  "package_path": "dist/hangar18-ai-stock-scanner-v0.2.0.zip",
  "sha256": "f8997db1ba935a36e3098370ab4bf96d44ea8ce3daada5b9173b0f617a0eca1e"
}
~~~

Dette er låst til den ene betroede repository-sti, og ZIP-filen verificeres før installation. Opdatér aldrig manifestet til en ny version før den tilhørende ZIP er bygget og publiceret.

## Backup og rollback

WordPress 6.3+ tager en **midlertidig** backup under normal manuel pluginopdatering og prøver at gendanne ved en installationsfejl. Backupen slettes efter en **vellykket** opdatering. Dette er **ikke** en permanent versionsbackup eller en manuel Rollback-knap som i Madplan.

Før større produktionsopdateringer: tag en separat backup af pluginmappen og WordPress-databasen via dit webhotels almindelige backupløsning. En egentlig permanent checkpoint-/rollback-funktion er endnu ikke implementeret i AI Stock Scanner.

## Kontrol på staging

- Installer ZIP v0.2.0 og bekræft at pluginet er aktivt.
- Åbn dashboardet med en abonnentbruger.
- Tilføj read-only GitHub-token i staging-`wp-config.php`.
- Brug Tjek GitHub-opdatering; forvent v0.2.0 som den seneste.
- Når næste testversion er publiceret: kør manuel opdatering og kontrollér at **Plugins → AI Stock Scanner** stadig viser aktiv.
- Kontroller at data, shortcode, sync-agent og WordPress REST-route stadig fungerer.
- Prøv opdatering når pluginet er **inaktivt** og kontrollér at det forbliver inaktivt.
- Test fejlet SHA-256 og forkert ZIP-version; begge skal afvises.

**Sikkerhed:** PHP `ZipArchive` er påkrævet, og WordPress skal have rettigheder til at opdatere pluginfiler. Token sendes kun server-til-server til `api.github.com`; den anvendes ikke i URL'er eller browseren.

## Links

- [Installationspakke v0.2.0](../dist/hangar18-ai-stock-scanner-v0.2.0.zip)
- [Plugin-kilde](../wordpress/hangar18-ai-stock-scanner/)
- [Opdateringsklasse](../wordpress/hangar18-ai-stock-scanner/includes/class-asc-github-updater.php)
- [Lokalt scanner-/WordPress-setup](PHASE-1-2-SETUP.md)
