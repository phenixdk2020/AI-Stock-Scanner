# Playbook-snapshot (schema 2): PC → aktier.hangar18.dk

Hver gang mandagslisten kører på PC'en (Windows-opgaven mandag kl. 8 eller knappen i appen), sender
`stockscanner/site_sync.py` et samlet snapshot til WordPress. WordPress regner ikke selv scores ud; den
viser snapshottet og laver kun det, der afhænger af den enkelte bruger (købsdato, kapital).
Alt vises kun for indloggede brugere.

## Endpoints (plugin ≥ 0.6.0)

| Metode | Sti | Adgang | Formål |
|---|---|---|---|
| GET | `/wp-json/ai-stock-scanner/v1/tickers` | `asc_sync` (Application Password) | Unikke tickere fra alle brugeres watchlists og porteføljer (ingen brugerdata) |
| POST | `/wp-json/ai-stock-scanner/v1/playbook` | `asc_sync` | Gem snapshottet (højst 3 MB JSON) i option `asc_playbook_v2` (autoload nej) |

PC'en henter først `/tickers`, så mandagslisten også dækker aktier, brugerne følger eller ejer.

## Format

```json
{
  "schema_version": 2,
  "generated_at": "2026-11-02T07:12:00Z",
  "market_date": "2026-10-30",
  "benchmark": "RSP",
  "breadth": {"20": 68.1, "50": 59.0, "200": 61.2},
  "research": ["MSFT", "V", "..."],
  "stocks": {
    "MSFT": {
      "region": "USA", "currency": "USD", "price": 520.17, "atr14": 11.76,
      "action": "pil ned", "reasons": "StockMap-salg denne uge (ikke ejet)",
      "stockmap": "salg 2026-10-30", "quadrant": "gul", "angle": 212.0,
      "tpi": "grøn/neutral", "mti": "uge grøn",
      "quality": 82, "moat": 95, "mss_score": 92, "value_pct": 13, "momentum": 51,
      "channel_score": 115, "peg": 1.0, "asymmetry": null, "asymmetry_inf": true,
      "earnings": "2027-01-27", "eps_trend": null,
      "exit": {"supertrend_down": false, "sma50_breaks": ["2026-10-14"], "stockmap_sell": true}
    }
  },
  "universe": {
    "columns": ["ticker", "region", "quality", "value", "momentum", "moat",
                "quality_r", "value_r", "momentum_r", "moat_r", "upside", "peg", "mcap_usd_bn"],
    "rows": [["MSFT", "USA", 82, 13, 51, 95, 80, 20, 55, 93, 12.5, 2.1, 3870]]
  },
  "screeners": {
    "triple-green": {"label": "...", "global": ["INVE-B.ST"], "regional": ["INVE-B.ST"]},
    "tpi-trend": {"label": "...", "global": [], "regional": []},
    "stock-of-the-day": {"label": "...", "global": [], "regional": []}
  },
  "paper": {
    "summary": {"handler": 0, "aabne": 0, "afkast_pct": null, "vundne_pct": null},
    "trades": [{"ticker": "X", "koebsdato": "2026-11-02", "koebskurs": 10.0, "salgsdato": null,
                "salgskurs": null, "salgsgrund": null, "seneste": 10.4}]
  },
  "changes": ["MSFT: handling: hold øje → pil ned"]
}
```

- Tal kan være `null`. `*_r`-kolonnerne er percentiler inden for regionen (som MSS); de andre er mod hele universet.
- `asymmetry_inf: true` betyder, at kursen ligger under bear-linjen (ingen nedside).
- `exit.sma50_breaks`: datoer for brud under SMA50 det seneste år. En ejet aktie har salgsregel ramt, hvis
  `supertrend_down` eller `stockmap_sell` er sand, eller hvis et brud ligger på eller efter brugerens købsdato
  (samme regel som `portfolio.exit_check`).
- Positionsstørrelse på siden: stop = `price − 3 × atr14`; antal = min(kapital × risiko % / (price − stop),
  kapital × maks % / price), omregnet med pluginets ECB-kurser. Kapital, valuta, risiko og maks gemmes pr. bruger.
- Screening, ikke købs- eller salgsanbefalinger – det skal stå på siden.
