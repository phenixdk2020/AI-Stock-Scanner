"""Byg en versionsmærket WordPress-plugin-ZIP fra repository.

Ingen GitHub Actions, netværk eller eksterne afhængigheder.
Kør fra Git-klonen: python scripts/build_wp_package.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent.parent
SLUG = "hangar18-ai-stock-scanner"
PLUGIN = ROOT / "wordpress" / SLUG
MAIN = PLUGIN / (SLUG + ".php")
DIST = ROOT / "dist"
TEXT_SUFFIXES = {".php", ".css", ".js", ".json", ".txt", ".md", ".csv"}


def build_package() -> tuple[Path, dict]:
    if not MAIN.is_file():
        raise FileNotFoundError(MAIN)
    code = MAIN.read_text(encoding="utf-8")
    match = re.search(r"^\s*\* Version:\s*(\d+\.\d+\.\d+)\s*$", code, re.MULTILINE)
    define = re.search(r"define\('ASC_PLUGIN_VERSION',\s*'(\d+\.\d+\.\d+)'\)", code)
    if not match or not define or match.group(1) != define.group(1):
        raise ValueError("Plugin header version matches not ASC_PLUGIN_VERSION")
    version = match.group(1)
    files = sorted(p for p in PLUGIN.rglob("*") if p.is_file())
    if len(files) < 2:
        raise ValueError("Plugin skal mindst indeholde PHP og CSS")
    DIST.mkdir(parents=True, exist_ok=True)
    target = DIST / f"{SLUG}-v{version}.zip"
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as out:
        for file in files:
            relative = file.relative_to(PLUGIN).as_posix()
            if any(segment in ("..", ".git", "__pycache__") for segment in relative.split("/")):
                raise ValueError("Ugyldig sti til plugin")
            info = ZipInfo(f"{SLUG}/{relative}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            data = file.read_bytes()
            if file.suffix.lower() in TEXT_SUFFIXES:
                data = data.replace(b"\r\n", b"\n")  # samme ZIP uanset Windows-checkout (core.autocrlf)
            out.writestr(info, data)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {"slug": SLUG, "version": version,
                "filename": target.name, "sha256": digest, "source": "local-package"}
    (DIST / f"{SLUG}-v{version}.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return target, manifest


if __name__ == "__main__":
    file, meta = build_package()
    print(f"WordPress ZIP: {file}")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
