"""Bear/Base/Bull for hele universet (ikke kun mandagslisten), cachet i `data/universe_scenarios.json`.

Bygges ugentligt af scripts/build_universe.py (ca. 1,5 sekund pr. aktie), eller med
`python -m stockscanner.universe_scenarios`. Aktier uden estimater eller P/E-historik får ingen tal.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stockscanner.playbook import scenarios_entry
from stockscanner.valuation import DEFAULT_HORIZON, fetch_inputs, value_channel

FILE = Path(__file__).resolve().parent.parent / "data" / "universe_scenarios.json"
MAX_AGE_DAYS = 14
PAUSE = 0.2     # sekunder mellem aktierne af hensyn til Yahoo


def build(tickers, currencies: dict, channel_of=None, path: Path = FILE, pause: float = PAUSE) -> dict:
    """Scenarier pr. ticker; en aktie der fejler eller mangler data springes over, og resten fortsætter."""
    channel_of = channel_of or (lambda ticker: value_channel(fetch_inputs(ticker)))
    result = {}
    for ticker in tickers:
        try:
            entry = scenarios_entry(channel_of(ticker), currencies.get(ticker), DEFAULT_HORIZON)
        except Exception:
            entry = None
        if entry is not None:
            result[ticker] = entry
        if pause:
            time.sleep(pause)
    if result:      # en fejlet kørsel (fx Yahoo-spærring) må ikke slette sidste uges tal
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps({"built": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scenarios": result},
                                   ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)
    return result


def load(path: Path = FILE, max_age_days: int = MAX_AGE_DAYS, now: datetime | None = None) -> dict:
    """Cachens scenarier; tom når filen mangler, er ugyldig eller er for gammel (forældede kursmål vises ikke)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        built = datetime.fromisoformat(data["built"])
        scenarios = data["scenarios"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    if (now or datetime.now(timezone.utc)) - built > timedelta(days=max_age_days) or not isinstance(scenarios, dict):
        return {}
    return scenarios


if __name__ == "__main__":
    from stockscanner import universe

    sys.stdout.reconfigure(encoding="utf-8")
    frame = universe.load()
    names = universe.read_tickers()
    money = {} if frame is None or "x_currency" not in frame.columns else frame["x_currency"].dropna().to_dict()
    done = build(names, money)
    print(f"Bear/Base/Bull: {len(done)} af {len(names)} aktier → {FILE}")
