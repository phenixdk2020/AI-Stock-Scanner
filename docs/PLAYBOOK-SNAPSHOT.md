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
      "tpi": "grøn/neutral", "mti": "uge grøn", "size": "Mega", "liquidity": "Høj", "sector": "Teknologi",
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
                "quality_r", "value_r", "momentum_r", "moat_r", "upside", "peg", "mcap_usd_bn", "size", "liquidity", "sector"],
    "rows": [["MSFT", "USA", 82, 13, 51, 95, 80, 20, 55, 93, 12.5, 2.1, 3870, "Mega", "Høj", "Teknologi"]]
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
  "paper_score": {"antal": 6, "sammenlignet": 5, "udeladt": 1, "afkast_pct": 4.2, "rsp_pct": 2.9, "forskel_pp": 1.3,
                  "vinderandel_pct": 60.0, "slaar_rsp_pct": 40.0, "start": "2026-11-02", "dage": 41, "for_tidligt": true},
  "changes": ["MSFT: handling: hold øje → pil ned"]
}
```

- Tal kan være `null`. `*_r`-kolonnerne er percentiler inden for regionen (som MSS); de andre er mod hele universet.
- `size` (plugin ≥ 0.7.1 viser den): Mega over 200 mia. USD, Large 10–200, Mid 2–10, Small 0,3–2, Micro under 0,3, ellers "ukendt".
  `liquidity`: Høj (≥ 20 mio. USD i gennemsnitlig dagsomsætning de seneste 21 dage), Middel, Lav (under 2 mio. eller over 2 dage
  uden handel) eller "ukendt". Aktier med `Lav` bliver aldrig køb-kandidater (begrundelse "for lidt handel"); ejede aktier rammes ikke.
  Begge felter er additive (skema stadig 2): et ældre plugin ignorerer ukendte stock-felter og universkolonner, og en ældre
  scanner uden dem får "–" i det nye plugin.
- `sector` (plugin ≥ 0.8.4, additivt; skema stadig 2): aktiens sektor på dansk (Teknologi, Finans, Sundhed, Cyklisk forbrug, Defensivt forbrug,
  Energi, Industri, Råvarer, Forsyning, Ejendomme, Kommunikation; ukendte Yahoo-navne uændret, manglende som "ukendt"). Kilde: `x_sector`
  (yfinance `info['sector']`) i universet, så den kommer med ved næste kørsel af `scripts/build_universe.py`; for aktier hvor kolonnen mangler er
  fallback `data/sector_map.json` (`sector_rs.sector_name`). Både `stocks[..].sector` og sidste kolonne i `universe`. Et ældre snapshot uden
  feltet tåles: pluginet viser "ukendt". **Spredningsadvarslen** (kun en advarsel, ændrer aldrig `action` eller KØB-KANDIDAT-reglerne) beregnes i
  pluginet ud fra feltet: aktier med entry (Find aktier og Overblik) og købskandidater på mandagslisten, hvis flere end 3 eller over 40 % (mindst 4 i alt)
  ligger i samme sektor; brugerens egne positioner i simulatoren og porteføljen, hvis over 40 % (mindst 4 positioner) gør det. "ukendt" tæller med i
  nævneren, men giver aldrig selv en advarsel.
- `paper_score` (plugin ≥ 0.8.4, additivt; `null` uden beregning): papirporteføljens stilling mod RSP, beregnet af `paper.score` ud fra handlerne (lige store
  beløb pr. handel, afkast i aktiens egen valuta, ikke omregnet). Pr. handel: gevinst i % (lukkede til salgskurs, åbne til seneste kurs) og RSP fra købsdato til
  salgsdato (åbne: RSP's seneste kursdato). En handel uden kurs eller uden RSP-kurs (højst 7 dage før datoen) udelades af sammenligningen og tælles i
  `udeladt`; gennemsnit (`afkast_pct`, `rsp_pct`, `forskel_pp` i %-point) og `vinderandel_pct` gælder kun de `sammenlignet` handler, `slaar_rsp_pct` er andelen
  der slog RSP. `start` er første købsdato, `dage` dage siden, `for_tidligt` er sand under 90 dage (pluginet skriver "Under 3 måneder siger tallene ikke noget.").
  Hver kørsel gemmer også én linje i `data/papir_stilling.csv` (`dato;antal;gns_afkast;gns_rsp;forskel`; samme dato overskrives).
- `earnings_risk` (plugin ≥ 0.7.1, additivt; kun med når regnskabet er højst 14 dage væk): `level` Lav/Middel/Høj
  (0 point = Lav, 1 = Middel, 2-3 = Høj), `points`, `reasons` (inkl. "ingen data" for manglende estimater, nyheder eller kurser),
  `avg_move_pct` (gennemsnitlig absolut kursbevægelse over de seneste op til 8 regnskaber), `down_share_pct` (andel fald), `count`
  (antal regnskaber). Med under 4 regnskaber er de to første `null` og `note` er "for få regnskaber". Feltet ændrer aldrig `action`;
  det er et risikomål, ikke et salgssignal. Uden feltet viser pluginet intet. Pluginet beregner nedtællingen til `earnings` selv ved hver
  sidevisning (rød inden for 7 dage; en KØB-KANDIDAT får "spærret: regnskab"; manglende dato vises som "Dato ukendt").
  En køb-kandidat uden kendt regnskabsdato får begrundelsen "regnskabsdato ukendt" i `reasons`.
- Topniveau `scenarios` (plugin ≥ 0.8.1, additivt): samme felter pr. ticker for universets aktier uden for `stocks`, fra `data/universe_scenarios.json` (`stockscanner/universe_scenarios.py`, bygges ugentligt).
- `scenarios` (plugin ≥ 0.8.1, additivt; skema stadig 2): automatisk Bear/Base/Bull fra `valuation.ValueChannel`. Kun med når kanalen har
  mindst ét scenariepris; aktier uden kanal (manglende EPS-estimater eller P/E-historik) får intet felt, og pluginet siger "Ikke beregnet endnu".
  Kursmål = `eps_horizon` × `pe` for hvert scenarie, dvs. et regnestykke ud fra historiske P/E og analytikernes estimater, ikke en prognose.
  ```json
  "scenarios": {"currency": "USD", "horizon_years": 2.0, "price": 60.0, "eps_today": 4.0, "eps_horizon": 5.0,
                "pe": {"bear": 10.0, "base": 15.0, "bull": 20.0},
                "prices": {"bear": 50.0, "base": 75.0, "bull": 100.0},
                "upside_pct": {"bear": -16.7, "base": 25.0, "bull": 66.7},
                "cagr_pct": {"bear": -8.7, "base": 11.8, "bull": 29.1},
                "asymmetry": 1.5, "asymmetry_inf": false, "peg": 1.2, "notes": ["Under 3 års P/E-historik"]}
  ```
  Alle tal kan være `null` (NaN og uendelige tal sendes aldrig); `asymmetry_inf: true` når kursen ligger under bear-linjen. `notes`: højst 6
  tekster på højst 160 tegn. Pluginet renser pr. felt (tal inden for grænser, valuta på 3 bogstaver) og viser tre kort i analysepanelet
  (aktiesiden og simulatorens opslag) samt på Analyse-siden, hvor EPS og de tre P/E også udfylder den manuelle beregner.
- Flere brugere (plugin ≥ 0.8.1): snapshottet er fælles og indeholder alle symboler, scanneren analyserer, men pluginet viser pr. bruger kun
  `research`, `candidates` og det, brugeren selv følger, ejer (WordPress-porteføljen) eller har i simulatoren. `action` "BEHOLD (ejet)"/"SÆLG (ejet)"
  og "% siden køb" i `reasons` stammer fra scannerens egen lokale portefølje; pluginet regner dem om pr. bruger ud fra brugerens egne køb
  (`exit`-fakta + købsdato) og viser "hold øje" for aktier, brugeren ikke selv ejer. "(ejet)"-ændringer i `changes` vises ikke, og `paper` er fælles.
- `asymmetry_inf: true` betyder, at kursen ligger under bear-linjen (ingen nedside).
- `exit.sma50_breaks` og `exit.supertrend_flips`: datoer for brud det seneste år. En ejet aktie har salgsregel ramt, hvis
  `stockmap_sell` er sand, hvis SMA50 er brudt EFTER købsdatoen, eller hvis Supertrend er vendt ned efter købsdatoen og stadig peger ned
  (samme regel som `portfolio.exit_check`).
- Positionsstørrelse på siden: stop = `price − 3 × atr14`; antal = min(kapital × risiko % / (price − stop),
  kapital × maks % / price), omregnet med pluginets ECB-kurser. Kapital, valuta, risiko og maks gemmes pr. bruger.
- `news` (plugin ≥ 0.6.1): højst 5 overskrifter fra Google News (kun til personlig brug), vurderet af lokal Ollama.
  `impact` 1–3; en stor negativ nyhed de seneste 3 dage blokerer køb, når de negative overskrifter er flest.
- Screening, ikke købs- eller salgsanbefalinger – det skal stå på siden.
