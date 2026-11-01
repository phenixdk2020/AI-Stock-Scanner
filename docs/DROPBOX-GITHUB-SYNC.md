# Dropbox → GitHub synkronisering

**Kilde på Windows:** C:\Users\allan\Dropbox\AI-Stock-Scanner

**GitHub-destination:** privat repository phenixdk2020/AI-Stock-Scanner,
undermappen docs/Dropbox/.

Dette er en **envejs synkronisering** af analysefiler: Dropbox er kilden.
Der udføres ingen sletninger i GitHub, ingen force-push og ingen synkronisering
af hele din øvrige Dropbox.

## Hvad er gjort fra ChatGPT?

Den 1. november 2026 blev MyStockScanner-gennemgang-2026-11-01.md kopieret
direkte fra den tilknyttede Dropbox til docs/Dropbox/ på GitHub.
Indholdet blev læst tilbage og verificeret.

Billedet watchlist-2026-11-01.png ligger også i den pågældende Dropbox-mappe,
men var **ikke** overført med chattens GitHub-forbindelse. Scriptet herunder
kan synkronisere både Markdown og PNG fra din egen Windows-maskine.

## Kør første gang

Kræver Git for Windows med adgang til dit private GitHub-repository.
Åbn Windows PowerShell i din lokale projektmappe (eller angiv den fulde
sti til scriptet):

~~~powershell
# Vis hvilke filer der vil blive synkroniseret
.\scripts\Sync-Dropbox-To-GitHub.ps1 -DryRun

# Hent ændringer og push nye/ændrede researchfiler
.\scripts\Sync-Dropbox-To-GitHub.ps1
~~~

Scriptet kloner selv GitHub-repositoryet til
C:\Users\allan\Documents\GitHub\AI-Stock-Scanner, hvis mappen ikke findes.
Det redigerer ikke kildefilerne i Dropbox.

## Fremtidige opdateringer

Du kan køre scriptet igen når som helst. For løbende sync kan du oprette
en opgave i **Windows Opgavestyring** til at køre PowerShell-scriptet
ved logon eller efter et interval, du selv vælger.

**En sådan opgave er ikke oprettet på din computer fra ChatGPT.**
Mappen på C:-drevet er ikke direkte tilgængelig fra ChatGPT; de aktuelle
filer blev fundet gennem din tilknyttede Dropbox-konto.

## Sikkerhedsregler

- Kun filtyperne MD, TXT, PNG, JPG, JPEG, WebP, PDF og CSV.
- Højst 20 MB per fil; store videoer og lokale databaser synkroniseres ikke.
- Visse hemmelighedsrelaterede filnavne bliver frasorteret.
- Scriptet kontrollerer ren Git-arbejdskopi, branch main og korrekt origin.
- Det opdaterer først lokal Git med fast-forward og pusher normalt.
- Det sletter ikke filer på nogen af siderne.

**Læs nye filer igennem inden første sync.**
Filnavnefilteret kan ikke finde adgangskoder, private oplysninger eller
API-tokens inde i dokumenter og billeder. At repositoryet er privat,
er ikke en garanti for at følsomme data må opbevares dér.

Hvis push fejler, eksempelvis på grund af konflikt eller manglende
GitHub-adgang, stopper scriptet. Det overskriver aldrig remote history.

## Relation til Hangar18 Update

Dette Dropbox-research-sync er **uafhængigt** af scannerens
Update-knap og af den planlagte WordPress-plugin-updater på hangar18.dk.
