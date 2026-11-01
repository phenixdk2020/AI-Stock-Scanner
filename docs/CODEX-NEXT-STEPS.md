# AI-Stock-Scanner – Codex-handoff for v0.4.0

## Vision
WordPress at `https://aktier.hangar18.dk` is the independent user-facing stock portfolio.
Windows scanner at `C:\AI-Stock-Scanner` is optional for analysis and historical data.
The user does not want extra paid subscriptions or metered API costs.

## Delivered in v0.4.0
- WordPress login form for signed-out visitors; uses existing WordPress accounts.
- Private per-user portfolio, acquisition lots, purchase price, quantity, currency and date.
- Manual price at creation, editable lots and manual quote updates for immediate P/L.
- Per-currency invested/market value (portfolio net worth), total shares and P/L.
- Personal CSV export with nonce and formula-injection prevention.
- Private personal watchlist with add/delete, up to 50 symbols.
- Optional experimental Yahoo quote integration, disabled by default, throttled/cached.
- Candlestick SVG from sanitized daily OHLCV over up to six months.
- Average daily shares traded and approximate daily traded value (close × volume) over
  last 5 and 21 valid sessions, plus volume-surge alert where 5d >= 1.5× 21d.
- WordPress admin-only button to create and select the homepage (not automatic).

## Known limits and priorities for Codex
1. **Critical:** Yahoo chart endpoint is undocumented, not licensed for redistribution by default.
   Keep it optional and private; investigate legal and stable data feeds before public production.
2. Automatic quotes may be delayed or unavailable. Show timestamps/source; no invented values.
3. Book equity/net worth and shares outstanding are **not available** from OHLCV.
   Portfolio net worth is held securities' quoted value, not personal total wealth.
4. Estimate `closing_price * daily_volume` is *not* exchange-reported trade turnover.
5. Price totals intentionally remain by currency. FX conversion requires legitimate FX source.
6. No sale lots, fees, dividends, splits, realized gains, tax lots, or corporate actions yet;
   design a trade ledger/migrations before adding these.
7. Full WP browser and live-host tests still needed; GitHub Actions currently runs PHP lint
   and offline Python regression tests, not WordPress integration or live quote tests.
8. Use a proper `WP_UnitTestCase` suite for user isolation, nonce, redirects, CSV and hooks.
9. Cache personalized HTML carefully; exclude private pages from shared/public full-page cache.
10. Remove experimental Yahoo feed or disable it if provider TOS/data license prohibits use.
11. Add legal handling of market cap, shares outstanding, equity and sector metadata only
    after acquiring licensed fundamentals; do not infer these metrics from candle data.
12. Improve market source adapters, localization, accessibility, mobile charts, user feedback,
    and validation with Codex in focused PRs.

## Chinese GitHub inspiration
Earlier review referred to `hyan1985/ai-stock-scanner` and to sector-first scanning
ideas. Existing local Python module `stockscanner/sectors.py` already covers sampled
watchlist sector ranking, overheated/under-pressure flags and volume-aware status.
No Tushare dependency or copied third-party source was added.

## Build, test, install
- Local Windows checkout: `C:\AI-Stock-Scanner`.
- WordPress plugin root: `wordpress/hangar18-ai-stock-scanner/`.
- Run `python -m unittest discover -s tests -v`, `php -l` on all PHP files.
- Release file: `dist/hangar18-ai-stock-scanner-v0.4.0.zip`; `update.json`
  contains matching hash, slug and version for the existing WordPress updater.
- On WP admin: Plugins > AI Stock Scanner > Opdateringer; then
  AI Stock Scanner > Oversigt > `Opret porteføljeside og sæt som forside`.
- Users login with *regular WordPress password*, not Application Password.
- Python sync credentials are only for `stockscanner.site_sync`; the user's
  `asc_auth_failed` issue is separate and does not block website portfolio features.
