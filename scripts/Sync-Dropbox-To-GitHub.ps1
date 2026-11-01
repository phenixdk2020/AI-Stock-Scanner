<#
.SYNOPSIS
 Envejs sync af researchfiler fra Dropbox til privat GitHub-repository.
 Kræver Git for Windows og eksisterende Git-login (Credential Manager/SSH).
 Kompatibel med Windows PowerShell 5.1 og PowerShell 7.
#>
[CmdletBinding()]
param(
 [string]$SourcePath = (Join-Path $env:USERPROFILE 'Dropbox\AI-Stock-Scanner'),
 [string]$RepositoryPath = (Join-Path $env:USERPROFILE 'Documents\GitHub\AI-Stock-Scanner'),
 [switch]$DryRun
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repoUrl = 'https://github.com/phenixdk2020/AI-Stock-Scanner.git'
$extensions = @('.md','.txt','.png','.jpg','.jpeg','.webp','.pdf','.csv')
$maxSize = 20MB

function RunGit([string[]]$Commands) {
 & git @Commands
 if ($LASTEXITCODE -ne 0) { throw "Git-fejl: exitcode $LASTEXITCODE. Intet force-push udført." }
}
function TrustedOrigin([string]$Url) {
 return ($Url.Trim() -match '^(?i:(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)phenixdk2020/AI-Stock-Scanner(?:\.git)?/?)$')
}

if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
 throw "Dropbox-mappen findes ikke: $SourcePath"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git for Windows skal installeres.' }
$root = (Resolve-Path -LiteralPath $SourcePath).Path.TrimEnd('\')
$files = @(Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {
 $relative = $_.FullName.Substring($root.Length).TrimStart('\')
 ($extensions -contains $_.Extension.ToLowerInvariant()) -and
 ($_.Length -le $maxSize) -and
 (-not [bool]($_.Attributes -band [IO.FileAttributes]::ReparsePoint)) -and
 ($_.Name -notmatch '(?i)(^|[._-])(token|password|secret|credential|privatekey|apikey|id_rsa|env)([._-]|$)') -and
 ($relative -notmatch '(?i)(^|\\)(\.git|\.venv|node_modules|__pycache__)(\\|$)')
})
Write-Host "Kilde: $root"
Write-Host "Godkendte filer: $($files.Count)"
if ($DryRun) {
 foreach ($f in $files) {
  Write-Host ('[DRY-RUN] docs/Dropbox/' + $f.FullName.Substring($root.Length).TrimStart('\').Replace('\','/'))
 }
 Write-Host 'Ingen ændringer foretaget.'
 return
}

if (-not (Test-Path -LiteralPath $RepositoryPath -PathType Container)) {
 $parent = Split-Path -Path $RepositoryPath -Parent
 if (-not (Test-Path -LiteralPath $parent)) { New-Item -Path $parent -ItemType Directory -Force | Out-Null }
 RunGit @('clone','--branch','main',$repoUrl,$RepositoryPath)
}
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryPath '.git'))) {
 throw "Mappen er ikke en Git-klon: $RepositoryPath"
}

Push-Location -LiteralPath $RepositoryPath
try {
 $origin = (& git remote get-url origin)
 if ($LASTEXITCODE -ne 0 -or -not (TrustedOrigin $origin)) { throw 'Forkert GitHub origin.' }
 $branch = (& git branch --show-current).Trim()
 if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') { throw 'Sync kræver main-branch.' }
 $dirty = (& git status --porcelain)
 if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Lokale Git-ændringer opdaget. Sync stoppet.' }
 RunGit @('fetch','--no-tags','origin','main')
 RunGit @('pull','--ff-only','origin','main')

 $updated = 0
 foreach ($f in $files) {
  $relative = $f.FullName.Substring($root.Length).TrimStart('\')
  $dest = Join-Path (Join-Path $RepositoryPath 'docs\Dropbox') $relative
  $dir = Split-Path -Path $dest -Parent
  if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $needed = -not (Test-Path -LiteralPath $dest -PathType Leaf)
  if (-not $needed) {
   $needed = ((Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash)
  }
  if ($needed) {
   Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
   $updated++
   Write-Host ('Synkroniseret: docs/Dropbox/' + $relative.Replace('\','/'))
  }
 }
 if ($updated -eq 0) { Write-Host 'Alle filer er allerede synkroniseret.'; return }
 RunGit @('add','--','docs/Dropbox')
 & git diff --cached --quiet
 if ($LASTEXITCODE -eq 0) { Write-Host 'Ingen Git-ændringer.'; return }
 if ($LASTEXITCODE -ne 1) { throw 'Fejl ved kontrollen af staged ændringer.' }
 RunGit @('commit','-m',('Sync Dropbox research ' + (Get-Date -Format 'yyyy-MM-dd HH:mm')))
 RunGit @('push','origin','main')
 Write-Host "OK: $updated fil(er) synkroniseret."
}
finally { Pop-Location }
