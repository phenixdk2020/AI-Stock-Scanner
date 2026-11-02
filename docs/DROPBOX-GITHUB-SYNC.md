# Dropbox → GitHub — forskningsfiler

**Kilde:** `C:\Users\allan\Dropbox\AI-Stock-Scanner`.
**Destination:** **offentligt** repository `phenixdk2020/AI-Stock-Scanner`, undermappen `docs/Dropbox/`.

Envejs synkronisering — Dropbox er kilden. Script: `scripts/Sync-Dropbox-To-GitHub.ps1`. Det kopierer understøttede filtyper og overskriver ikke andre grene eller sletter remote-historik.

```powershell
.\scripts\Sync-Dropbox-To-GitHub.ps1 -DryRun
.\scripts\Sync-Dropbox-To-GitHub.ps1
```

Scriptet kontrollerer ren Git-arbejdskopi, branch `main`, korrekt origin og fast-forward før push. Det overfører ikke hele Dropbox, og det kræver ikke et nyt API-abonnement. Den lokale Git-installation skal dog have skriveadgang til repositoryet.

**Sikkerhed:** Repoet er offentligt. Læs nye MD/PDF/CSV/PNG-filer før push og kontrollér persondata, licensbegrænset indhold og adgangskoder. Filnavnefiltre kan ikke opdage alle hemmeligheder. En hemmelighed, som pushes og senere slettes, kan fortsat findes i Git-historikken.

**Status 2026-11-02:** docs/Dropbox er bragt ajour med Dropbox-mappen (gennemgang, funktionstest, supplerende test, emnelog, restliste, læs-mig og billeder) og udvidet med datakatalog og screenshots-2026-11-02/. PDF-e-bøgerne i Dropbox er bevidst ikke kopieret til det offentlige repo.

Dropbox-sync er uafhængig af WordPress-opdateringsknappen og scannerens Application Password.
