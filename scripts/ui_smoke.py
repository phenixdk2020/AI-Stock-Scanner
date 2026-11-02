"""Røgtest af Streamlit-appen med Playwright (headless Chromium).

Kør med serveren styret af webapp-testing-skillens hjælper, fx:
  python ~/.claude/skills/webapp-testing/scripts/with_server.py \
    --server ".venv/Scripts/python.exe -m streamlit run app.py --server.port 8518 --server.headless true" \
    --port 8518 --timeout 60 -- .venv/Scripts/python.exe scripts/ui_smoke.py
Henter kursdata og regnskabstal via yfinance (netværk). Skærmbillede: data/ui_smoke.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8518"
SHOT = Path(__file__).resolve().parent.parent / "data" / "ui_smoke.png"


def main() -> int:
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        page.get_by_text("AI-Stock-Scanner").first.wait_for(timeout=30000)

        page.get_by_role("button", name="Scan nu").click()
        page.get_by_text("Analyserede aktier").wait_for(timeout=120000)
        if not page.get_by_text("Resultater").count():
            failures.append("Ingen resultattabel efter scanning")

        page.get_by_role("button", name="Hent regnskabstal og beregn kvalitet").click()
        try:
            page.get_by_text("Kvalitetsscore").first.wait_for(timeout=120000)
        except Exception:
            failures.append("Kvalitetsscore blev ikke vist")

        SHOT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT), full_page=True)
        exceptions = page.locator("[data-testid='stException']").count()
        if exceptions:
            failures.append(f"{exceptions} Streamlit-fejl på siden")
        if errors:
            failures.append(f"JavaScript-fejl: {errors[:3]}")
        browser.close()

    print("OK – scanning og kvalitetsvisning virker" if not failures else "FEJL: " + "; ".join(failures))
    print(f"Skærmbillede: {SHOT}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
