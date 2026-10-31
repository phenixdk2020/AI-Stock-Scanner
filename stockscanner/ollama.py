"""Valgfri lokal AI-forklaring via Ollama; ingen cloud-API-nøgle."""
from __future__ import annotations

from dataclasses import asdict
import json

import requests

from stockscanner.core import ScanResult


def explain(result: ScanResult, model: str = "qwen3.5:9b") -> str:
    if not model.strip():
        raise ValueError("Angiv navnet på en installeret Ollama-model.")
    prompt = (
        "Du er en forsigtig analytiker. Svar på dansk. Giv en kort, "
        "faktabaseret forklaring på højst 250 ord af følgende TEKNISKE "
        "aktiescanning. Angiv 2 styrker, 2 risici og hvad data ikke siger. "
        "Du har IKKE nyheder, regnskab, intradagkurser eller pålidelig "
        "værdiansættelse. Opfind ingen informationer eller kursmål. "
        "Dette er ikke personlig investeringsrådgivning.\n\n"
        + json.dumps(asdict(result), ensure_ascii=False, indent=2)
    )
    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={"model": model.strip(), "prompt": prompt, "stream": False},
        timeout=180,
    )
    response.raise_for_status()
    text = str(response.json().get("response") or "").strip()
    if not text:
        raise ValueError("Ollama returnerede intet svar.")
    return text
