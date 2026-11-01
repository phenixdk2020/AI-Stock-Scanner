# AI Stock Scanner – offentlig GitHub-opdatering (v0.2.2)

> **v0.2.5 – API-godkendelse (2026-11-01):** Ved `HTTP 401 rest_not_logged_in` kan Python-scanneren nu automatisk gentage godkendelsen via `X-ASC-Authorization`, som kun godkendes på AI Stock Scanner-ruterne og valideres med WordPress' egen Application Password-funktion. Klienten kræver HTTPS og følger ikke redirects. [Download v0.2.5 ZIP](../dist/hangar18-ai-stock-scanner-v0.2.5.zip). Gå til **AI Stock Scanner → Opdateringer** for at opdatere; synkroniser derefter din Windows-projektmappe via `git pull --ff-only` og kør `python -m stockscanner.site_sync --check-auth`. Bemærk, at `/wp-json/wp/v2/users/me` stadig kan fejle i sådanne miljøer; fallback gælder kun scannerens egne REST-ruter. Hvis hosting også fjerner ekstra headers, er serverrettelse nødvendig.


> **Nyeste version: v0.2.3 (2026-11-01).** Denne version flytter WordPress-administrationen til et synligt hovedmenupunkt **AI Stock Scanner** med undermenuerne **Oversigt**, **Opdateringer** og **Forbindelse**. Under Opdateringer bruges `Tjek GitHub-opdatering` og `Backup og opdater plugin`. Ældre beskrivelser af v0.2.2 og placeringen under **Værktøjer** er historiske. [Hent v0.2.3 ZIP](../dist/hangar18-ai-stock-scanner-v0.2.3.zip). Første opgradering kan foretages via **Plugins → Tilføj nyt → Upload plugin → Erstat nuværende**. Kontrollér at pluginet er aktivt bagefter.


**Status 2026-11-01:** Repositoryet `phenixdk2020/AI-Stock-Scanner` er nu **offentligt**. Pluginet er opdateret til **v0.2.2** med tokenfri GitHub-opdatering og PclZip-kompatibel kontrol.

## Installer v0.2.2

**Download ZIP:** https://raw.githubusercontent.com/phenixdk2020/AI-Stock-Scanner/main/dist/hangar18-ai-stock-scanner-v0.2.2.zip

1. Hent ZIP-filen; den må ikke udpakkes inden upload.
2. WordPress → Plugins → Tilføj nyt → Upload plugin.
3. Hvis WordPress allerede har en tidligere version, vælg at erstatte den installerede version. Kontrollér derefter, at pluginet er aktivt.
4. Opret en WordPress-side med `[ai_stock_scanner]`.
5. Gå til **Værktøjer → AI Stock Scanner** for at se GitHub-opdateringspanelet.

**Ingen GitHub-token:** Sæt **ikke** `ASC_GITHUB_TOKEN` i `wp-config.php`. Den nye updater læser offentlige, versionerede ZIP-filer og `update.json` fra `raw.githubusercontent.com`, ikke GitHub-API med adgangstoken.

## Hvad v0.2.2 retter

- v0.2.0 indeholdt en **forkert formateret ZIP-fil** med fejl i central-directory-strukturen, hvilket gav `PCLZIP_ERR_BAD_FORMAT (-10)` ved installation.
- v0.2.1 rettede ZIP-strukturen.
- v0.2.2 indeholder yderligere offentlig GitHub-opdatering **uden token** og validerer ZIP via **PclZip**, som også bruges af WordPress på webhoteller uden PHP ZipArchive.
- Manifestet `update.json` angiver versionsnummer, forventet ZIP-sti og SHA-256.
- En opdatering registrerer, om pluginet var aktivt før filudskiftningen, og **genaktiverer efter en vellykket opdatering**.
- WordPress kan midlertidigt deaktivere pluginet under udskiftningen; den normale aktiveringstilstand gendannes bagefter. Mislykkes genaktiveringen, rapporterer updateren en fejl.

## Opdateringsflow fremover

Under **Værktøjer → AI Stock Scanner**:

1. **Tjek GitHub-opdatering** læser `update.json`.
2. Hvis versionen på GitHub er højere, vises **Backup og opdater plugin**.
3. Updateren downloader ZIP-filen over HTTPS fra den **faste, tilladte** public GitHub-sti.
4. Den kontrollerer SHA-256 og verificerer ZIP-filernes stier og hovedfilens versionsnummer ved hjælp af PclZip.
5. Den bruger WordPress' normale `Plugin_Upgrader` og genaktiverer pluginet, hvis det var aktivt.

WordPress' midlertidige backup ved opdateringsfejl er ikke en vedvarende, manuel rollbackfunktion. Tag en separat serverbackup før større opdateringer.

## Udvikling og pakning

Kilden ligger under `wordpress/hangar18-ai-stock-scanner/`.

Til nye versioner:
- Hæv plugin-headeren og `ASC_PLUGIN_VERSION`.
- Byg ZIP med Python-standardbibliotekets `zipfile` gennem `python scripts/build_wp_package.py`.
- Kontrollér ZIP med `python -m zipfile -t dist/hangar18-ai-stock-scanner-vX.Y.Z.zip`.
- Kør `python -m unittest discover -s tests -v` samt `php -l` og `php tests/wp_updater_reactivation.php` hvor PHP er tilgængelig.
- Commit ZIP samt opdater `update.json` med den **præcise** ZIP-checksum.
- Kontrollér efter en testopdatering, at pluginet fortsat er aktivt, at data stadig findes, og at shortcode/REST virker.

Manifestets format:

~~~json
{
  "name": "Hangar18 AI Stock Scanner",
  "slug": "hangar18-ai-stock-scanner",
  "version": "0.2.2",
  "package_path": "dist/hangar18-ai-stock-scanner-v0.2.2.zip",
  "sha256": "0ed2f56a45f74931d12c6c6b5aa4082da29dbd4e6fb0673a07f151eb210b3db2"
}
~~~

## Public repository – privatliv og sikkerhed

Fordi repositoryet nu er offentligt, er **alle filer i det synlige**, herunder kode og research under `docs/`. Bekræft, at ingen hemmeligheder, følsomme filer eller beskyttet materiale ligger i Git-historikken. En fil, som blot slettes i en senere commit, kan stadig findes i tidligere commits. Selve WordPress Application Password til datasynkronisering skal fortsat forblive server-/PC-hemmeligt; det har intet med GitHub-update at gøre.

**Teststatus:** ZIP-arkivets struktur, filstier og manifest er kontrolleret ved generering. PHP-opdatering og faktisk installation på dit webhotel kræver fortsat live-test; ingen har endnu kørt v0.2.2 på din WordPress-server fra denne chat.
