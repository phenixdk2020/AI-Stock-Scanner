"""Sikker, manuel GitHub-opdatering af den lokale Streamlit-scanner.

Privat repository: Git Credential Manager eller SSH klarer login.
Denne funktion opdaterer ikke WordPress-pluginfiler på hangar18.dk.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from stockscanner.storage import DB_PATH, WATCHLIST_PATH

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "backups"


@dataclass(frozen=True)
class UpdateStatus:
    current: str
    remote: str
    behind: int


def authorized(token: str) -> bool:
    secret = os.environ.get("STOCKSCANNER_ADMIN_TOKEN", "")
    return len(secret) >= 20 and hmac.compare_digest(token, secret)


def trusted_origin(value: str) -> bool:
    return bool(re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
        r"phenixdk2020/AI-Stock-Scanner(?:\.git)?/?",
        value.strip(), re.IGNORECASE,
    ))


def git(*args: str, allow_nonzero: bool = False) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT, env=environment,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Git er ikke tilgængelig eller svarede ikke.") from error
    if proc.returncode != 0 and not allow_nonzero:
        raise RuntimeError("Git-fejl. Kontrollér adgang til det private repository.")
    return proc


def check_update() -> UpdateStatus:
    root = Path(git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if root != ROOT.resolve():
        raise RuntimeError("Programmet skal køres fra sin originale Git-klon.")
    if not trusted_origin(git("remote", "get-url", "origin").stdout):
        raise RuntimeError("Git origin er ikke AI-Stock-Scanner på den tilladte GitHub-konto.")
    if git("branch", "--show-current").stdout.strip() != "main":
        raise RuntimeError("Automatisk opdatering kræver main-branch.")
    if git("status", "--porcelain").stdout.strip():
        raise RuntimeError("Der findes lokale, ikke-gemte ændringer. Opdatering afbrudt.")
    git("fetch", "--no-tags", "origin", "main")
    current = git("rev-parse", "HEAD").stdout.strip()
    remote = git("rev-parse", "refs/remotes/origin/main").stdout.strip()
    if git("merge-base", "--is-ancestor", current, remote, allow_nonzero=True).returncode != 0:
        raise RuntimeError("Historikken er ikke fast-forward-kompatibel. Manuel gennemgang kræves.")
    behind = int(git("rev-list", "--count", current + ".." + remote).stdout.strip())
    return UpdateStatus(current=current, remote=remote, behind=behind)


def backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filename = BACKUP_DIR / ("stockscanner-" + timestamp + ".zip")
    with tempfile.TemporaryDirectory(prefix="stockscanner-backup-") as work:
        temp = Path(work)
        copies: list[tuple[Path, str]] = []
        if DB_PATH.is_file():
            saved_db = temp / "scans.sqlite3"
            with sqlite3.connect("file:" + DB_PATH.resolve().as_posix() + "?mode=ro", uri=True) as original:
                with sqlite3.connect(saved_db) as copied:
                    original.backup(copied)
            copies.append((saved_db, "data/scans.sqlite3"))
        if WATCHLIST_PATH.is_file():
            saved_list = temp / "watchlist.txt"
            shutil.copy2(WATCHLIST_PATH, saved_list)
            copies.append((saved_list, "data/watchlist.txt"))
        with ZipFile(filename, "x", compression=ZIP_DEFLATED) as archive:
            archive.writestr("backup.json", json.dumps({"created_utc": timestamp}))
            for source, destination in copies:
                archive.write(source, destination)
    return filename


def install_update(remote_commit: str, token: str) -> Path:
    if not authorized(token):
        raise PermissionError("Administratortoken mangler eller er forkert.")
    status = check_update()
    if not re.fullmatch(r"[0-9a-f]{40}", remote_commit) or remote_commit != status.remote:
        raise RuntimeError("GitHub er ændret. Tjek opdateringer igen.")
    if status.behind == 0:
        raise RuntimeError("Der findes ingen opdatering.")
    saved = backup()
    git("merge", "--ff-only", remote_commit)
    return saved
