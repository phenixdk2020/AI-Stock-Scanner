<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Playbook-snapshot (schema 2) sent by the local PC app after each run.
 * WordPress only stores and displays it; per-user parts (watchlist, buy date,
 * capital) are the only things computed here. Screening, not advice.
 */
final class ASC_Playbook {
    public const OPTION = 'asc_playbook_v2';
    private const SIZING_META = 'asc_sizing_v1';
    private const WATCH_META = 'asc_watchlist_v1';
    private const PORTFOLIO_META = 'asc_portfolio_positions_v1';
    private const SIM_META = 'asc_simulator_v1';
    private const BENCHMARK_TICKER = 'RSP';
    private const TICKER_RE = '/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D';
    private const DATE_RE = '/^\d{4}-\d\d-\d\d$/D';
    private const MAX_BODY = 3145728;
    private const MAX_STOCKS = 600;
    private const MAX_UNIVERSE = 2000;
    private const MAX_TRADES = 1000;
    private const UNIVERSE_COLUMNS = [
        'ticker', 'region', 'quality', 'value', 'momentum', 'moat',
        'quality_r', 'value_r', 'momentum_r', 'moat_r', 'upside', 'peg', 'mcap_usd_bn',
        'size', 'liquidity', 'sector',
    ];
    private const SECTOR_UNKNOWN = 'ukendt';
    private const SECTOR_MAX_ENTRIES = 3;      // flere end 3 aktier med entry i samme sektor giver en advarsel
    private const SECTOR_SHARE = 0.4;          // ... og det samme gør over 40 % af aktierne (eller positionerne)
    private const SECTOR_MIN_TOTAL = 4;        // procentreglen kræver mindst så mange aktier eller positioner
    private const PAPER_EARLY_NOTE = 'Under 3 måneder siger tallene ikke noget.';
    private const EARNINGS_BLOCK_DAYS = 7; // som EARNINGS_BLOCK_DAYS i stockscanner/analyst.py
    private const RISK_LEVELS = ['Lav', 'Middel', 'Høj'];
    private const RISK_DISCLAIMER = 'Risikomål, ikke et salgssignal.';
    private const SCREENERS = ['triple-green', 'tpi-trend', 'stock-of-the-day'];
    private const OWNED_ACTIONS = ['BEHOLD (ejet)', 'SÆLG (ejet)'];
    private const SCENARIO_KEYS = ['bear' => 'Bear', 'base' => 'Base', 'bull' => 'Bull'];
    private const CURRENCIES = ['DKK', 'SEK', 'NOK', 'EUR', 'USD'];
    private const ACTION_ORDER = [
        'SÆLG (ejet)' => 0,
        'KØB-KANDIDAT' => 1,
        'BEHOLD (ejet)' => 2,
        'pil ned' => 3,
        'hold øje' => 4,
    ];
    private static ?array $cached = null;
    private static bool $cache_loaded = false;

    public static function register(): void {
        add_shortcode('ai_stock_playbook', [self::class, 'render']);
        add_action('rest_api_init', [self::class, 'register_routes']);
        add_action('admin_post_asc_sizing_save', [self::class, 'save_sizing']);
    }

    // ------------------------------------------------------------------ REST

    public static function register_routes(): void {
        // Same permission check as the scanner routes (asc_sync, incl. header fallback).
        register_rest_route('ai-stock-scanner/v1', '/tickers', [
            'methods'             => 'GET',
            'callback'            => [self::class, 'rest_tickers'],
            'permission_callback' => 'asc_snapshot_permission',
        ]);
        register_rest_route('ai-stock-scanner/v1', '/playbook', [
            'methods'             => 'POST',
            'callback'            => [self::class, 'rest_accept'],
            'permission_callback' => 'asc_snapshot_permission',
        ]);
    }

    /** Sorted unique symbols from all users' watchlists and portfolios. No user data. */
    public static function rest_tickers(WP_REST_Request $request) {
        return rest_ensure_response(['tickers' => self::followed_tickers()]);
    }

    /** @return string[] Unikke symboler fra alle brugeres watchlists, porteføljer og simulator-positioner samt RSP (ingen brugerdata). */
    public static function followed_tickers(): array {
        global $wpdb;
        $found = $wpdb->get_results(
            $wpdb->prepare(
                "SELECT meta_key, meta_value FROM {$wpdb->usermeta} WHERE meta_key IN (%s, %s, %s)",
                self::WATCH_META,
                self::PORTFOLIO_META,
                self::SIM_META
            ),
            ARRAY_A
        );
        // Simulator-benchmark: RSP følges altid, så startkursen og afkastet kan beregnes.
        $symbols = [self::BENCHMARK_TICKER => true];
        foreach (is_array($found) ? $found : [] as $row) {
            $value = maybe_unserialize($row['meta_value'] ?? '');
            if (!is_array($value)) { continue; }
            if (($row['meta_key'] ?? '') === self::SIM_META) {
                // Kun symbolerne i den aktuelle rundes åbne positioner – ingen øvrige brugerdata.
                $sim_positions = is_array($value['round']['positions'] ?? null) ? $value['round']['positions'] : [];
                foreach ($sim_positions as $sim_position) {
                    $sim_ticker = is_array($sim_position) ? ($sim_position['ticker'] ?? null) : null;
                    if (is_string($sim_ticker) && preg_match(self::TICKER_RE, $sim_ticker) === 1) {
                        $symbols[$sim_ticker] = true;
                    }
                }
                continue;
            }
            foreach ($value as $item) {
                if (($row['meta_key'] ?? '') === self::PORTFOLIO_META) {
                    $item = is_array($item) ? ($item['ticker'] ?? null) : null;
                }
                if (is_string($item) && preg_match(self::TICKER_RE, $item) === 1) {
                    $symbols[$item] = true;
                }
            }
        }
        $list = array_map('strval', array_keys($symbols));
        sort($list, SORT_STRING);
        return $list;
    }

    private static function cut(string $value, int $max): string {
        return function_exists('mb_substr') ? mb_substr($value, 0, $max) : substr($value, 0, $max);
    }

    private static function clean_string($value, int $max = 200): ?string {
        if (!is_string($value)) { return null; }
        $clean = trim(sanitize_text_field($value));
        return $clean === '' ? null : self::cut($clean, $max);
    }

    /** @return int|float|null */
    private static function clean_number($value) {
        if (is_int($value)) { return $value; }
        if (is_float($value) && is_finite($value) && abs($value) < 1.0e15) { return $value; }
        return null;
    }

    private static function clean_date($value): ?string {
        if (!is_string($value) || preg_match(self::DATE_RE, $value) !== 1) { return null; }
        $dt = DateTimeImmutable::createFromFormat('!Y-m-d', $value);
        return ($dt && $dt->format('Y-m-d') === $value) ? $value : null;
    }

    private static function clean_ticker($value): ?string {
        if (!is_string($value)) { return null; }
        $ticker = strtoupper(trim($value));
        return preg_match(self::TICKER_RE, $ticker) === 1 ? $ticker : null;
    }

    /** @return string[] */
    private static function clean_ticker_list($value, int $max): array {
        $out = [];
        if (!is_array($value)) { return $out; }
        foreach ($value as $item) {
            $ticker = self::clean_ticker($item);
            if ($ticker !== null) { $out[$ticker] = true; }
            if (count($out) >= $max) { break; }
        }
        // Numeric-looking tickers become integer array keys; keep them strings.
        return array_map('strval', array_keys($out));
    }

    public static function rest_accept(WP_REST_Request $request) {
        if (strlen($request->get_body()) > self::MAX_BODY) {
            return new WP_Error('asc_too_large', 'Payload er for stor.', ['status' => 413]);
        }
        $input = $request->get_json_params();
        if (!is_array($input) || ($input['schema_version'] ?? null) !== 2 ||
            !is_string($input['generated_at'] ?? null) ||
            !is_array($input['stocks'] ?? null)) {
            return new WP_Error('asc_invalid', 'Ugyldigt payload-format.', ['status' => 400]);
        }
        $generated = (string)$input['generated_at'];
        if (preg_match('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/D', $generated) !== 1) {
            return new WP_Error('asc_date', 'Tidspunkt skal være UTC ISO8601.', ['status' => 400]);
        }
        $epoch = strtotime($generated);
        if (!$epoch || $epoch > time() + 300) {
            return new WP_Error('asc_time', 'Tidspunktet ligger i fremtiden.', ['status' => 400]);
        }
        $current = get_option(self::OPTION, []);
        if (is_array($current) && !empty($current['generated_at'])) {
            $previous = strtotime((string)$current['generated_at']);
            if ($previous !== false && $epoch <= $previous) {
                return new WP_Error('asc_replay', 'Playbook er ikke nyere end den seneste.', ['status' => 409]);
            }
        }
        if (count($input['stocks']) > self::MAX_STOCKS) {
            return new WP_Error('asc_count', 'For mange aktier i playbook.', ['status' => 400]);
        }

        $stocks = [];
        foreach ($input['stocks'] as $key => $raw) {
            $ticker = self::clean_ticker((string)$key);
            if ($ticker === null || !is_array($raw)) { continue; }
            $stocks[$ticker] = self::clean_stock($raw);
        }

        $snapshot = [
            'schema_version' => 2,
            'generated_at' => $generated,
            'market_date' => self::clean_date($input['market_date'] ?? null),
            'benchmark' => self::clean_string($input['benchmark'] ?? null, 20),
            'breadth' => self::clean_breadth($input['breadth'] ?? null),
            'research' => self::clean_ticker_list($input['research'] ?? null, self::MAX_STOCKS),
            'candidates' => self::clean_ticker_list($input['candidates'] ?? null, self::MAX_STOCKS),
            'stocks' => $stocks,
            'universe' => self::clean_universe($input['universe'] ?? null),
            'scenarios' => self::clean_scenario_map($input['scenarios'] ?? null),
            'screeners' => self::clean_screeners($input['screeners'] ?? null),
            'paper' => self::clean_paper($input['paper'] ?? null),
            'paper_score' => self::clean_paper_score($input['paper_score'] ?? null),
            'changes' => self::clean_changes($input['changes'] ?? null),
        ];
        update_option(self::OPTION, $snapshot, false);
        self::$cache_loaded = false;
        return rest_ensure_response(['ok' => true, 'stocks' => count($stocks)]);
    }

    private static function clean_stock(array $raw): array {
        $strings = [
            'region' => 40, 'action' => 40, 'reasons' => 400, 'stockmap' => 60,
            'quadrant' => 20, 'tpi' => 60, 'mti' => 60, 'earnings' => 40, 'eps_trend' => 200,
            'news_summary' => 300, 'size' => 20, 'liquidity' => 20, 'sector' => 40,
        ];
        $numbers = [
            'price', 'atr14', 'angle', 'quality', 'moat', 'mss_score', 'value_pct',
            'momentum', 'channel_score', 'peg', 'asymmetry',
        ];
        $out = [];
        foreach ($strings as $field => $max) {
            $out[$field] = self::clean_string($raw[$field] ?? null, $max);
        }
        $currency = is_string($raw['currency'] ?? null) ? strtoupper(trim($raw['currency'])) : '';
        $out['currency'] = preg_match('/^[A-Z]{3}$/D', $currency) === 1 ? $currency : null;
        foreach ($numbers as $field) {
            $out[$field] = self::clean_number($raw[$field] ?? null);
        }
        $out['asymmetry_inf'] = ($raw['asymmetry_inf'] ?? false) === true;
        $exit = is_array($raw['exit'] ?? null) ? $raw['exit'] : [];
        $dates = static function ($raw): array {
            $out = [];
            foreach (is_array($raw) ? $raw : [] as $date) {
                $date = self::clean_date($date);
                if ($date !== null) { $out[] = $date; }
            }
            return array_slice($out, -60); // de seneste brud tæller for salgsreglen
        };
        $out['exit'] = [
            'supertrend_down' => ($exit['supertrend_down'] ?? false) === true,
            'supertrend_flips' => $dates($exit['supertrend_flips'] ?? null),
            'stockmap_sell' => ($exit['stockmap_sell'] ?? false) === true,
            'sma50_breaks' => $dates($exit['sma50_breaks'] ?? null),
        ];
        $out['news'] = self::clean_news($raw['news'] ?? null);
        $out['earnings_risk'] = self::clean_earnings_risk($raw['earnings_risk'] ?? null);
        $out['scenarios'] = self::clean_scenarios($raw['scenarios'] ?? null);
        return $out;
    }

    /**
     * Automatisk Bear/Base/Bull (additivt felt, regnestykket EPS × P/E): tal inden for fornuftige grænser,
     * højst 6 noter på 160 tegn. Null uden mindst ét kursmål, så siden siger "ikke beregnet".
     */
    /** Universets Bear/Base/Bull pr. ticker. @return array<string, array> */
    private static function clean_scenario_map($raw): array {
        $out = [];
        foreach (is_array($raw) ? array_slice($raw, 0, self::MAX_UNIVERSE, true) : [] as $ticker => $item) {
            $symbol = self::clean_ticker((string)$ticker);
            $clean = self::clean_scenarios($item);
            if ($symbol !== null && $clean !== null) { $out[$symbol] = $clean; }
        }
        return $out;
    }

    private static function clean_scenarios($raw): ?array {
        if (!is_array($raw)) { return null; }
        $single = static function ($value, float $min, float $max) {
            $number = self::clean_number($value);
            return $number !== null && $number >= $min && $number <= $max ? $number : null;
        };
        $triple = static function ($source, float $min, float $max) use ($single): array {
            $source = is_array($source) ? $source : [];
            $out = [];
            foreach (array_keys(self::SCENARIO_KEYS) as $key) {
                $out[$key] = $single($source[$key] ?? null, $min, $max);
            }
            return $out;
        };
        $prices = $triple($raw['prices'] ?? null, 0.0, 1.0e12);
        if ($prices['bear'] === null && $prices['base'] === null && $prices['bull'] === null) { return null; }
        $currency = is_string($raw['currency'] ?? null) ? strtoupper(trim($raw['currency'])) : '';
        $notes = [];
        foreach (array_slice(is_array($raw['notes'] ?? null) ? array_values($raw['notes']) : [], 0, 6) as $note) {
            $note = self::clean_string($note, 160);
            if ($note !== null) { $notes[] = $note; }
        }
        return [
            'currency' => preg_match('/^[A-Z]{3}$/D', $currency) === 1 ? $currency : null,
            'horizon_years' => $single($raw['horizon_years'] ?? null, 0.5, 10.0),
            'price' => $single($raw['price'] ?? null, 0.0, 1.0e12),
            'eps_today' => $single($raw['eps_today'] ?? null, -1.0e6, 1.0e6),
            'eps_horizon' => $single($raw['eps_horizon'] ?? null, -1.0e6, 1.0e6),
            'pe' => $triple($raw['pe'] ?? null, 0.0, 10000.0),
            'prices' => $prices,
            'upside_pct' => $triple($raw['upside_pct'] ?? null, -100.0, 1.0e6),
            'cagr_pct' => $triple($raw['cagr_pct'] ?? null, -100.0, 1.0e5),
            'asymmetry' => $single($raw['asymmetry'] ?? null, -1.0e4, 1.0e4),
            'asymmetry_inf' => ($raw['asymmetry_inf'] ?? false) === true,
            'peg' => $single($raw['peg'] ?? null, -1.0e4, 1.0e4),
            'channel_score' => $single($raw['channel_score'] ?? null, -1.0e5, 1.0e5),
            'notes' => $notes,
        ];
    }

    /** Regnskabsrisiko (additivt felt): kendt niveau, højst 6 begrundelser, andele 0-100; ellers null. */
    private static function clean_earnings_risk($raw): ?array {
        if (!is_array($raw)) { return null; }
        $level = is_string($raw['level'] ?? null) ? $raw['level'] : '';
        if (!in_array($level, self::RISK_LEVELS, true)) { return null; }
        $reasons = [];
        foreach (array_slice(is_array($raw['reasons'] ?? null) ? array_values($raw['reasons']) : [], 0, 6) as $reason) {
            $reason = self::clean_string($reason, 160);
            if ($reason !== null) { $reasons[] = $reason; }
        }
        $share = static function ($value, float $max) {
            $number = self::clean_number($value);
            return $number === null ? null : max(0.0, min($max, (float)$number));
        };
        return [
            'level' => $level,
            'points' => is_int($raw['points'] ?? null) ? max(0, min(3, $raw['points'])) : 0,
            'reasons' => $reasons,
            'avg_move_pct' => $share($raw['avg_move_pct'] ?? null, 1000.0),
            'down_share_pct' => $share($raw['down_share_pct'] ?? null, 100.0),
            'count' => is_int($raw['count'] ?? null) ? max(0, min(50, $raw['count'])) : 0,
            'note' => self::clean_string($raw['note'] ?? null, 60),
        ];
    }

    /** B-20: højst 5 overskrifter pr. aktie; kun https-links, kendte vurderinger. */
    private static function clean_news($raw): array {
        if (!is_array($raw)) { return []; }
        $out = [];
        foreach (array_slice(array_values($raw), 0, 5) as $item) {
            if (!is_array($item)) { continue; }
            $title = self::clean_string($item['title'] ?? null, 200);
            $url = is_string($item['url'] ?? null) ? esc_url_raw($item['url'], ['https']) : '';
            if ($title === null || $url === '') { continue; }
            $sentiment = is_string($item['sentiment'] ?? null) ? $item['sentiment'] : '';
            $impact = is_int($item['impact'] ?? null) ? max(0, min(3, $item['impact'])) : 0;
            $out[] = [
                'title' => $title,
                'url' => $url,
                'source' => self::clean_string($item['source'] ?? null, 80),
                'published' => self::clean_date($item['published'] ?? null),
                'sentiment' => in_array($sentiment, ['positiv', 'negativ', 'neutral'], true) ? $sentiment : 'uvurderet',
                'impact' => $impact,
                'reason' => self::clean_string($item['reason'] ?? null, 160),
            ];
        }
        return $out;
    }

    private static function clean_breadth($raw): array {
        $out = [];
        foreach (['20', '50', '200'] as $key) {
            $out[$key] = is_array($raw) ? self::clean_number($raw[$key] ?? null) : null;
        }
        return $out;
    }

    private static function clean_universe($raw): array {
        $result = ['columns' => self::UNIVERSE_COLUMNS, 'rows' => []];
        if (!is_array($raw) || !is_array($raw['columns'] ?? null) || !is_array($raw['rows'] ?? null)) {
            return $result;
        }
        // Map the sender's column order to our fixed order; unknown columns are ignored.
        $index = [];
        foreach (array_values($raw['columns']) as $pos => $name) {
            if (is_string($name) && in_array($name, self::UNIVERSE_COLUMNS, true)) {
                $index[$name] = $pos;
            }
        }
        if (!isset($index['ticker'])) { return $result; }
        $seen = [];
        foreach ($raw['rows'] as $row) {
            if (count($result['rows']) >= self::MAX_UNIVERSE) { break; }
            if (!is_array($row)) { continue; }
            $row = array_values($row);
            $ticker = self::clean_ticker($row[$index['ticker']] ?? null);
            if ($ticker === null || isset($seen[$ticker])) { continue; }
            $seen[$ticker] = true;
            $clean = [];
            foreach (self::UNIVERSE_COLUMNS as $name) {
                $value = isset($index[$name]) ? ($row[$index[$name]] ?? null) : null;
                if ($name === 'ticker') { $clean[] = $ticker; }
                elseif (in_array($name, ['region', 'size', 'liquidity', 'sector'], true)) { $clean[] = self::clean_string($value, 40); }
                else { $clean[] = self::clean_number($value); }
            }
            $result['rows'][] = $clean;
        }
        return $result;
    }

    private static function clean_screeners($raw): array {
        $out = [];
        foreach (self::SCREENERS as $key) {
            $item = is_array($raw) && is_array($raw[$key] ?? null) ? $raw[$key] : [];
            $out[$key] = [
                'label' => self::clean_string($item['label'] ?? null, 200) ?? $key,
                'global' => self::clean_ticker_list($item['global'] ?? null, self::MAX_UNIVERSE),
                'regional' => self::clean_ticker_list($item['regional'] ?? null, self::MAX_UNIVERSE),
            ];
        }
        return $out;
    }

    /**
     * Papirporteføljens stilling mod RSP (additivt felt `paper_score`): tal og dato renses, null uden felt.
     * Intet gættes: manglende tal forbliver null.
     */
    private static function clean_paper_score($raw): ?array {
        if (!is_array($raw) || self::clean_number($raw['antal'] ?? null) === null) { return null; }
        $out = [];
        foreach (['antal', 'sammenlignet', 'udeladt', 'dage'] as $key) {
            $value = self::clean_number($raw[$key] ?? null);
            $out[$key] = $value === null ? null : (int)$value;
        }
        foreach (['afkast_pct', 'rsp_pct', 'forskel_pp', 'vinderandel_pct', 'slaar_rsp_pct'] as $key) {
            $out[$key] = self::clean_number($raw[$key] ?? null);
        }
        $out['start'] = self::clean_date($raw['start'] ?? null);
        $out['for_tidligt'] = ($raw['for_tidligt'] ?? true) !== false;
        return $out;
    }

    private static function clean_paper($raw): array {
        $summary = is_array($raw) && is_array($raw['summary'] ?? null) ? $raw['summary'] : [];
        $out = [
            'summary' => [
                'handler' => self::clean_number($summary['handler'] ?? null),
                'aabne' => self::clean_number($summary['aabne'] ?? null),
                'afkast_pct' => self::clean_number($summary['afkast_pct'] ?? null),
                'vundne_pct' => self::clean_number($summary['vundne_pct'] ?? null),
            ],
            'trades' => [],
        ];
        $trades = is_array($raw) && is_array($raw['trades'] ?? null) ? $raw['trades'] : [];
        foreach ($trades as $trade) {
            if (count($out['trades']) >= self::MAX_TRADES) { break; }
            if (!is_array($trade)) { continue; }
            $ticker = self::clean_ticker($trade['ticker'] ?? null);
            if ($ticker === null) { continue; }
            $out['trades'][] = [
                'ticker' => $ticker,
                'koebsdato' => self::clean_date($trade['koebsdato'] ?? null),
                'koebskurs' => self::clean_number($trade['koebskurs'] ?? null),
                'salgsdato' => self::clean_date($trade['salgsdato'] ?? null),
                'salgskurs' => self::clean_number($trade['salgskurs'] ?? null),
                'salgsgrund' => self::clean_string($trade['salgsgrund'] ?? null, 200),
                'seneste' => self::clean_number($trade['seneste'] ?? null),
            ];
        }
        return $out;
    }

    private static function clean_changes($raw): array {
        $out = [];
        if (!is_array($raw)) { return $out; }
        foreach ($raw as $item) {
            $text = self::clean_string($item, 300);
            if ($text !== null) { $out[] = $text; }
            if (count($out) >= 200) { break; }
        }
        return $out;
    }

    // ------------------------------------------------------------ Data access

    public static function snapshot(): ?array {
        if (!self::$cache_loaded) {
            $data = get_option(self::OPTION, []);
            self::$cached = is_array($data) && is_array($data['stocks'] ?? null)
                && is_string($data['generated_at'] ?? null) ? $data : null;
            self::$cache_loaded = true;
        }
        return self::$cached;
    }

    // ------------------------------------------------- Brugerens egne data og synlighed

    /** @return string[] Symbolerne på den indloggede brugers egen overvågningsliste. */
    private static function user_watch(int $user_id): array {
        $watch = get_user_meta($user_id, self::WATCH_META, true);
        return is_array($watch) ? array_values(array_filter($watch, 'is_string')) : [];
    }

    /** @return array<string, array<int, array<string, mixed>>> Brugerens egne køb i WordPress-porteføljen pr. symbol. */
    private static function user_lots(int $user_id): array {
        $raw = get_user_meta($user_id, self::PORTFOLIO_META, true);
        $out = [];
        foreach (is_array($raw) ? $raw : [] as $lot) {
            $ticker = is_array($lot) ? self::clean_ticker($lot['ticker'] ?? null) : null;
            if ($ticker !== null) { $out[$ticker][] = $lot; }
        }
        return $out;
    }

    /** @return string[] Symbolerne i brugerens egen simulatorrunde. */
    private static function user_sim_tickers(int $user_id): array {
        $sim = get_user_meta($user_id, self::SIM_META, true);
        $positions = is_array($sim) && is_array($sim['round']['positions'] ?? null) ? $sim['round']['positions'] : [];
        $out = [];
        foreach ($positions as $position) {
            $ticker = is_array($position) ? self::clean_ticker($position['ticker'] ?? null) : null;
            if ($ticker !== null) { $out[] = $ticker; }
        }
        return $out;
    }

    /**
     * Rene regler for, hvilke aktier en bruger ser på mandagslisten: den fælles research-liste og tragtens
     * kandidater samt det, brugeren selv følger, ejer (WordPress-porteføljen) eller har i sin simulator.
     * Andre brugeres lister kommer aldrig med, selv om scanneren analyserer dem.
     * @param string[] $watch @param string[] $owned @param string[] $simulated
     * @return array<string, true>
     */
    public static function visible_tickers(array $data, array $watch, array $owned, array $simulated): array {
        $visible = [];
        foreach ([$data['research'] ?? null, $data['candidates'] ?? null, $watch, $owned, $simulated] as $list) {
            foreach (is_array($list) ? $list : [] as $symbol) {
                $ticker = self::clean_ticker($symbol);
                if ($ticker !== null) { $visible[$ticker] = true; }
            }
        }
        return $visible;
    }

    /** Er teksten en begrundelse, der stammer fra scannerens egen (lokale) portefølje og købsdato? */
    private static function is_owner_reason(string $part): bool {
        return preg_match('/% siden køb$/u', $part) === 1
            || $part === 'ingen salgsregel ramt'
            || $part === 'StockMap-salg denne uge'
            || str_starts_with($part, 'Supertrend ×3 vendt ned')
            || str_starts_with($part, 'brud under SMA50');
    }

    /** Gennemsnitlig gevinst i % siden køb for brugerens egne køb; null ved blandede valutaer eller manglende tal. */
    private static function lots_gain(array $stock, array $lots): ?float {
        $price = $stock['price'] ?? null;
        $currency = $stock['currency'] ?? null;
        if (!is_numeric($price) || (float)$price <= 0) { return null; }
        $cost = 0.0;
        $quantity = 0.0;
        foreach ($lots as $lot) {
            $count = is_array($lot) ? ($lot['quantity'] ?? null) : null;
            $buy = is_array($lot) ? ($lot['buy_price'] ?? null) : null;
            $lot_currency = is_array($lot) ? ($lot['currency'] ?? null) : null;
            if (!is_numeric($count) || !is_numeric($buy) || (float)$count <= 0 || (float)$buy <= 0) { return null; }
            if (!is_string($lot_currency) || !is_string($currency) || $lot_currency !== $currency) { return null; }
            $cost += (float)$count * (float)$buy;
            $quantity += (float)$count;
        }
        return $quantity > 0 ? ((float)$price / ($cost / $quantity) - 1) * 100 : null;
    }

    /**
     * Aktien set med den enkelte brugers øjne. Scannerens "(ejet)"-handlinger og "% siden køb" stammer fra
     * scannerens egen lokale portefølje og vises derfor kun, når brugeren selv har aktien i sin WordPress-portefølje;
     * handling og salgsregler regnes da af brugerens egne købsdatoer. Ellers "hold øje" og en neutral begrundelse.
     * @param array<int, array<string, mixed>> $lots Brugerens egne køb i aktien (tom = ejer den ikke).
     */
    public static function personal_stock(array $stock, array $lots): array {
        $kept = [];
        foreach (explode('; ', (string)($stock['reasons'] ?? '')) as $part) {
            $part = trim($part);
            if ($part !== '' && !self::is_owner_reason($part)) { $kept[] = $part; }
        }
        if (!$lots) {
            if (!in_array($stock['action'] ?? null, self::OWNED_ACTIONS, true)) { return $stock; }
            $stock['action'] = 'hold øje';
            $stock['reasons'] = implode('; ', array_merge(['ikke i din portefølje'], $kept));
            return $stock;
        }
        $sell = [];
        foreach ($lots as $lot) {
            $buy_date = is_array($lot) ? (string)($lot['buy_date'] ?? '') : '';
            foreach (self::exit_reasons($stock, $buy_date) as $reason) { $sell[$reason] = true; }
        }
        $gain = self::lots_gain($stock, $lots);
        $parts = [];
        if ($gain !== null) { $parts[] = ($gain > 0 ? '+' : '') . self::n($gain, 1) . ' % siden køb'; }
        $parts = array_merge($parts, $sell ? array_map('strval', array_keys($sell)) : ['ingen salgsregel ramt'], $kept);
        $stock['action'] = $sell ? 'SÆLG (ejet)' : 'BEHOLD (ejet)';
        $stock['reasons'] = implode('; ', $parts);
        return $stock;
    }

    /**
     * "Ændringer siden sidst" for én bruger: kun aktier brugeren ser (og papirporteføljens fælles linjer).
     * Handlings-ændringer med "(ejet)" stammer fra scannerens egen portefølje og udelades.
     * @param array<int, mixed> $changes @param array<string, true> $visible
     * @return string[]
     */
    public static function visible_changes(array $changes, array $visible): array {
        $out = [];
        foreach ($changes as $change) {
            if (!is_string($change)) { continue; }
            if (str_starts_with($change, 'PAPIR ')) { $out[] = $change; continue; }
            if (preg_match('/^([A-Z0-9^][A-Z0-9.^=-]{0,19}): (.+)$/Du', $change, $match) !== 1
                || !isset($visible[$match[1]])) { continue; }
            $parts = array_values(array_filter(explode('; ', $match[2]),
                static fn(string $part): bool => !str_contains($part, '(ejet)')));
            if ($parts) { $out[] = $match[1] . ': ' . implode('; ', $parts); }
        }
        return $out;
    }

    /** One line for the admin overview page (already escaped). */
    public static function admin_status_line(): string {
        $data = self::snapshot();
        if ($data === null) {
            return '<p>Playbook (mandagsliste) fra PC: <strong>ingen endnu</strong></p>';
        }
        return '<p>Playbook (mandagsliste) fra PC: <strong>'
            . esc_html(self::when((string)$data['generated_at'])) . '</strong> – '
            . esc_html((string)count($data['stocks'])) . ' aktier</p>';
    }

    private static function when(string $iso): string {
        $stamp = strtotime($iso);
        if ($stamp === false) { return $iso; }
        $text = wp_date('d-m-Y H:i', $stamp, new DateTimeZone('Europe/Copenhagen'));
        return is_string($text) ? $text : $iso;
    }

    /**
     * Playbook analysis of one ticker for the simulator's lookup panel. Returns
     * complete, already escaped HTML: the full stock analysis when the ticker is in
     * the snapshot's stocks, the universe scores otherwise, or a clear notice.
     */
    public static function analysis_panel(string $ticker): string {
        $data = self::snapshot();
        $stock = $data !== null && is_array($data['stocks'][$ticker] ?? null)
            ? $data['stocks'][$ticker] : null;
        $html = '<div class="asc-sim-analysis"><h4>Playbook-analyse</h4>';
        if ($stock !== null) {
            // Ejet-status og "% siden køb" vises kun, hvis brugeren selv har aktien (se personal_stock).
            $stock = self::personal_stock($stock, self::user_lots(get_current_user_id())[$ticker] ?? []);
            $html .= '<p><strong>' . self::s($stock['action'] ?? null) . '</strong> – '
                . self::s($stock['reasons'] ?? null) . ' ' . self::earnings_block_badge($stock) . '</p>';
            $risk = self::risk_html($stock);
            if ($risk !== '') { $html .= '<p class="asc-pb-risk">' . $risk . '</p>'; }
            $html .= '<dl class="asc-sim-facts">';
            $facts = [
                'StockMap' => self::s($stock['stockmap'] ?? null),
                'TPI' => self::s($stock['tpi'] ?? null),
                'MTI' => self::s($stock['mti'] ?? null),
                'Kvalitet' => esc_html(self::n($stock['quality'] ?? null)),
                'Moat' => esc_html(self::n($stock['moat'] ?? null)),
                'MSS-score' => esc_html(self::n($stock['mss_score'] ?? null)),
                'Værdi' => esc_html(self::n($stock['value_pct'] ?? null)),
                'Momentum' => esc_html(self::n($stock['momentum'] ?? null)),
                'Kanal' => esc_html(self::n($stock['channel_score'] ?? null)),
                'PEG' => esc_html(self::n($stock['peg'] ?? null, 1)),
                'Asymmetri' => !empty($stock['asymmetry_inf']) ? '∞'
                    : esc_html(self::n($stock['asymmetry'] ?? null, 1)),
                'Regnskab' => self::earnings_html($stock['earnings'] ?? null),
                'EPS-trend' => self::s($stock['eps_trend'] ?? null),
                'Størrelse' => self::s($stock['size'] ?? null),
                'Likviditet' => self::liquidity_badge($stock['liquidity'] ?? null),
                'Sektor' => esc_html(self::sector_of($stock, self::universe_index($data)[$ticker] ?? [])),
            ];
            foreach ($facts as $label => $value) {
                $html .= '<div><dt>' . esc_html($label) . '</dt><dd>' . $value . '</dd></div>';
            }
            $html .= '</dl>' . self::scenarios_section($ticker);
            $html .= '<p class="asc-subtle">Nyheder: ' . self::s($stock['news_summary'] ?? null) . '</p>';
            $html .= '<p class="asc-subtle">Analyse fra ' . esc_html(self::when((string)$data['generated_at'])) . '.</p>';
            return $html . '</div>';
        }
        $row = $data !== null ? (self::universe_index($data)[$ticker] ?? null) : null;
        if (is_array($row)) {
            $html .= '<p>Kun grundscores (percentiler, global / region) – ikke fuld analyse endnu. '
                . 'Fuld analyse kommer med ved næste kørsel, hvis aktien følges.</p><dl class="asc-sim-facts">';
            foreach (['quality' => 'Kvalitet', 'value' => 'Værdi', 'momentum' => 'Momentum', 'moat' => 'Moat'] as $key => $label) {
                $html .= '<div><dt>' . esc_html($label) . '</dt><dd>'
                    . esc_html(self::n($row[$key] ?? null) . ' / ' . self::n($row[$key . '_r'] ?? null)) . '</dd></div>';
            }
            $html .= '<div><dt>Region</dt><dd>' . self::s($row['region'] ?? null) . '</dd></div>';
            $html .= '<div><dt>Upside %</dt><dd>' . esc_html(self::n($row['upside'] ?? null, 1)) . '</dd></div>';
            $html .= '<div><dt>PEG</dt><dd>' . esc_html(self::n($row['peg'] ?? null, 1)) . '</dd></div>';
            $html .= '<div><dt>Størrelse</dt><dd>' . self::s($row['size'] ?? null) . '</dd></div>';
            $html .= '<div><dt>Likviditet</dt><dd>' . self::liquidity_badge($row['liquidity'] ?? null) . '</dd></div>';
            $html .= '<div><dt>Sektor</dt><dd>' . esc_html(self::sector_label($row['sector'] ?? null)) . '</dd></div>';
            return $html . '</dl>' . self::scenarios_section($ticker) . '</div>';
        }
        return $html . '<p>Ikke analyseret endnu – kommer med ved næste kørsel, hvis du køber aktien i simulatoren '
            . 'eller sætter den på overvågningslisten.</p></div>';
    }

    /** "Køb i simulator" link (escaped HTML) to the simulator lookup for this ticker. */
    private static function simulator_link(string $ticker): string {
        if (!class_exists('ASC_Simulator')) { return ''; }
        return '<a class="asc-sim-link" href="' . esc_url(ASC_Simulator::lookup_url($ticker))
            . '">Køb i simulator</a>';
    }

    /** Tickere med automatiske scenarier, som den indloggede bruger selv ser (til vælgeren på Analyse-siden). @return string[] */
    public static function scenario_tickers(): array {
        $data = self::snapshot();
        if ($data === null) { return []; }
        $user_id = get_current_user_id();
        $visible = self::visible_tickers($data, self::user_watch($user_id), array_map('strval', array_keys(self::user_lots($user_id))),
            self::user_sim_tickers($user_id));
        $out = [];
        foreach ($data['stocks'] as $ticker => $stock) {
            if (isset($visible[(string)$ticker]) && is_array($stock) && is_array($stock['scenarios'] ?? null)) {
                $out[] = (string)$ticker;
            }
        }
        // Universets tal er fælles markedsdata og må ses af alle.
        foreach (is_array($data['scenarios'] ?? null) ? array_keys($data['scenarios']) : [] as $ticker) {
            $out[] = (string)$ticker;
        }
        $out = array_values(array_unique($out));
        sort($out, SORT_STRING);
        return $out;
    }

    /** De automatiske scenarier for én aktie fra snapshottet; null når de ikke er beregnet. */
    public static function scenarios_for(string $ticker): ?array {
        $data = self::snapshot();
        $stock = $data !== null && is_array($data['stocks'][$ticker] ?? null) ? $data['stocks'][$ticker] : null;
        if (is_array($stock['scenarios'] ?? null)) { return $stock['scenarios']; }
        return $data !== null && is_array($data['scenarios'][$ticker] ?? null) ? $data['scenarios'][$ticker] : null;
    }

    private static function signed($value, int $decimals = 1): string {
        if (!is_int($value) && !is_float($value)) { return '–'; }
        return (((float)$value) > 0 ? '+' : '') . self::n($value, $decimals);
    }

    /**
     * Tre kort Bear/Base/Bull med kursmål, upside, årligt afkast og P/E × EPS, kursen nu markeret og en tekst,
     * der siger, at det er et regnestykke og ikke en prognose. Escaped HTML.
     * @param array<string, mixed> $sc Et renset `scenarios`-felt (clean_scenarios).
     */
    public static function scenario_cards_html(array $sc): string {
        $unit = is_string($sc['currency'] ?? null) && $sc['currency'] !== '' ? ' ' . esc_html($sc['currency']) : '';
        $field = static fn(string $key): array => is_array($sc[$key] ?? null) ? $sc[$key] : [];
        $prices = $field('prices');
        $pe = $field('pe');
        $upside = $field('upside_pct');
        $cagr = $field('cagr_pct');
        $eps_horizon = $sc['eps_horizon'] ?? null;
        $price = $sc['price'] ?? null;
        $years = is_int($sc['horizon_years'] ?? null) || is_float($sc['horizon_years'] ?? null) ? (float)$sc['horizon_years'] : null;
        $html = '<div class="asc-scenarios"><p class="asc-scenario-now">Kurs nu (ved seneste kørsel): <strong>'
            . esc_html(self::n($price, 2)) . '</strong>' . $unit . '</p><div class="asc-analysis-grid">';
        foreach (self::SCENARIO_KEYS as $key => $label) {
            $target = $prices[$key] ?? null;
            $change = $upside[$key] ?? null;
            $class = !is_numeric($change) ? '' : ((float)$change >= 0 ? 'asc-positive' : 'asc-negative');
            $html .= '<div class="asc-analysis-card asc-scenario asc-scenario-' . esc_attr($key) . '"><h4>' . esc_html($label)
                . '</h4><strong>' . esc_html(self::n($target, 2)) . '</strong>' . $unit
                . '<p class="' . esc_attr($class) . '">Upside ' . esc_html(self::signed($change)) . ' %'
                . ' · årligt ' . esc_html(self::signed($cagr[$key] ?? null)) . ' %</p>'
                . '<small>EPS ' . esc_html(self::n($eps_horizon, 2)) . ' × P/E ' . esc_html(self::n($pe[$key] ?? null, 1))
                . '</small></div>';
        }
        $html .= '</div>';
        if (is_numeric($price) && is_numeric($prices['bear'] ?? null) && is_numeric($prices['base'] ?? null)
            && is_numeric($prices['bull'] ?? null)) {
            $now = (float)$price;
            $where = $now < (float)$prices['bear'] ? 'under Bear-kursmålet'
                : ($now < (float)$prices['base'] ? 'mellem Bear og Base'
                : ($now < (float)$prices['bull'] ? 'mellem Base og Bull' : 'over Bull-kursmålet'));
            $html .= '<p class="asc-scenario-position">Kursen nu ligger <strong>' . esc_html($where) . '</strong>.</p>';
        }
        $asymmetry = !empty($sc['asymmetry_inf']) ? '∞' : (is_numeric($sc['asymmetry'] ?? null) ? self::n($sc['asymmetry'], 1) : '–');
        $html .= '<p class="asc-subtle">Kursmål = EPS om ' . esc_html($years === null ? '–' : self::n($years, 1)) . ' år × P/E. '
            . 'Dagens EPS: ' . esc_html(self::n($sc['eps_today'] ?? null, 2)) . '. Asymmetri (mulig gevinst ved Base mod mulig nedside ved Bear): '
            . esc_html($asymmetry) . '. PEG: ' . esc_html(self::n($sc['peg'] ?? null, 1)) . '.</p>';
        $notes = [];
        foreach (is_array($sc['notes'] ?? null) ? $sc['notes'] : [] as $note) {
            if (is_string($note) && $note !== '') { $notes[] = $note; }
        }
        if ($notes) { $html .= '<p class="asc-subtle">Bemærk: ' . esc_html(implode('; ', $notes)) . '.</p>'; }
        $html .= '<p class="asc-disclaimer">Det er regnestykket EPS × P/E ud fra historiske P/E og analytikernes estimater, '
            . 'ikke en prognose og ikke en købs- eller salgsanbefaling.</p></div>';
        return $html;
    }

    /** Scenarieafsnit til analysepanelet: kortene, eller en besked om at de ikke er beregnet. Escaped HTML. */
    private static function scenarios_section(string $ticker): string {
        $html = '<h5>Bear / Base / Bull</h5>';
        $scenarios = self::scenarios_for($ticker);
        if ($scenarios === null) {
            return $html . '<p class="asc-subtle">Ikke beregnet endnu. Følg aktien, så kommer den med ved næste kørsel.</p>';
        }
        return $html . self::scenario_cards_html($scenarios);
    }

    /**
     * Sell rule for an owned lot, used by the portfolio table. Returns the
     * complete, escaped table row (empty when the stock is not in the snapshot).
     */
    public static function exit_rule_row(string $ticker, string $buy_date, int $columns): string {
        $text = self::exit_rule_text($ticker, $buy_date);
        if ($text === null) { return ''; }
        return '<tr class="asc-rule-row"><td colspan="' . $columns . '"><div>Salgsregel: ' . $text . '</div></td></tr>';
    }

    /**
     * Aktive salgsgrunde for et køb ud fra snapshottets købsdato-uafhængige fakta og brugerens egen købsdato.
     * @return string[]
     */
    private static function exit_reasons(array $stock, string $buy_date): array {
        $exit = is_array($stock['exit'] ?? null) ? $stock['exit'] : [];
        $reasons = [];
        $valid_date = preg_match(self::DATE_RE, $buy_date) === 1;
        // Kun brud EFTER købsdatoen tæller (som i backtesten); en aktie købt i en nedtrend sælges ikke straks.
        $after = static function ($dates) use ($buy_date, $valid_date): string {
            $latest = '';
            foreach ($valid_date && is_array($dates) ? $dates : [] as $date) {
                if (is_string($date) && $date > $buy_date && $date > $latest) { $latest = $date; }
            }
            return $latest;
        };
        $flip = $after($exit['supertrend_flips'] ?? null);
        if ($flip !== '' && !empty($exit['supertrend_down'])) { $reasons[] = 'Supertrend ×3 vendt ned (' . $flip . ')'; }
        if (!empty($exit['stockmap_sell'])) { $reasons[] = 'StockMap-salg denne uge'; }
        $break = $after($exit['sma50_breaks'] ?? null);
        if ($break !== '') { $reasons[] = 'brud under SMA50 (' . $break . ')'; }
        return $reasons;
    }

    /** Salgsreglens tekst (escaped HTML) for ét køb; null når aktien ikke er i snapshottet. */
    private static function exit_rule_text(string $ticker, string $buy_date): ?string {
        $data = self::snapshot();
        $stock = $data !== null && is_array($data['stocks'][$ticker] ?? null)
            ? $data['stocks'][$ticker] : null;
        if ($stock === null) { return null; }
        $reasons = self::exit_reasons($stock, $buy_date);
        return $reasons
            ? '<span class="asc-pb-sell">SÆLG: ' . esc_html(implode(', ', $reasons)) . '</span>'
            : 'behold';
    }

    /**
     * Aktiesidens analyseafsnit (escaped HTML): playbook-analysen (med regnskabsnedtælling og regnskabsrisiko),
     * salgsregel for hvert ejet køb og nyheder med vurdering. Uden playbook-data en klar besked.
     * @param array<int, array{source: string, buy_date: string}> $owned Ejede køb (portefølje og simulator).
     */
    public static function stock_page_analysis(string $ticker, array $owned = []): string {
        $data = self::snapshot();
        $stock = $data !== null && is_array($data['stocks'][$ticker] ?? null) ? $data['stocks'][$ticker] : null;
        $row = $data !== null ? (self::universe_index($data)[$ticker] ?? null) : null;
        if ($stock === null && !is_array($row)) {
            return '<div class="asc-sim-analysis"><h4>Playbook-analyse</h4>'
                . '<p>Ikke analyseret endnu. Følg aktien, så kommer den med ved næste kørsel.</p></div>';
        }
        $html = self::analysis_panel($ticker);
        if ($stock === null) { return $html; }
        $rules = '';
        foreach (array_slice($owned, 0, 6) as $item) {
            $buy_date = is_array($item) ? (string)($item['buy_date'] ?? '') : '';
            $text = self::exit_rule_text($ticker, $buy_date);
            if ($text === null) { continue; }
            $rules .= '<li>' . esc_html(is_array($item) ? (string)($item['source'] ?? '') : '')
                . ($buy_date !== '' ? esc_html(', købt ' . $buy_date) : '') . ': ' . $text . '</li>';
        }
        if ($rules !== '') {
            $html .= '<div class="asc-sim-analysis"><h4>Salgsregel (du ejer aktien)</h4><ul>' . $rules . '</ul></div>';
        }
        ob_start();
        self::render_news([$ticker => $stock]);
        return $html . (string)ob_get_clean();
    }

    /** Størrelses- og likviditetsklasse (escaped HTML) fra playbook eller universet; tom streng uden data. */
    public static function size_liquidity_html(string $ticker): string {
        $data = self::snapshot();
        if ($data === null) { return ''; }
        $stock = is_array($data['stocks'][$ticker] ?? null) ? $data['stocks'][$ticker] : [];
        $row = self::universe_index($data)[$ticker] ?? [];
        $size = $stock['size'] ?? ($row['size'] ?? null);
        $liquidity = $stock['liquidity'] ?? ($row['liquidity'] ?? null);
        $parts = [];
        if (is_string($size) && $size !== '') { $parts[] = 'Størrelse: ' . esc_html($size); }
        if (is_string($liquidity) && $liquidity !== '') { $parts[] = 'Likviditet: ' . self::liquidity_badge($liquidity); }
        return implode(' · ', $parts);
    }

    /**
     * Nøgletal til aktiesidens graf fra playbook-data: P/E (kurs / EPS i dag fra Bear/Base/Bull, kun når begge
     * er positive) og markedsværdi i mia. USD (universet). null hvor data mangler; intet gættes.
     * @return array{pe: ?float, mcap_usd_bn: ?float}
     */
    public static function key_figures(string $ticker): array {
        $out = ['pe' => null, 'mcap_usd_bn' => null];
        $data = self::snapshot();
        if ($data === null) { return $out; }
        $row = self::universe_index($data)[$ticker] ?? [];
        $cap = self::clean_number($row['mcap_usd_bn'] ?? null);
        if ($cap !== null && $cap > 0) { $out['mcap_usd_bn'] = (float)$cap; }
        $sc = self::scenarios_for($ticker);
        $price = is_array($sc) ? ($sc['price'] ?? null) : null;
        $eps = is_array($sc) ? ($sc['eps_today'] ?? null) : null;
        if ((is_int($price) || is_float($price)) && (is_int($eps) || is_float($eps)) && $price > 0 && $eps > 0) {
            $pe = (float)$price / (float)$eps;
            if (is_finite($pe) && $pe < 10000.0) { $out['pe'] = $pe; }
        }
        return $out;
    }

    /** Alle symboler playbook kender (aktier og univers), til aktiesidens navnesøgning. @return string[] */
    public static function known_tickers(): array {
        $data = self::snapshot();
        if ($data === null) { return []; }
        $list = array_map('strval', array_keys($data['stocks']));
        $list = array_merge($list, array_map('strval', array_keys(self::universe_index($data))));
        return array_values(array_unique($list));
    }

    // ------------------------------------------------- Spredning på sektorer

    /** Sektoren som tekst: den indsendte, ellers "ukendt" (snapshot uden feltet er i orden). */
    public static function sector_label($value): string {
        $text = is_string($value) ? trim($value) : '';
        return $text === '' ? self::SECTOR_UNKNOWN : $text;
    }

    /** Aktiens sektor fra playbook-aktien, ellers fra universets række, ellers "ukendt". */
    public static function sector_of(?array $stock, array $row = []): string {
        $sector = self::sector_label($stock['sector'] ?? null);
        return $sector !== self::SECTOR_UNKNOWN ? $sector : self::sector_label($row['sector'] ?? null);
    }

    /**
     * Antal pr. sektor, største først (ens antal alfabetisk). "ukendt" tælles for sig selv og står aldrig i `counts`.
     * @param array<int|string, mixed> $sectors
     * @return array{counts: array<string, int>, unknown: int, total: int}
     */
    public static function sector_counts(array $sectors): array {
        $counts = [];
        $unknown = 0;
        foreach ($sectors as $sector) {
            $label = self::sector_label($sector);
            if ($label === self::SECTOR_UNKNOWN) { $unknown++; continue; }
            $counts[$label] = ($counts[$label] ?? 0) + 1;
        }
        uksort($counts, static function ($a, $b) use ($counts): int {
            return [-$counts[$a], (string)$a] <=> [-$counts[$b], (string)$b];
        });
        return ['counts' => $counts, 'unknown' => $unknown, 'total' => count($sectors)];
    }

    /**
     * Spredningsadvarsel: den største sektor, hvis den har flere end $max_count aktier (kun hvis $max_count er sat)
     * eller over 40 % af alle, når der er mindst $min_total i alt. Aktier uden sektor tæller med i nævneren, men
     * giver aldrig selv en advarsel. Blokerer intet.
     * @param array<int|string, mixed> $sectors
     * @return array{sector: string, count: int, total: int}|null
     */
    public static function concentration_warning(array $sectors, int $min_total, ?int $max_count = null): ?array {
        $info = self::sector_counts($sectors);
        if ($info['counts'] === []) { return null; }
        $sector = (string)array_key_first($info['counts']);
        $count = $info['counts'][$sector];
        $total = $info['total'];
        $many = $max_count !== null && $count > $max_count;
        $share = $total >= $min_total && $count / $total > self::SECTOR_SHARE;
        return $many || $share ? ['sector' => $sector, 'count' => $count, 'total' => $total] : null;
    }

    /** Advarslens tekst (ikke escaped): "Bemærk: 7 af 9 aktier med entry ligger i Teknologi. Falder sektoren, falder de samlet." */
    public static function concentration_text(array $warning, string $what): string {
        return 'Bemærk: ' . (int)$warning['count'] . ' af ' . (int)$warning['total'] . ' ' . $what . ' ligger i '
            . (string)$warning['sector'] . '. Falder sektoren, falder de samlet.';
    }

    /** "Teknologi 7 · Sundhed 2 · ukendt 1" (escaped HTML); tom streng uden aktier. @param array<int|string, mixed> $sectors */
    public static function sector_count_line(array $sectors): string {
        $info = self::sector_counts($sectors);
        $parts = [];
        foreach ($info['counts'] as $sector => $count) {
            $parts[] = esc_html((string)$sector) . ' ' . $count;
        }
        if ($info['unknown'] > 0) { $parts[] = esc_html(self::SECTOR_UNKNOWN) . ' ' . $info['unknown']; }
        return implode(' · ', $parts);
    }

    /** Spredningsadvarslen som afsnit (escaped HTML); tom streng uden advarsel. @param array<int|string, mixed> $sectors */
    public static function concentration_html(array $sectors, int $min_total, ?int $max_count, string $what): string {
        $warning = self::concentration_warning($sectors, $min_total, $max_count);
        return $warning === null ? ''
            : '<p class="asc-warning asc-pb-spread" role="status">' . esc_html(self::concentration_text($warning, $what)) . '</p>';
    }

    /** Advarsel for aktier med entry (Find aktier og Overblik). @param array<int|string, mixed> $sectors */
    public static function entry_concentration_html(array $sectors): string {
        return self::concentration_html($sectors, self::SECTOR_MIN_TOTAL, self::SECTOR_MAX_ENTRIES, 'aktier med entry');
    }

    /**
     * Advarsel om brugerens egne positioner (portefølje eller simulator): over 40 % i samme sektor, når der er mindst
     * 4 positioner. Kun sektordata fra snapshottet; mangler sektoren, tælles aktien som ukendt og giver ingen advarsel.
     * @param array<int, mixed> $tickers
     */
    public static function own_sector_warning(array $tickers): string {
        $data = self::snapshot();
        if ($data === null) { return ''; }
        $index = self::universe_index($data);
        $sectors = [];
        foreach (array_values(array_unique(array_map('strval', $tickers))) as $ticker) {
            $stock = is_array($data['stocks'][$ticker] ?? null) ? $data['stocks'][$ticker] : null;
            $sectors[] = self::sector_of($stock, $index[$ticker] ?? []);
        }
        return self::concentration_html($sectors, self::SECTOR_MIN_TOTAL, null, 'positioner i din portefølje');
    }

    // ------------------------------------------------ Papirporteføljen mod RSP

    /**
     * Stillingen øverst på fanen Papirportefølje (escaped HTML): antal handler, gennemsnitligt afkast mod RSP i samme
     * periode, forskel, vinderandel og startdato, med noten om de første 3 måneder. Tom streng uden handler.
     */
    public static function paper_score_html(?array $score): string {
        if ($score === null || (int)($score['antal'] ?? 0) <= 0) { return ''; }
        $antal = (int)$score['antal'];
        $compared = (int)($score['sammenlignet'] ?? 0);
        $left_out = max(0, $antal - $compared);
        $diff = $score['forskel_pp'] ?? null;
        $class = !is_numeric($diff) ? '' : ((float)$diff >= 0 ? 'asc-positive' : 'asc-negative');
        $start = is_string($score['start'] ?? null) ? $score['start'] : null;
        $html = '<div class="asc-pb-paper-score"><h4>Stilling mod RSP</h4>';
        $html .= '<div class="asc-metrics asc-portfolio-summary">';
        $html .= '<div><strong>' . esc_html(self::n($antal)) . '</strong><span>Handler</span></div>';
        $html .= '<div><strong>' . esc_html(self::signed($score['afkast_pct'] ?? null)) . ' %</strong>'
            . '<span>Gennemsnitligt afkast</span></div>';
        $html .= '<div><strong>' . esc_html(self::signed($score['rsp_pct'] ?? null)) . ' %</strong>'
            . '<span>RSP i samme periode</span></div>';
        $html .= '<div><strong class="' . esc_attr($class) . '">' . esc_html(self::signed($diff)) . ' %-point</strong>'
            . '<span>Forskel</span></div>';
        $html .= '<div><strong>' . esc_html(self::n($score['vinderandel_pct'] ?? null)) . ' %</strong>'
            . '<span>Vinderandel</span></div>';
        $html .= '<div><strong>' . esc_html($start === null ? '–' : $start) . '</strong><span>Startdato</span></div>';
        $html .= '</div>';
        if (($score['for_tidligt'] ?? true) !== false) {
            $html .= '<p class="asc-warning" role="status"><strong>' . esc_html(self::PAPER_EARLY_NOTE) . '</strong></p>';
        }
        $html .= '<p class="asc-subtle">Lige store beløb pr. handel. Afkast er i aktiens egen valuta og er ikke omregnet. '
            . 'RSP regnes fra samme købsdato til salgsdato, eller til seneste kursdato for åbne handler. '
            . esc_html(self::n($compared)) . ' af ' . esc_html(self::n($antal)) . ' handler er med i sammenligningen';
        $html .= $left_out > 0
            ? '; ' . esc_html(self::n($left_out)) . ' er udeladt, fordi en kurs mangler (de gættes ikke).'
            : '.';
        return $html . '</p></div>';
    }

    /** Kort stilling til Overblik (escaped HTML) med link til fanen; tom streng uden handler. */
    public static function paper_brief_html(?array $score, string $url): string {
        if ($score === null || (int)($score['antal'] ?? 0) <= 0) { return ''; }
        $antal = (int)$score['antal'];
        $link = ' <a href="' . esc_url($url) . '">Se papirporteføljen</a>';
        $html = '<div class="asc-top-picks asc-paper-brief"><h2>Reglerne mod markedet</h2>';
        if ((int)($score['sammenlignet'] ?? 0) <= 0) {
            return $html . '<p>' . esc_html(self::n($antal)) . ' papirhandler, men ingen kan sammenlignes med RSP endnu.'
                . $link . '</p></div>';
        }
        $html .= '<p>' . esc_html(self::n($antal)) . ' papirhandler: gennemsnit '
            . esc_html(self::signed($score['afkast_pct'] ?? null)) . ' % mod RSP '
            . esc_html(self::signed($score['rsp_pct'] ?? null)) . ' % ('
            . esc_html(self::signed($score['forskel_pp'] ?? null)) . ' %-point).';
        if (($score['for_tidligt'] ?? true) !== false) { $html .= ' <strong>' . esc_html(self::PAPER_EARLY_NOTE) . '</strong>'; }
        return $html . $link . '</p></div>';
    }

    /** Overblikkets kort over papirporteføljens stilling; tom streng uden snapshot eller handler. */
    public static function paper_brief(string $url): string {
        $data = self::snapshot();
        return $data === null ? '' : self::paper_brief_html(is_array($data['paper_score'] ?? null) ? $data['paper_score'] : null, $url);
    }

    // ----------------------------------------------------------------- Sizing

    private static function sizing(int $user_id): array {
        $raw = get_user_meta($user_id, self::SIZING_META, true);
        $raw = is_array($raw) ? $raw : [];
        $kapital = is_numeric($raw['kapital'] ?? null) ? (float)$raw['kapital'] : 100000.0;
        $valuta = is_string($raw['valuta'] ?? null) && in_array($raw['valuta'], self::CURRENCIES, true)
            ? $raw['valuta'] : 'DKK';
        $risiko = is_numeric($raw['risiko_pct'] ?? null) ? (float)$raw['risiko_pct'] : 0.75;
        $max = is_numeric($raw['max_pct'] ?? null) ? (float)$raw['max_pct'] : 3.0;
        if ($kapital <= 0 || $kapital > 1.0e10) { $kapital = 100000.0; }
        if ($risiko < 0.1 || $risiko > 5) { $risiko = 0.75; }
        if ($max < 0.5 || $max > 100) { $max = 3.0; }
        return ['kapital' => $kapital, 'valuta' => $valuta, 'risiko_pct' => $risiko, 'max_pct' => $max];
    }

    private static function decimal(string $raw): ?float {
        $raw = str_replace([' ', "\u{00A0}"], '', trim($raw));
        if ($raw === '') { return null; }
        if (str_contains($raw, ',')) { $raw = str_replace(',', '.', str_replace('.', '', $raw)); }
        elseif (preg_match('/^\d{1,3}(?:\.\d{3})+$/D', $raw) === 1) { $raw = str_replace('.', '', $raw); }
        if (preg_match('/^[0-9]+(?:\.[0-9]+)?$/D', $raw) !== 1) { return null; }
        $value = (float)$raw;
        return is_finite($value) ? $value : null;
    }

    public static function save_sizing(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_sizing_save');
        $field = static function (string $key): string {
            $value = $_POST[$key] ?? '';
            return is_string($value) ? trim(sanitize_text_field(wp_unslash($value))) : '';
        };
        $kapital = self::decimal($field('asc_kapital'));
        $valuta = strtoupper($field('asc_valuta'));
        $risiko = self::decimal($field('asc_risiko'));
        $max = self::decimal($field('asc_max'));
        $ok = $kapital !== null && $kapital > 0 && $kapital <= 1.0e10
            && in_array($valuta, self::CURRENCIES, true)
            && $risiko !== null && $risiko >= 0.1 && $risiko <= 5
            && $max !== null && $max >= 0.5 && $max <= 100;
        if ($ok) {
            update_user_meta(get_current_user_id(), self::SIZING_META, [
                'kapital' => $kapital, 'valuta' => $valuta,
                'risiko_pct' => $risiko, 'max_pct' => $max,
            ]);
        }
        $referer = wp_get_referer();
        $url = is_string($referer) ? wp_validate_redirect($referer, home_url('/')) : home_url('/');
        $url = add_query_arg('asc_sizing_status', $ok ? 'saved' : 'invalid',
            remove_query_arg('asc_sizing_status', $url));
        wp_safe_redirect($url . '#asc-playbook');
        exit;
    }

    /** Units of the user's currency per one unit of the stock's currency. */
    private static function fx_factor(string $stock_currency, string $user_currency): ?float {
        if ($stock_currency === $user_currency) { return 1.0; }
        $from = ASC_FX_Rates::to_dkk($stock_currency);
        $to = ASC_FX_Rates::to_dkk($user_currency);
        if ($from === null || $to === null) { return null; }
        $factor = (float)$from['rate'] / (float)$to['rate'];
        return is_finite($factor) && $factor > 0 ? $factor : null;
    }

    /** B-20: overskrifterne pr. aktie, sammenfoldet. */
    private static function render_news(array $rows): void {
        $marks = ['positiv' => '▲', 'negativ' => '▼', 'neutral' => '•', 'uvurderet' => '?'];
        $any = false;
        foreach ($rows as $ticker => $stock) {
            $items = is_array($stock['news'] ?? null) ? $stock['news'] : [];
            if (!$items) { continue; }
            if (!$any) {
                echo '<h3>Nyheder</h3><p class="asc-subtle">Overskrifter fra de seneste 7 dage (Google News), vurderet af '
                    . 'en lokal AI på PC\'en. Vurderingen kan tage fejl – læs selv nyheden.</p>';
                $any = true;
            }
            echo '<details class="asc-pb-news"><summary>' . esc_html((string)$ticker) . ' – '
                . self::s($stock['news_summary'] ?? null) . '</summary><ul>';
            foreach ($items as $item) {
                if (!is_array($item) || !is_string($item['url'] ?? null) || !is_string($item['title'] ?? null)) { continue; }
                $sentiment = is_string($item['sentiment'] ?? null) ? $item['sentiment'] : 'uvurderet';
                echo '<li class="asc-pb-news-' . esc_attr($sentiment) . '">'
                    . esc_html(($marks[$sentiment] ?? '?') . str_repeat('!', (int)($item['impact'] ?? 0) >= 3 ? 1 : 0)) . ' '
                    . self::s($item['published'] ?? null) . ' <a href="' . esc_url($item['url']) . '" rel="noopener nofollow" '
                    . 'target="_blank">' . esc_html($item['title']) . '</a> <span class="asc-subtle">('
                    . self::s($item['source'] ?? null) . ')';
                if (is_string($item['reason'] ?? null) && $item['reason'] !== '') {
                    echo ' – ' . esc_html($item['reason']);
                }
                echo '</span></li>';
            }
            echo '</ul></details>';
        }
    }

    /** @return array{shares:int,stop:float}|null */
    private static function position_size(array $stock, array $sizing): ?array {
        $price = $stock['price'] ?? null;
        $atr = $stock['atr14'] ?? null;
        $currency = $stock['currency'] ?? null;
        if (!is_numeric($price) || !is_numeric($atr) || !is_string($currency)
            || (float)$price <= 0 || (float)$atr <= 0) {
            return null;
        }
        $price = (float)$price;
        $stop = $price - 3 * (float)$atr;
        $fx = self::fx_factor($currency, $sizing['valuta']);
        if ($fx === null) { return null; }
        $risk_unit = 3 * (float)$atr * $fx;
        $price_unit = $price * $fx;
        if (!is_finite($risk_unit) || !is_finite($price_unit) || $risk_unit <= 0 || $price_unit <= 0) { return null; }
        $by_risk = $sizing['kapital'] * $sizing['risiko_pct'] / 100 / $risk_unit;
        $by_max = $sizing['kapital'] * $sizing['max_pct'] / 100 / $price_unit;
        $shares = floor(min($by_risk, $by_max));
        if (!is_finite($shares) || $shares < 0) { return null; }
        return ['shares' => (int)$shares, 'stop' => max($stop, 0.0)];
    }

    // -------------------------------------------------------------- Rendering

    private static function n($value, int $decimals = 0): string {
        return is_int($value) || is_float($value)
            ? number_format((float)$value, $decimals, ',', '.') : '–';
    }

    private static function s($value): string {
        return is_string($value) && $value !== '' ? esc_html($value) : '–';
    }

    /** Likviditetsklasse som mærkat (escaped HTML); "Lav" markeres, manglende felt er "–". */
    private static function liquidity_badge($value): string {
        if (!is_string($value) || $value === '') { return '–'; }
        $class = $value === 'Lav' ? 'asc-score asc-weak' : ($value === 'Høj' ? 'asc-score asc-strong' : '');
        return $class === '' ? esc_html($value) : '<span class="' . esc_attr($class) . '">' . esc_html($value) . '</span>';
    }

    // ------------------------------------------------------- Regnskab og risiko

    /** Dage fra i dag (site-tid, beregnes ved hver sidevisning) til datoen; negativ = afholdt, null = ukendt. */
    private static function earnings_days($iso): ?int {
        $clean = self::clean_date($iso);
        if ($clean === null) { return null; }
        $utc = new DateTimeZone('UTC');
        $now = wp_date('Y-m-d');
        if (!is_string($now)) { return null; }
        $today = DateTimeImmutable::createFromFormat('!Y-m-d', $now, $utc);
        $target = DateTimeImmutable::createFromFormat('!Y-m-d', $clean, $utc);
        if (!$today || !$target) { return null; }
        return (int)$today->diff($target)->format('%r%a');
    }

    private static function earnings_soon(?int $days): bool {
        return $days !== null && $days >= 0 && $days <= self::EARNINGS_BLOCK_DAYS;
    }

    /** Regnskabsdato med nedtælling (escaped HTML): "11-11-2026 (om 7 dage)"; rød inden for 7 dage. */
    public static function earnings_html($iso): string {
        $days = self::earnings_days($iso);
        if ($days === null) { return 'Dato ukendt'; }
        $clean = (string)$iso;
        $date = substr($clean, 8, 2) . '-' . substr($clean, 5, 2) . '-' . substr($clean, 0, 4);
        if ($days < 0) {
            $when = $days === -1 ? 'afholdt i går' : 'afholdt for ' . (-$days) . ' dage siden';
        } elseif ($days === 0) {
            $when = 'i dag';
        } else {
            $when = $days === 1 ? 'om 1 dag' : 'om ' . $days . ' dage';
        }
        $text = esc_html($date . ' (' . $when . ')');
        return self::earnings_soon($days) ? '<span class="asc-pb-sell">' . $text . '</span>' : $text;
    }

    /** Mærket "spærret: regnskab" på en KØB-KANDIDAT med regnskab inden for 7 dage (escaped HTML, ellers tom). */
    private static function earnings_block_badge(array $stock): string {
        if (($stock['action'] ?? null) !== 'KØB-KANDIDAT') { return ''; }
        return self::earnings_soon(self::earnings_days($stock['earnings'] ?? null))
            ? '<span class="asc-pb-sell">spærret: regnskab</span>' : '';
    }

    /** Beløbstekst til en position: DKK hvis kendt ("ca. 12.000 kr."), ellers i aktiens valuta; null uden værdi. */
    private static function risk_amount(?float $avg_move, ?float $value, ?float $value_dkk, string $currency): ?string {
        if ($avg_move === null) { return null; }
        $base = $value_dkk ?? $value;
        if ($base === null || $base <= 0) { return null; }
        $amount = $base * $avg_move / 100;
        $step = $amount >= 1000 ? 100 : 10;
        $rounded = round($amount / $step) * $step;
        return 'ca. ' . number_format($rounded, 0, ',', '.') . ' ' . ($value_dkk !== null ? 'kr.' : $currency)
            . ' på din position';
    }

    /**
     * Regnskabsrisiko som tekst (escaped HTML); tom uden payload-data. $amount er den færdige beløbstekst
     * (kun i porteføljen). Risikomål, aldrig et salgssignal.
     */
    private static function risk_html(array $stock, ?string $amount = null): string {
        $risk = $stock['earnings_risk'] ?? null;
        if (!is_array($risk) || !in_array($risk['level'] ?? null, self::RISK_LEVELS, true)) { return ''; }
        $level = (string)$risk['level'];
        $class = $level === 'Høj' ? 'asc-pb-sell' : ($level === 'Middel' ? 'asc-risk-mid' : '');
        $html = 'Regnskabsrisiko: <strong' . ($class !== '' ? ' class="' . esc_attr($class) . '"' : '') . '>'
            . esc_html($level) . '</strong>';
        $reasons = [];
        foreach (is_array($risk['reasons'] ?? null) ? $risk['reasons'] : [] as $reason) {
            if (is_string($reason) && $reason !== '') { $reasons[] = $reason; }
        }
        if ($reasons) { $html .= ' – ' . esc_html(implode('; ', $reasons)); }
        $avg = is_numeric($risk['avg_move_pct'] ?? null) ? (float)$risk['avg_move_pct'] : null;
        $count = is_int($risk['count'] ?? null) ? $risk['count'] : 0;
        if ($avg === null) {
            $html .= '. Regnskabsbevægelse: for få regnskaber (' . esc_html((string)$count) . ')';
        } else {
            $html .= '. Plejer at bevæge sig ±' . esc_html(self::n($avg, 0)) . ' %';
            if ($amount !== null) { $html .= ', ' . esc_html($amount); }
            if (is_numeric($risk['down_share_pct'] ?? null)) {
                $html .= ' (faldt i ' . esc_html(self::n((float)$risk['down_share_pct'])) . ' % af '
                    . esc_html((string)$count) . ' regnskaber)';
            }
        }
        return $html . '. ' . esc_html(self::RISK_DISCLAIMER);
    }

    /**
     * Regnskabsrisiko på en ejet position i porteføljen (hel tabelrække, escaped HTML). Tom uden payload-data.
     * Beløbet er positionens værdi × aktiens typiske regnskabsbevægelse.
     */
    public static function earnings_risk_row(string $ticker, ?float $value, ?float $value_dkk, string $currency, int $columns): string {
        $data = self::snapshot();
        $stock = $data !== null && is_array($data['stocks'][$ticker] ?? null) ? $data['stocks'][$ticker] : null;
        if ($stock === null || !is_array($stock['earnings_risk'] ?? null)) { return ''; }
        $avg = is_numeric($stock['earnings_risk']['avg_move_pct'] ?? null)
            ? (float)$stock['earnings_risk']['avg_move_pct'] : null;
        $text = self::risk_html($stock, self::risk_amount($avg, $value, $value_dkk, $currency));
        if ($text === '') { return ''; }
        return '<tr class="asc-rule-row"><td colspan="' . $columns . '"><div>Regnskab: '
            . self::earnings_html($stock['earnings'] ?? null) . '. ' . $text . '</div></td></tr>';
    }

    private static function query_text(string $key): string {
        return isset($_GET[$key]) && is_string($_GET[$key])
            ? sanitize_text_field(wp_unslash($_GET[$key])) : '';
    }

    public static function render(): string {
        if (!is_user_logged_in()) {
            $url = wp_login_url(get_permalink());
            return '<p>Log ind for at se playbook. <a href="' . esc_url($url) . '">Log ind</a></p>';
        }
        wp_enqueue_style('hangar18-asc');
        $data = self::snapshot();
        ob_start();
        echo '<section class="asc-dashboard"><div class="asc-portfolio asc-playbook" id="asc-playbook">';
        echo '<div class="asc-section-title"><h2>Playbook</h2>'
            . '<p>Ugentlig mandagsliste, screenere og aktie-scores fra den lokale scanner.</p></div>';
        if ($data === null) {
            echo '<div class="asc-empty">Ingen playbook modtaget endnu. PC-programmet sender data til hjemmesiden '
                . 'efter hver kørsel af mandagslisten (mandag morgen eller via knappen i appen). '
                . 'Når den første kørsel er sendt, vises listen her.</div>';
            echo self::footer();
            echo '</div></section>';
            return (string)ob_get_clean();
        }

        $tabs = [
            'mandag' => 'Mandagsliste',
            'screener' => 'Screenere',
            'value' => 'Find aktier',
            'scores' => 'Aktie-scores',
            'papir' => 'Papirportefølje',
        ];
        $tab = sanitize_key(self::query_text('asc_tab'));
        if (!isset($tabs[$tab])) { $tab = 'mandag'; }
        $base = remove_query_arg(
            ['asc_tab', 'asc_q', 'asc_screen', 'asc_region', 'asc_liq', 'asc_sizing_status'],
            add_query_arg([])
        );

        echo '<p class="asc-updated">Opdateret ' . esc_html(self::when((string)$data['generated_at'])) . '</p>';
        $breadth = is_array($data['breadth'] ?? null) ? $data['breadth'] : [];
        $b50 = $breadth['50'] ?? null;
        if (is_int($b50) || is_float($b50)) {
            $bull = (float)$b50 > 50;
            echo '<p class="asc-pb-breadth"><span class="asc-score ' . ($bull ? 'asc-strong' : 'asc-weak') . '">'
                . ($bull ? 'Bull' : 'Ikke bull') . '</span> Markedsbredde: '
                . esc_html(self::n($breadth['20'] ?? null, 0)) . ' % over 20-dages, '
                . esc_html(self::n($b50, 0)) . ' % over 50-dages, '
                . esc_html(self::n($breadth['200'] ?? null, 0)) . ' % over 200-dages gennemsnit.</p>';
        }

        echo '<nav class="asc-pb-tabs" aria-label="Playbook">';
        foreach ($tabs as $key => $label) {
            echo '<a class="asc-pb-tab' . ($tab === $key ? ' is-active' : '') . '" href="'
                . esc_url(add_query_arg('asc_tab', $key, $base)) . '"'
                . ($tab === $key ? ' aria-current="page"' : '') . '>' . esc_html($label) . '</a>';
        }
        echo '</nav>';

        if ($tab === 'screener') { self::tab_screener($data); }
        elseif ($tab === 'value') { self::tab_value($data); }
        elseif ($tab === 'scores') { self::tab_scores($data); }
        elseif ($tab === 'papir') { self::tab_paper($data); }
        else { self::tab_monday($data); }

        echo self::footer();
        echo '</div></section>';
        return (string)ob_get_clean();
    }

    private static function footer(): string {
        return '<p class="asc-disclaimer">Screening efter egne regler inspireret af MSS – '
            . 'ikke købs- eller salgsanbefalinger.</p>';
    }

    private static function hidden_view(string $tab): string {
        $html = '<input type="hidden" name="asc_tab" value="' . esc_attr($tab) . '">';
        $view = sanitize_key(self::query_text('asc_view'));
        if ($view !== '') {
            $html .= '<input type="hidden" name="asc_view" value="' . esc_attr($view) . '">';
        }
        return $html;
    }

    private static function tab_monday(array $data): void {
        $user_id = get_current_user_id();
        $sizing = self::sizing($user_id);
        // Scanneren analyserer alle aktier, men hver bruger ser kun research-listen, tragtens kandidater og sine egne.
        $lots_by_ticker = self::user_lots($user_id);
        $wanted = self::visible_tickers($data, self::user_watch($user_id), array_map('strval', array_keys($lots_by_ticker)),
            self::user_sim_tickers($user_id));
        // Tragtens fund i hele universet (StockMap-køb + Quality ≥ 60) vises for alle.
        $from_universe = [];
        foreach (is_array($data['candidates'] ?? null) ? $data['candidates'] : [] as $symbol) {
            if (is_string($symbol)) { $from_universe[$symbol] = true; }
        }
        $universe = self::universe_index($data);
        $rows = [];
        foreach ($data['stocks'] as $ticker => $stock) {
            $ticker = (string)$ticker;
            if (isset($wanted[$ticker]) && is_array($stock)) {
                // "(ejet)" og "% siden køb" kun for aktier i brugerens egen portefølje.
                $rows[$ticker] = self::personal_stock($stock, $lots_by_ticker[$ticker] ?? []);
            }
        }
        uksort($rows, static function ($a, $b) use ($rows): int {
            $pa = self::ACTION_ORDER[(string)($rows[$a]['action'] ?? '')] ?? 9;
            $pb = self::ACTION_ORDER[(string)($rows[$b]['action'] ?? '')] ?? 9;
            if ($pa !== $pb) { return $pa <=> $pb; }
            $qa = is_numeric($rows[$a]['quality'] ?? null) ? (float)$rows[$a]['quality'] : -1.0;
            $qb = is_numeric($rows[$b]['quality'] ?? null) ? (float)$rows[$b]['quality'] : -1.0;
            if ($qa !== $qb) { return $qb <=> $qa; }
            return strcmp((string)$a, (string)$b);
        });

        $status = sanitize_key(self::query_text('asc_sizing_status'));
        if ($status === 'saved') {
            echo '<p role="status" class="asc-notice">Positionsstørrelse er gemt.</p>';
        } elseif ($status === 'invalid') {
            echo '<div class="asc-notice-error" role="alert">Ugyldige værdier. Kapital skal være positiv, '
                . 'risiko 0,1–5 % og maks pr. aktie 0,5–100 %.</div>';
        }

        echo '<h3>Mandagsliste</h3>';
        echo '<p class="asc-subtle">Din overvågningsliste, din portefølje, din simulator og den fælles research-liste. '
            . '★ = fundet ved scanning af hele universet (StockMap-køb og kvalitet ≥ 60), analyseret fuldt på samme måde. '
            . 'BEHOLD/SÆLG (ejet) og gevinst siden køb vises kun for aktier i din egen portefølje på hjemmesiden; '
            . 'andre brugeres lister er aldrig med.</p>';
        $changes = self::visible_changes(is_array($data['changes'] ?? null) ? $data['changes'] : [], $wanted);
        if ($changes) {
            echo '<div class="asc-pb-changes"><strong>Ændringer siden sidst</strong><ul>';
            foreach ($changes as $change) {
                echo '<li>' . esc_html($change) . '</li>';
            }
            echo '</ul></div>';
        }

        $buy_sectors = [];
        foreach ($rows as $ticker => $stock) {
            if (($stock['action'] ?? null) === 'KØB-KANDIDAT') {
                $buy_sectors[] = self::sector_of($stock, $universe[$ticker] ?? []);
            }
        }
        echo self::concentration_html($buy_sectors, self::SECTOR_MIN_TOTAL, self::SECTOR_MAX_ENTRIES, 'købskandidater');
        if (!$rows) {
            echo '<p class="asc-empty">Ingen af dine overvågede aktier er med i seneste playbook. '
                . 'Følg aktier på din overvågningsliste, så sendes de med ved næste kørsel.</p>';
        } else {
            echo '<div class="asc-table-wrap"><table><thead><tr>';
            foreach (['Aktie', 'Sektor', 'Handling', 'StockMap', 'TPI', 'MTI', 'Kvalitet', 'Moat', 'MSS-score',
                      'Værdi', 'Momentum', 'Kanal', 'PEG', 'Asymmetri', 'Regnskab', 'Størrelsesklasse', 'Likviditet', 'Størrelse',
                      'Nyheder', 'Begrundelse'] as $head) {
                echo '<th scope="col">' . esc_html($head) . '</th>';
            }
            echo '</tr></thead><tbody>';
            foreach ($rows as $ticker => $stock) {
                $action = (string)($stock['action'] ?? '');
                $class = '';
                if (str_starts_with($action, 'SÆLG')) { $class = 'asc-pb-sell'; }
                elseif ($action === 'KØB-KANDIDAT') { $class = 'asc-pb-buy'; }
                $size = '';
                if ($action === 'KØB-KANDIDAT') {
                    $calc = self::position_size($stock, $sizing);
                    $size = $calc === null ? '–'
                        : esc_html(self::n($calc['shares']) . ' stk. · stop ' . self::n($calc['stop'], 2));
                }
                echo '<tr><th scope="row">' . ASC_Stock_Page::link((string)$ticker)
                    . (isset($from_universe[$ticker]) ? ' <span class="asc-subtle" title="Fundet i hele universet">★</span>' : '')
                    . ($action === 'KØB-KANDIDAT' ? '<div class="asc-subtle">' . self::simulator_link((string)$ticker) . '</div>' : '')
                    . '</th>';
                echo '<td>' . esc_html(self::sector_of($stock, $universe[$ticker] ?? [])) . '</td>';
                echo '<td class="' . esc_attr($class) . '">' . self::s($action)
                    . (self::earnings_block_badge($stock) !== '' ? '<div>' . self::earnings_block_badge($stock) . '</div>' : '') . '</td>';
                echo '<td>' . self::s($stock['stockmap'] ?? null) . '</td>';
                echo '<td>' . self::s($stock['tpi'] ?? null) . '</td>';
                echo '<td>' . self::s($stock['mti'] ?? null) . '</td>';
                echo '<td>' . esc_html(self::n($stock['quality'] ?? null)) . '</td>';
                echo '<td>' . esc_html(self::n($stock['moat'] ?? null)) . '</td>';
                echo '<td>' . esc_html(self::n($stock['mss_score'] ?? null)) . '</td>';
                echo '<td>' . esc_html(self::n($stock['value_pct'] ?? null)) . '</td>';
                echo '<td>' . esc_html(self::n($stock['momentum'] ?? null)) . '</td>';
                echo '<td>' . esc_html(self::n($stock['channel_score'] ?? null)) . '</td>';
                echo '<td>' . esc_html(self::n($stock['peg'] ?? null, 1)) . '</td>';
                echo '<td>' . (!empty($stock['asymmetry_inf']) ? '∞'
                    : esc_html(self::n($stock['asymmetry'] ?? null, 1))) . '</td>';
                echo '<td>' . self::earnings_html($stock['earnings'] ?? null) . '</td>';
                echo '<td>' . self::s($stock['size'] ?? null) . '</td>';
                echo '<td>' . self::liquidity_badge($stock['liquidity'] ?? null) . '</td>';
                echo '<td>' . ($size === '' ? '' : $size) . '</td>';
                echo '<td>' . self::s($stock['news_summary'] ?? null) . '</td>';
                echo '<td class="asc-subtle">' . self::s($stock['reasons'] ?? null) . '</td></tr>';
                $risk = self::risk_html($stock);
                if ($risk !== '') {
                    echo '<tr class="asc-rule-row"><td colspan="20"><div>' . $risk . '</div></td></tr>';
                }
            }
            echo '</tbody></table></div>';
            self::render_news($rows);
        }

        echo '<div class="asc-add-position asc-pb-sizing"><h3>Positionsstørrelse</h3>';
        echo '<p class="asc-subtle">Antal beregnes med stop = kurs − 3 × ATR(14), så tabet ved stop højst er den valgte '
            . 'risiko af kapitalen, og aldrig over maks pr. aktie. Valutaomregning sker med ECB-kurser.</p>';
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_sizing_save">';
        wp_nonce_field('asc_sizing_save');
        echo '<label>Kapital <input name="asc_kapital" type="text" inputmode="decimal" value="'
            . esc_attr(number_format($sizing['kapital'], 2, ',', '.')) . '" required></label>';
        echo '<label>Valuta<select name="asc_valuta">';
        foreach (self::CURRENCIES as $currency) {
            echo '<option value="' . esc_attr($currency) . '"'
                . selected($sizing['valuta'], $currency, false) . '>' . esc_html($currency) . '</option>';
        }
        echo '</select></label>';
        echo '<label>Risiko pr. handel (%) <input name="asc_risiko" type="text" inputmode="decimal" value="'
            . esc_attr(number_format($sizing['risiko_pct'], 2, ',', '.')) . '" required></label>';
        echo '<label>Maks pr. aktie (%) <input name="asc_max" type="text" inputmode="decimal" value="'
            . esc_attr(number_format($sizing['max_pct'], 2, ',', '.')) . '" required></label>';
        echo '<button type="submit">Gem indstillinger</button></form></div>';
    }

    /** @return array<string,array> universe rows keyed by ticker */
    private static function universe_index(array $data): array {
        $index = [];
        $universe = is_array($data['universe'] ?? null) ? $data['universe'] : [];
        $columns = is_array($universe['columns'] ?? null) ? $universe['columns'] : [];
        foreach (is_array($universe['rows'] ?? null) ? $universe['rows'] : [] as $row) {
            if (!is_array($row) || count($row) !== count($columns)) { continue; }
            $named = array_combine($columns, $row);
            if (is_array($named) && is_string($named['ticker'] ?? null)) {
                $index[$named['ticker']] = $named;
            }
        }
        return $index;
    }

    private static function tab_screener(array $data): void {
        $screeners = is_array($data['screeners'] ?? null) ? $data['screeners'] : [];
        $key = sanitize_key(self::query_text('asc_screen'));
        if (!isset($screeners[$key])) { $key = self::SCREENERS[0]; }
        $regional = self::query_text('asc_region') === '1';
        $screen = is_array($screeners[$key] ?? null) ? $screeners[$key] : [];
        $hits = self::clean_ticker_list($screen[$regional ? 'regional' : 'global'] ?? null, self::MAX_UNIVERSE);
        $index = self::universe_index($data);

        echo '<h3>Screenere</h3>';
        echo '<form class="asc-filter-form" method="get">' . self::hidden_view('screener');
        echo '<label>Screener<select name="asc_screen">';
        foreach (self::SCREENERS as $name) {
            $item = is_array($screeners[$name] ?? null) ? $screeners[$name] : [];
            echo '<option value="' . esc_attr($name) . '"' . selected($key, $name, false) . '>'
                . esc_html((string)($item['label'] ?? $name)) . '</option>';
        }
        echo '</select></label>';
        echo '<label><span><input type="checkbox" name="asc_region" value="1"'
            . checked($regional, true, false) . '> pr. region</span></label>';
        echo '<button type="submit">Vis</button></form>';
        echo '<p class="asc-updated">' . esc_html((string)count($hits)) . ' aktier'
            . ($regional ? ' (rangeret inden for region)' : ' (rangeret mod hele universet)') . '.</p>';

        if (!$hits) {
            echo '<p class="asc-empty">Ingen aktier opfylder reglen i denne kørsel.</p>';
            return;
        }
        $suffix = $regional ? '_r' : '';
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        foreach (['Aktie', 'Region', 'Kvalitet', 'Værdi', 'Momentum', 'Moat', 'Upside %', 'PEG', 'Mkt.værdi (mia. USD)',
                  'Størrelse', 'Likviditet'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach (array_slice($hits, 0, self::MAX_UNIVERSE) as $ticker) {
            $row = $index[$ticker] ?? [];
            echo '<tr><th scope="row">' . ASC_Stock_Page::link((string)$ticker)
                . '<div class="asc-subtle">' . self::simulator_link((string)$ticker) . '</div></th>';
            echo '<td>' . self::s($row['region'] ?? null) . '</td>';
            foreach (['quality', 'value', 'momentum', 'moat'] as $metric) {
                echo '<td>' . esc_html(self::n($row[$metric . $suffix] ?? null)) . '</td>';
            }
            echo '<td>' . esc_html(self::n($row['upside'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['peg'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['mcap_usd_bn'] ?? null, 1)) . '</td>';
            echo '<td>' . self::s($row['size'] ?? null) . '</td>';
            echo '<td>' . self::liquidity_badge($row['liquidity'] ?? null) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    /**
     * Entry-vurdering for én aktie i universet. Alle universets aktier med StockMap-køb og Kvalitet mindst 60
     * analyseres fuldt på mandagslisten, så en aktie uden for listen har ikke et aktuelt købssignal.
     * @return array{0: int, 1: string} Rang (0 = Entry, 1 = Vent, 2 = Nej, 3 = ukendt) og tekst.
     */
    public static function entry_verdict(?array $stock, array $row, ?array $scenarios): array {
        $action = (string)($stock['action'] ?? '');
        if ($action === 'KØB-KANDIDAT') { return [0, 'Entry']; }
        if ($action === 'pil ned') { return [2, 'Nej: salgssignal']; }
        if (($stock['liquidity'] ?? $row['liquidity'] ?? null) === 'Lav') { return [2, 'Nej: for lidt handel']; }
        $quality = $stock['quality'] ?? $row['quality'] ?? null;
        if (is_numeric($quality) && (float)$quality < 60) { return [2, 'Nej: svag kvalitet']; }
        $channel = $stock['channel_score'] ?? $scenarios['channel_score'] ?? null;
        if (!is_numeric($channel)) { return [3, 'Ingen vurdering: mangler tal']; }
        if ((float)$channel < 50) { return [2, 'Nej: ikke billig']; }
        return [1, 'Vent: billig, men intet købssignal'];
    }

    /** Universets aktier med entry-vurdering, bedste først. @return array<int, array<string, mixed>> */
    private static function value_rows(array $data): array {
        $rows = [];
        foreach (self::universe_index($data) as $ticker => $row) {
            $ticker = (string)$ticker;
            $stock = is_array($data['stocks'][$ticker] ?? null) ? $data['stocks'][$ticker] : null;
            $scenarios = self::scenarios_for($ticker);
            [$rank, $text] = self::entry_verdict($stock, $row, $scenarios);
            $upside = $scenarios['upside_pct']['base'] ?? null;
            $rows[] = [
                'ticker' => $ticker, 'row' => $row, 'stock' => $stock, 'sc' => $scenarios, 'rank' => $rank, 'text' => $text,
                'sort' => is_numeric($upside) ? (float)$upside : -1.0e9,
            ];
        }
        usort($rows, static fn(array $a, array $b): int => [$a['rank'], -$a['sort']] <=> [$b['rank'], -$b['sort']]);
        return $rows;
    }

    /** Siden Find aktier: de bedste muligheder fra hele universet. */
    public static function render_find(): string {
        wp_enqueue_style('hangar18-asc');
        $data = self::snapshot();
        ob_start();
        echo '<section class="asc-playbook">';
        if ($data === null) {
            echo '<p class="asc-empty">Ingen scanning modtaget endnu.</p>';
        } else {
            echo '<p class="asc-updated">Opdateret ' . esc_html(self::when((string)$data['generated_at'])) . '</p>';
            self::tab_value($data);
        }
        echo '</section>';
        return (string)ob_get_clean();
    }

    /** Forsidens kort: op til fem aktier med entry nu. Tom streng uden data. */
    public static function top_opportunities(string $more_url): string {
        $data = self::snapshot();
        if ($data === null) { return ''; }
        $rows = self::value_rows($data);
        $best = array_slice(array_values(array_filter($rows, static fn(array $r): bool => $r['rank'] === 0)), 0, 5);
        $waiting = count(array_filter($rows, static fn(array $r): bool => $r['rank'] === 1));
        $entry_sectors = [];
        foreach ($rows as $item) {
            if ($item['rank'] === 0) { $entry_sectors[] = self::sector_of($item['stock'], $item['row']); }
        }
        $html = '<div class="asc-top-picks"><h2>Aktier med entry nu</h2>';
        if (!$best) {
            $html .= '<p>Ingen aktier opfylder alle købskrav lige nu.</p>';
        } else {
            $html .= '<ul>';
            foreach ($best as $item) {
                $sc = is_array($item['sc']) ? $item['sc'] : [];
                $stock = is_array($item['stock']) ? $item['stock'] : [];
                $html .= '<li>' . ASC_Stock_Page::link($item['ticker']) . ' <span>Kvalitet '
                    . esc_html(self::n($item['row']['quality'] ?? null)) . ', Kanal '
                    . esc_html(self::n($stock['channel_score'] ?? $sc['channel_score'] ?? null)) . ', Base '
                    . esc_html(self::n($sc['upside_pct']['base'] ?? null, 1)) . ' %</span> '
                    . self::earnings_block_badge($stock) . '</li>';
            }
            $html .= '</ul>';
        }
        $html .= self::entry_concentration_html($entry_sectors);
        return $html . '<p>' . esc_html((string)$waiting) . ' billige aktier venter på købssignal. <a href="'
            . esc_url($more_url) . '">Se alle muligheder</a></p>'
            . '<p class="asc-disclaimer">Screening efter faste regler, ikke en købsanbefaling.</p></div>';
    }

    /** Værdi & entry: er aktien billig, og er der en entry nu? Fælles markedsdata for hele universet. */
    private static function tab_value(array $data): void {
        $all = self::value_rows($data);
        $count = static fn(int $rank): int => count(array_filter($all, static fn(array $r): bool => $r['rank'] === $rank));
        $entries = $count(0);
        $waiting = $count(1);
        $show = sanitize_key(self::query_text('asc_show'));
        if (!in_array($show, ['best', 'entry', 'all'], true)) { $show = 'best'; }
        $rows = array_values(array_filter($all, static fn(array $r): bool =>
            $show === 'all' || $r['rank'] === 0 || ($show === 'best' && $r['rank'] === 1)));
        echo '<h2>Find aktier</h2>';
        echo '<p class="asc-subtle">Gode selskaber, der er billige i forhold til deres egen værdi, og som har et signal til '
            . 'entry. Entry: alle købskrav er opfyldt. Vent: god og billig, men StockMap har ikke givet købssignal. '
            . 'En regelbaseret screening, ikke en købsanbefaling.</p>';
        $entry_sectors = [];
        foreach ($all as $item) {
            if ($item['rank'] === 0) { $entry_sectors[] = self::sector_of($item['stock'], $item['row']); }
        }
        echo self::entry_concentration_html($entry_sectors);
        if ($entry_sectors) {
            echo '<p class="asc-subtle asc-pb-sector-line">Entry pr. sektor: ' . self::sector_count_line($entry_sectors) . '</p>';
        }
        echo '<nav class="asc-pb-tabs" aria-label="Vis aktier">';
        foreach ([
            'best' => 'Bedste muligheder (' . ($entries + $waiting) . ')',
            'entry' => 'Kun entry nu (' . $entries . ')',
            'all' => 'Alle aktier (' . count($all) . ')',
        ] as $key => $label) {
            echo '<a class="asc-pb-tab' . ($show === $key ? ' is-active' : '') . '" href="'
                . esc_url(add_query_arg('asc_show', $key)) . '"' . ($show === $key ? ' aria-current="true"' : '') . '>'
                . esc_html($label) . '</a>';
        }
        echo '</nav>';
        if (!$rows) {
            echo '<p class="asc-empty">Ingen aktier opfylder kravene i denne kørsel.</p>';
            return;
        }
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        foreach (['Aktie', 'Sektor', 'Entry', 'Kanal', 'Bear %', 'Base %', 'Asymmetri', 'Kvalitet', 'Værdi', 'PEG', 'Størrelse', 'Likviditet'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach ($rows as $item) {
            $row = $item['row'];
            $sc = is_array($item['sc']) ? $item['sc'] : [];
            $stock = is_array($item['stock']) ? $item['stock'] : [];
            echo '<tr><th scope="row">' . ASC_Stock_Page::link($item['ticker']) . '</th>';
            echo '<td>' . esc_html(self::sector_of($stock, $row)) . '</td>';
            echo '<td>' . ($item['rank'] === 0 ? '<strong>' . esc_html($item['text']) . '</strong>' : esc_html($item['text']))
                . ($item['rank'] === 0 ? ' ' . self::earnings_block_badge($stock) : '') . '</td>';
            echo '<td>' . esc_html(self::n($stock['channel_score'] ?? $sc['channel_score'] ?? null)) . '</td>';
            echo '<td>' . esc_html(self::n($sc['upside_pct']['bear'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($sc['upside_pct']['base'] ?? null, 1)) . '</td>';
            echo '<td>' . (!empty($sc['asymmetry_inf']) ? '∞' : esc_html(self::n($sc['asymmetry'] ?? null, 1))) . '</td>';
            echo '<td>' . esc_html(self::n($row['quality'] ?? null)) . '</td>';
            echo '<td>' . esc_html(self::n($row['value'] ?? null)) . '</td>';
            echo '<td>' . esc_html(self::n($row['peg'] ?? null, 1)) . '</td>';
            echo '<td>' . self::s($row['size'] ?? null) . '</td>';
            echo '<td>' . self::liquidity_badge($row['liquidity'] ?? null) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function tab_scores(array $data): void {
        $query = strtoupper(self::query_text('asc_q'));
        $query = preg_replace('/[^A-Z0-9.^=-]/', '', $query);
        $query = is_string($query) ? self::cut($query, 20) : '';
        $index = self::universe_index($data);
        $hide_thin = self::query_text('asc_liq') === '1';
        $matches = [];
        foreach ($index as $ticker => $row) {
            if ($hide_thin && ($row['liquidity'] ?? null) === 'Lav') { continue; }
            if ($query === '' || str_contains((string)$ticker, $query)) { $matches[(string)$ticker] = $row; }
        }
        uasort($matches, static function (array $a, array $b): int {
            $qa = is_numeric($a['quality'] ?? null) ? (float)$a['quality'] : -1.0;
            $qb = is_numeric($b['quality'] ?? null) ? (float)$b['quality'] : -1.0;
            return $qb <=> $qa;
        });
        $limit = 100;

        echo '<h3>Aktie-scores</h3>';
        echo '<form class="asc-filter-form" method="get">' . self::hidden_view('scores');
        echo '<label>Søg ticker <input type="text" name="asc_q" maxlength="20" value="'
            . esc_attr($query) . '" placeholder="fx MSFT"></label>';
        echo '<label><span><input type="checkbox" name="asc_liq" value="1"' . checked($hide_thin, true, false)
            . '> skjul tyndt handlede (lav likviditet)</span></label>';
        echo '<button type="submit">Søg</button></form>';
        echo '<p class="asc-updated">Viser ' . esc_html((string)min($limit, count($matches))) . ' af '
            . esc_html((string)count($matches)) . ' aktier. Tal er percentiler (global / region).</p>';
        if (!$matches) {
            echo '<p class="asc-empty">Ingen aktier fundet.</p>';
            return;
        }
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        foreach (['Aktie', 'Region', 'Kvalitet', 'Værdi', 'Momentum', 'Moat', 'Upside %', 'PEG', 'Mkt.værdi (mia. USD)',
                  'Størrelse', 'Likviditet'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach (array_slice($matches, 0, $limit, true) as $ticker => $row) {
            echo '<tr><th scope="row">' . ASC_Stock_Page::link((string)$ticker) . '</th>';
            echo '<td>' . self::s($row['region'] ?? null) . '</td>';
            foreach (['quality', 'value', 'momentum', 'moat'] as $metric) {
                echo '<td>' . esc_html(self::n($row[$metric] ?? null) . ' / '
                    . self::n($row[$metric . '_r'] ?? null)) . '</td>';
            }
            echo '<td>' . esc_html(self::n($row['upside'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['peg'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['mcap_usd_bn'] ?? null, 1)) . '</td>';
            echo '<td>' . self::s($row['size'] ?? null) . '</td>';
            echo '<td>' . self::liquidity_badge($row['liquidity'] ?? null) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function tab_paper(array $data): void {
        $paper = is_array($data['paper'] ?? null) ? $data['paper'] : [];
        $summary = is_array($paper['summary'] ?? null) ? $paper['summary'] : [];
        $trades = is_array($paper['trades'] ?? null) ? $paper['trades'] : [];
        echo '<h3>Papirportefølje</h3>';
        echo '<p class="asc-subtle">Scannerens egen papirportefølje, fælles for alle brugere. '
            . 'Den er ikke din portefølje og ændres kun af scanneren.</p>';
        echo self::paper_score_html(is_array($data['paper_score'] ?? null) ? $data['paper_score'] : null);
        echo '<div class="asc-metrics asc-portfolio-summary">';
        echo '<div><strong>' . esc_html(self::n($summary['handler'] ?? null)) . '</strong><span>Handler</span></div>';
        echo '<div><strong>' . esc_html(self::n($summary['aabne'] ?? null)) . '</strong><span>Åbne positioner</span></div>';
        echo '<div><strong>' . esc_html(self::n($summary['afkast_pct'] ?? null, 1)) . ' %</strong><span>Afkast</span></div>';
        echo '<div><strong>' . esc_html(self::n($summary['vundne_pct'] ?? null, 0)) . ' %</strong><span>Vundne handler</span></div>';
        echo '</div>';
        if (!$trades) {
            echo '<p class="asc-empty">Ingen papirhandler endnu.</p>';
            return;
        }
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        foreach (['Aktie', 'Købsdato', 'Købskurs', 'Salgsdato', 'Salgskurs / seneste', 'Afkast', 'Salgsgrund'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach ($trades as $trade) {
            if (!is_array($trade)) { continue; }
            $buy = $trade['koebskurs'] ?? null;
            $exit = $trade['salgskurs'] ?? null;
            $closed = is_int($exit) || is_float($exit);
            $last = $closed ? $exit : ($trade['seneste'] ?? null);
            $return = (is_int($buy) || is_float($buy)) && $buy > 0 && (is_int($last) || is_float($last))
                ? ((float)$last / (float)$buy - 1) * 100 : null;
            $class = $return === null ? '' : ($return >= 0 ? 'asc-positive' : 'asc-negative');
            echo '<tr><th scope="row">' . ASC_Stock_Page::link((string)($trade['ticker'] ?? '')) . '</th>';
            echo '<td>' . self::s($trade['koebsdato'] ?? null) . '</td>';
            echo '<td>' . esc_html(self::n($buy, 2)) . '</td>';
            echo '<td>' . self::s($trade['salgsdato'] ?? null) . '</td>';
            echo '<td>' . esc_html(self::n($last, 2)) . ($closed ? '' : ' <span class="asc-subtle">(seneste)</span>') . '</td>';
            echo '<td class="' . esc_attr($class) . '">'
                . ($return === null ? '–' : esc_html(($return > 0 ? '+' : '') . self::n($return, 1) . ' %')) . '</td>';
            echo '<td class="asc-subtle">' . self::s($trade['salgsgrund'] ?? null) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }
}
