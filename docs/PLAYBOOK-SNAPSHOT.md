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
      "tpi": "grøn/neutral", "mti": "uge grøn", "size": "Mega", "liquidity": "Høj",
      "quality": 82, "moat": 95, "mss_score": 92, "value_pct": 13, "momentum": 51,
      "channel_score": 115, "peg": 1.0, "asymmetry": null, "asymmetry_inf": true,
      "earnings": "2027-01-27", "eps_trend": null,
      "earnings_risk": {"level": "Høj", "points": 2, "reasons": ["analytikerne har sænket estimaterne de seneste 30 dage", "nyheder: ingen data"],
                        "avg_move_pct": 8.1, "down_share_pct": 62, "count": 8, "note": null},
      "exit": {"supertrend_down": false, "sma50_breaks": ["2026-10-14"], "stockmap_sell": true},
      "news_summary": "nyheder: 5+ 0−; stor positiv nyhed: …",
      "news": [{"title": "…", "source": "Børsen", "url": "https://…", "published": "2026-11-02",
                "sentiment": "positiv", "impact": 3, "reason": "…"}]
    }
  },
  "universe": {
    "columns": ["ticker", "region", "quality", "value", "momentum", "moat",
                "quality_r", "value_r", "momentum_r", "moat_r", "upside", "peg", "mcap_usd_bn", "size", "liquidity"],
    "rows": [["MSFT", "USA", 82, 13, 51, 95, 80, 20, 55, 93, 12.5, 2.1, 3870, "Mega", "Høj"]]
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
- `size` (plugin ≥ 0.7.1 viser den): Mega over 200 mia. USD, Large 10–200, Mid 2–10, Small 0,3–2, Micro under 0,3, ellers "ukendt".
  `liquidity`: Høj (≥ 20 mio. USD i gennemsnitlig dagsomsætning de seneste 21 dage), Middel, Lav (under 2 mio. eller over 2 dage
  uden handel) eller "ukendt". Aktier med `Lav` bliver aldrig køb-kandidater (begrundelse "for lidt handel"); ejede aktier rammes ikke.
  Begge felter er additive (skema stadig 2): et ældre plugin ignorerer ukendte stock-felter og universkolonner, og en ældre
  scanner uden dem får "–" i det nye plugin.
- `earnings_risk` (plugin ≥ 0.7.1, additivt; kun med når regnskabet er højst 14 dage væk): `level` Lav/Middel/Høj
  (0 point = Lav, 1 = Middel, 2-3 = Høj), `points`, `reasons` (inkl. "ingen data" for manglende estimater, nyheder eller kurser),
  `avg_move_pct` (gennemsnitlig absolut kursbevægelse over de seneste op til 8 regnskaber), `down_share_pct` (andel fald), `count`
  (antal regnskaber). Med under 4 regnskaber er de to første `null` og `note` er "for få regnskaber". Feltet ændrer aldrig `action`;
  det er et risikomål, ikke et salgssignal. Uden feltet viser pluginet intet. Pluginet beregner nedtællingen til `earnings` selv ved hver
  sidevisning (rød inden for 7 dage; en KØB-KANDIDAT får "spærret: regnskab"; manglende dato vises som "Dato ukendt").
  En køb-kandidat uden kendt regnskabsdato får begrundelsen "regnskabsdato ukendt" i `reasons`.
- `asymmetry_inf: true` betyder, at kursen ligger under bear-linjen (ingen nedside).
- `exit.sma50_breaks` og `exit.supertrend_flips`: datoer for brud det seneste år. En ejet aktie har salgsregel ramt, hvis
  `stockmap_sell` er sand, hvis SMA50 er brudt EFTER købsdatoen, eller hvis Supertrend er vendt ned efter købsdatoen og stadig peger ned
  (samme regel som `portfolio.exit_check`).
- Positionsstørrelse på siden: stop = `price − 3 × atr14`; antal = min(kapital × risiko % / (price − stop),
  kapital × maks % / price), omregnet med pluginets ECB-kurser. Kapital, valuta, risiko og maks gemmes pr. bruger.
- `news` (plugin ≥ 0.6.1): højst 5 overskrifter fra Google News (kun til personlig brug), vurderet af lokal Ollama.
  `impact` 1–3; en stor negativ nyhed de seneste 3 dage blokerer køb, når de negative overskrifter er flest.
- Screening, ikke købs- eller salgsanbefalinger – det skal stå på siden.
