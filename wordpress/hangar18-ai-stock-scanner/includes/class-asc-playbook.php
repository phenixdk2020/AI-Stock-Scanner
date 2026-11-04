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
    private const TICKER_RE = '/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D';
    private const DATE_RE = '/^\d{4}-\d\d-\d\d$/D';
    private const MAX_BODY = 3145728;
    private const MAX_STOCKS = 600;
    private const MAX_UNIVERSE = 2000;
    private const MAX_TRADES = 1000;
    private const UNIVERSE_COLUMNS = [
        'ticker', 'region', 'quality', 'value', 'momentum', 'moat',
        'quality_r', 'value_r', 'momentum_r', 'moat_r', 'upside', 'peg', 'mcap_usd_bn',
    ];
    private const SCREENERS = ['triple-green', 'tpi-trend', 'stock-of-the-day'];
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

    /** @return string[] Unikke symboler fra alle brugeres watchlists og porteføljer (ingen brugerdata). */
    public static function followed_tickers(): array {
        global $wpdb;
        $found = $wpdb->get_results(
            $wpdb->prepare(
                "SELECT meta_key, meta_value FROM {$wpdb->usermeta} WHERE meta_key IN (%s, %s)",
                self::WATCH_META,
                self::PORTFOLIO_META
            ),
            ARRAY_A
        );
        $symbols = [];
        foreach (is_array($found) ? $found : [] as $row) {
            $value = maybe_unserialize($row['meta_value'] ?? '');
            if (!is_array($value)) { continue; }
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
            'screeners' => self::clean_screeners($input['screeners'] ?? null),
            'paper' => self::clean_paper($input['paper'] ?? null),
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
            'news_summary' => 300,
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
        $breaks = [];
        if (is_array($exit['sma50_breaks'] ?? null)) {
            foreach ($exit['sma50_breaks'] as $date) {
                $date = self::clean_date($date);
                if ($date !== null) { $breaks[] = $date; }
            }
            $breaks = array_slice($breaks, -60); // de seneste brud tæller for salgsreglen
        }
        $out['exit'] = [
            'supertrend_down' => ($exit['supertrend_down'] ?? false) === true,
            'stockmap_sell' => ($exit['stockmap_sell'] ?? false) === true,
            'sma50_breaks' => $breaks,
        ];
        $out['news'] = self::clean_news($raw['news'] ?? null);
        return $out;
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
                elseif ($name === 'region') { $clean[] = self::clean_string($value, 40); }
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
     * Sell rule for an owned lot, used by the portfolio table. Returns the
     * complete, escaped table cell.
     */
    public static function exit_rule_cell(string $ticker, string $buy_date): string {
        $data = self::snapshot();
        $stock = $data !== null && is_array($data['stocks'][$ticker] ?? null)
            ? $data['stocks'][$ticker] : null;
        if ($stock === null) { return '<td>–</td>'; }
        $exit = is_array($stock['exit'] ?? null) ? $stock['exit'] : [];
        $reasons = [];
        if (!empty($exit['supertrend_down'])) { $reasons[] = 'Supertrend ×3 vendt ned'; }
        if (!empty($exit['stockmap_sell'])) { $reasons[] = 'StockMap-salg denne uge'; }
        if (preg_match(self::DATE_RE, $buy_date) === 1 && is_array($exit['sma50_breaks'] ?? null)) {
            $latest = '';
            foreach ($exit['sma50_breaks'] as $date) {
                if (is_string($date) && $date >= $buy_date && $date > $latest) { $latest = $date; }
            }
            if ($latest !== '') { $reasons[] = 'brud under SMA50 (' . $latest . ')'; }
        }
        if ($reasons) {
            return '<td class="asc-pb-sell">SÆLG: ' . esc_html(implode(', ', $reasons)) . '</td>';
        }
        return '<td>behold</td>';
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
            'scores' => 'Aktie-scores',
            'papir' => 'Papirportefølje',
        ];
        $tab = sanitize_key(self::query_text('asc_tab'));
        if (!isset($tabs[$tab])) { $tab = 'mandag'; }
        $base = remove_query_arg(
            ['asc_tab', 'asc_q', 'asc_screen', 'asc_region', 'asc_sizing_status'],
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
        $watch = get_user_meta($user_id, self::WATCH_META, true);
        $wanted = [];
        foreach (is_array($watch) ? $watch : [] as $symbol) {
            if (is_string($symbol)) { $wanted[$symbol] = true; }
        }
        $owned = get_user_meta($user_id, self::PORTFOLIO_META, true);
        foreach (is_array($owned) ? $owned : [] as $lot) {
            if (is_array($lot) && is_string($lot['ticker'] ?? null)) { $wanted[$lot['ticker']] = true; }
        }
        foreach (is_array($data['research'] ?? null) ? $data['research'] : [] as $symbol) {
            if (is_string($symbol)) { $wanted[$symbol] = true; }
        }
        // Tragtens fund i hele universet (StockMap-køb + Quality ≥ 60) vises for alle.
        $from_universe = [];
        foreach (is_array($data['candidates'] ?? null) ? $data['candidates'] : [] as $symbol) {
            if (is_string($symbol)) { $wanted[$symbol] = true; $from_universe[$symbol] = true; }
        }
        $rows = [];
        foreach ($data['stocks'] as $ticker => $stock) {
            $ticker = (string)$ticker;
            if (isset($wanted[$ticker]) && is_array($stock)) { $rows[$ticker] = $stock; }
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
        echo '<p class="asc-subtle">Din overvågningsliste, din portefølje og research-listen. ★ = fundet ved scanning af '
            . 'hele universet (StockMap-køb og kvalitet ≥ 60), analyseret fuldt på samme måde.</p>';
        $changes = is_array($data['changes'] ?? null) ? $data['changes'] : [];
        if ($changes) {
            echo '<div class="asc-pb-changes"><strong>Ændringer siden sidst</strong><ul>';
            foreach ($changes as $change) {
                if (is_string($change)) { echo '<li>' . esc_html($change) . '</li>'; }
            }
            echo '</ul></div>';
        }

        if (!$rows) {
            echo '<p class="asc-empty">Ingen af dine overvågede aktier er med i seneste playbook. '
                . 'Følg aktier på din overvågningsliste, så sendes de med ved næste kørsel.</p>';
        } else {
            echo '<div class="asc-table-wrap"><table><thead><tr>';
            foreach (['Aktie', 'Handling', 'StockMap', 'TPI', 'MTI', 'Kvalitet', 'Moat', 'MSS-score',
                      'Værdi', 'Momentum', 'Kanal', 'PEG', 'Asymmetri', 'Regnskab', 'Størrelse', 'Nyheder',
                      'Begrundelse'] as $head) {
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
                echo '<tr><th scope="row">' . esc_html((string)$ticker)
                    . (isset($from_universe[$ticker]) ? ' <span class="asc-subtle" title="Fundet i hele universet">★</span>' : '')
                    . '</th>';
                echo '<td class="' . esc_attr($class) . '">' . self::s($action) . '</td>';
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
                echo '<td>' . self::s($stock['earnings'] ?? null) . '</td>';
                echo '<td>' . ($size === '' ? '' : $size) . '</td>';
                echo '<td>' . self::s($stock['news_summary'] ?? null) . '</td>';
                echo '<td class="asc-subtle">' . self::s($stock['reasons'] ?? null) . '</td></tr>';
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
        foreach (['Aktie', 'Region', 'Kvalitet', 'Værdi', 'Momentum', 'Moat', 'Upside %', 'PEG', 'Mkt.værdi (mia. USD)'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach (array_slice($hits, 0, self::MAX_UNIVERSE) as $ticker) {
            $row = $index[$ticker] ?? [];
            echo '<tr><th scope="row">' . esc_html((string)$ticker) . '</th>';
            echo '<td>' . self::s($row['region'] ?? null) . '</td>';
            foreach (['quality', 'value', 'momentum', 'moat'] as $metric) {
                echo '<td>' . esc_html(self::n($row[$metric . $suffix] ?? null)) . '</td>';
            }
            echo '<td>' . esc_html(self::n($row['upside'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['peg'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['mcap_usd_bn'] ?? null, 1)) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function tab_scores(array $data): void {
        $query = strtoupper(self::query_text('asc_q'));
        $query = preg_replace('/[^A-Z0-9.^=-]/', '', $query);
        $query = is_string($query) ? self::cut($query, 20) : '';
        $index = self::universe_index($data);
        $matches = [];
        foreach ($index as $ticker => $row) {
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
        echo '<button type="submit">Søg</button></form>';
        echo '<p class="asc-updated">Viser ' . esc_html((string)min($limit, count($matches))) . ' af '
            . esc_html((string)count($matches)) . ' aktier. Tal er percentiler (global / region).</p>';
        if (!$matches) {
            echo '<p class="asc-empty">Ingen aktier fundet.</p>';
            return;
        }
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        foreach (['Aktie', 'Region', 'Kvalitet', 'Værdi', 'Momentum', 'Moat', 'Upside %', 'PEG', 'Mkt.værdi (mia. USD)'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach (array_slice($matches, 0, $limit, true) as $ticker => $row) {
            echo '<tr><th scope="row">' . esc_html((string)$ticker) . '</th>';
            echo '<td>' . self::s($row['region'] ?? null) . '</td>';
            foreach (['quality', 'value', 'momentum', 'moat'] as $metric) {
                echo '<td>' . esc_html(self::n($row[$metric] ?? null) . ' / '
                    . self::n($row[$metric . '_r'] ?? null)) . '</td>';
            }
            echo '<td>' . esc_html(self::n($row['upside'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['peg'] ?? null, 1)) . '</td>';
            echo '<td>' . esc_html(self::n($row['mcap_usd_bn'] ?? null, 1)) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function tab_paper(array $data): void {
        $paper = is_array($data['paper'] ?? null) ? $data['paper'] : [];
        $summary = is_array($paper['summary'] ?? null) ? $paper['summary'] : [];
        $trades = is_array($paper['trades'] ?? null) ? $paper['trades'] : [];
        echo '<h3>Papirportefølje</h3>';
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
            echo '<tr><th scope="row">' . esc_html((string)($trade['ticker'] ?? '')) . '</th>';
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
