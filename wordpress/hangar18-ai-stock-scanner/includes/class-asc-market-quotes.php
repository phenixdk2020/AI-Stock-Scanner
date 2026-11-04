<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Private portfolio quote adapter (experimental Yahoo Finance chart interface).
 *
 * Yahoo's chart endpoint is undocumented and Yahoo does not grant redistribution
 * rights by default. This integration is OFF until an administrator explicitly
 * enables it for restricted, non-commercial evaluation.
 * Do not publish portfolio quotes publicly or offer them as a data feed.
 */
final class ASC_Market_Quotes {
    private const OPTION = 'asc_yahoo_quotes_opt_in';
    private const AGE = 900;  // 15 minutes between external requests per ticker.
    private const CACHE_AGE = 840;  // Lidt under AGE, så hver 15-minutters kørsel altid finder cachen udløbet.
    private const RETRY_AFTER = 120;  // En mislykket hentning prøves først igen efter 2 minutter.
    private const REFRESH_BATCH = 5;  // Højst så mange kurser pr. kald fra siden (hver op til 3 sekunder).
    private const LAST_RUN = 'asc_quotes_last_run';
    private const MAX_RESPONSE = 262144;
    private const MAX_FETCH_PER_PAGE = 1;
    private const HISTORY_AGE = 21600;  // Lang historik (aktiesiden) caches i 6 timer.
    private const HISTORY_RETRY_AFTER = 300;  // Mislykket hentning af lang historik prøves først igen efter 5 minutter.
    private const HISTORY_MAX_RESPONSE = 1572864;  // Fem års daglige bars; større svar end ca. 1,5 MB afvises.
    private const HISTORY_MAX_BARS = 1400;  // Fem år er ca. 1.260 handelsdage.
    /** Perioder på aktiesiden: kalenderdage bagud fra seneste bar; null = al hentet historik, samlet til uger. */
    public const PERIOD_DAYS = ['1m' => 31, '6m' => 183, '1y' => 366, '5y' => null];
    public const PERIOD_LABELS = ['1m' => '1 måned', '6m' => '6 måneder', '1y' => '1 år', '5y' => '5 år'];
    private const INTRADAY_AGE = 600;  // Intradagsdata caches i 10 minutter.
    private const INTRADAY_RETRY_AFTER = 300;  // Mislykket hentning af intradagsdata prøves først igen efter 5 minutter.
    private const INTRADAY_MAX_RESPONSE = 524288;
    private const INTRADAY_MAX_BARS = 600;
    /** Intradagsgrafens perioder: Yahoo-range => interval (1 D = 5 minutter, 1 U = 15 minutter). */
    private const INTRADAY_RANGES = ['1d' => '5m', '5d' => '15m'];
    /** Markører på aktiegrafen: bogstav, forklaring og retning. */
    private const MARKER_KINDS = [
        'buy' => ['K', 'Køb (portefølje)', 'up'],
        'sim_buy' => ['V', 'Køb (simulator)', 'up'],
        'sim_sell' => ['S', 'Salg (simulator)', 'down'],
    ];
    private const CRON_HOOK = 'asc_quotes_refresh';
    private const CRON_SCHEDULE = 'asc_15min';
    private const CRON_MAX_TICKERS = 100;
    private static int $fetches_this_page = 0;
    private static bool $in_cron = false;
    private static bool $markup_done = false;

    public static function enabled(): bool {
        return get_option(self::OPTION, 'no') === 'yes';
    }

    public static function register(): void {
        add_action('admin_post_asc_quote_options', [self::class, 'save_options']);
        add_filter('cron_schedules', [self::class, 'cron_schedules']);
        add_action(self::CRON_HOOK, [self::class, 'refresh_followed']);
        add_action('init', [self::class, 'ensure_schedule']);
        add_action('rest_api_init', [self::class, 'register_routes']);
    }

    public static function register_routes(): void {
        register_rest_route('ai-stock-scanner/v1', '/quotes/refresh', [
            'methods'             => 'POST',
            'callback'            => [self::class, 'rest_refresh'],
            'permission_callback' => static fn() => is_user_logged_in(),
        ]);
        // Intradagsdata til grafens 1 D og 1 U. Kun for indloggede (cookie + X-WP-Nonce), kun læsning.
        register_rest_route('ai-stock-scanner/v1', '/quotes/intraday', [
            'methods'             => 'GET',
            'callback'            => [self::class, 'rest_intraday'],
            'permission_callback' => static fn() => is_user_logged_in(),
            'args'                => [
                'ticker' => ['required' => true, 'type' => 'string'],
                'range'  => ['required' => true, 'type' => 'string', 'enum' => ['1d', '5d']],
            ],
        ]);
    }

    /** @return WP_REST_Response|WP_Error */
    public static function rest_intraday(WP_REST_Request $request) {
        $ticker = $request->get_param('ticker');
        $range = $request->get_param('range');
        $ticker = is_string($ticker) ? strtoupper(trim($ticker)) : '';
        if (preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker) !== 1) {
            return new WP_Error('asc_bad_ticker', 'Ugyldigt aktiesymbol.', ['status' => 400]);
        }
        if (!is_string($range) || !isset(self::INTRADAY_RANGES[$range])) {
            return new WP_Error('asc_bad_range', 'Ugyldig periode.', ['status' => 400]);
        }
        $data = self::intraday($ticker, $range);
        if ($data === null) {
            return new WP_Error('asc_intraday_unavailable',
                'Intradagskurser kan ikke hentes lige nu.', ['status' => 503]);
        }
        $bars = [];
        foreach ($data['bars'] as $bar) {
            $bars[] = [(int)$bar['time'], (float)$bar['open'], (float)$bar['high'], (float)$bar['low'],
                (float)$bar['close'], (float)$bar['volume']];
        }
        $response = rest_ensure_response([
            'ticker' => $data['ticker'],
            'range' => $data['range'],
            'currency' => $data['currency'],
            'gmtoffset' => $data['gmtoffset'],
            'previous_close' => $data['previous_close'],
            'bars' => $bars,
        ]);
        $response->header('Cache-Control', 'private, no-store');
        return $response;
    }

    /** Skal kursen hentes nu? Ikke hvis cachen er frisk, eller et forsøg lige er mislykkedes. */
    private static function due(string $ticker): bool {
        $hash = md5($ticker);
        return !is_array(get_transient('asc_quote_' . $hash))
            && get_transient('asc_quote_attempt_' . $hash) === false;
    }

    /**
     * Siden kalder dette, så en visning henter alle forældede kurser i små portioner
     * uden at selve sidevisningen venter på Yahoo (MAX_FETCH_PER_PAGE).
     */
    public static function rest_refresh(): array {
        if (!self::enabled() || !class_exists('ASC_Playbook')) { return ['updated' => 0, 'remaining' => 0]; }
        $due = array_values(array_filter(ASC_Playbook::followed_tickers(), [self::class, 'due']));
        $batch = array_slice($due, 0, self::REFRESH_BATCH);
        $updated = 0;
        self::$in_cron = true;
        try {
            foreach ($batch as $ticker) {
                $quote = self::get($ticker);
                if (is_array($quote) && empty($quote['stale'])) { $updated++; }
            }
        } finally {
            self::$in_cron = false;
        }
        return ['updated' => $updated, 'remaining' => count($due) - count($batch)];
    }

    /** @param array<string, array<string, mixed>> $schedules */
    public static function cron_schedules($schedules): array {
        $schedules = is_array($schedules) ? $schedules : [];
        $schedules[self::CRON_SCHEDULE] = ['interval' => self::AGE, 'display' => 'Hvert 15. minut (AI Stock Scanner)'];
        return $schedules;
    }

    /** Kurser for alle fulgte/ejede aktier hentes i baggrunden hvert 15. minut, når kurskilden er slået til. */
    public static function ensure_schedule(): void {
        $scheduled = wp_next_scheduled(self::CRON_HOOK);
        if (self::enabled() && $scheduled === false) {
            wp_schedule_event(time() + 60, self::CRON_SCHEDULE, self::CRON_HOOK);
        } elseif (!self::enabled() && $scheduled !== false) {
            wp_clear_scheduled_hook(self::CRON_HOOK);
        }
    }

    public static function refresh_followed(): void {
        if (!self::enabled() || !class_exists('ASC_Playbook')) { return; }
        self::$in_cron = true;
        try {
            foreach (array_slice(ASC_Playbook::followed_tickers(), 0, self::CRON_MAX_TICKERS) as $ticker) {
                // Udløbet cache → ny kurs; endnu frisk → intet kald.
                self::get($ticker);
            }
        } finally {
            self::$in_cron = false;
        }
    }

    /**
     * Henter forældede kurser, når siden åbnes og hvert 15. minut, og genindlæser kun når der er nye kurser.
     * Er fanen skjult, sker det, når den vises igen. Genindlæser ikke midt i en formular.
     */
    public static function auto_refresh_markup(): string {
        if (!self::enabled() || !is_user_logged_in()) { return ''; }
        $last = (int)get_option(self::LAST_RUN, 0);
        $when = $last > 0 ? wp_date('H:i', $last) : false;
        $note = '<p class="asc-subtle">Kurserne opdateres automatisk hvert 15. minut (forsinket, uofficiel kilde).'
            . (is_string($when) ? ' Sidst hentet kl. ' . esc_html($when) . '.' : '') . '</p>';
        if (self::$markup_done) { return ''; }
        self::$markup_done = true;
        $url = wp_json_encode(rest_url('ai-stock-scanner/v1/quotes/refresh'), JSON_HEX_TAG | JSON_HEX_AMP);
        $nonce = wp_json_encode(wp_create_nonce('wp_rest'), JSON_HEX_TAG | JSON_HEX_AMP);
        return '<script>(function(){var u=' . $url . ',n=' . $nonce . ',w=' . (int)(self::AGE * 1000)
            . ',d=Date.now()+w,k=0;'
            . 'function b(){var a=document.activeElement;return !!(a&&/INPUT|SELECT|TEXTAREA/.test(a.tagName));}'
            . 'function e(c){if(c>0&&!b()){location.reload();}}'
            . 'function p(c,i){fetch(u,{method:"POST",credentials:"same-origin",headers:{"X-WP-Nonce":n}})'
            . '.then(function(r){return r.ok?r.json():null;}).then(function(j){'
            // Et afvist kald på en gammel fane skyldes ofte en udløbet nonce: en genindlæsning giver en ny.
            . 'if(!j){if(k>0&&!b()){location.reload();}return;}'
            . 'c+=j.updated;if(j.remaining>0&&i<20){p(c,i+1);}else{e(c);}})'
            . '.catch(function(){e(c);});}'
            . 'function t(){if(document.visibilityState==="visible"&&Date.now()>=d&&!b()){d=Date.now()+w;k++;p(0,0);}}'
            . 'p(0,0);setInterval(t,30000);document.addEventListener("visibilitychange",t);})();</script>'
            . $note;
    }

    public static function save_options(): void {
        if (!current_user_can('manage_options')) { wp_die('Ingen adgang.'); }
        check_admin_referer('asc_quote_options');
        $enabled = isset($_POST['asc_enable_yahoo'])
            && is_string($_POST['asc_enable_yahoo'])
            && $_POST['asc_enable_yahoo'] === 'yes';
        update_option(self::OPTION, $enabled ? 'yes' : 'no', false);
        wp_safe_redirect(admin_url('admin.php?page=asc-connection&asc_quotes=' . ($enabled ? 'on' : 'off')));
        exit;
    }

    public static function render_settings(): void {
        if (!current_user_can('manage_options')) { return; }
        echo '<hr><h2>Markedspriser – hjemmeside uden PC</h2>';
        echo '<p>Porteføljen kan gemmes og bruges uden kurskilde. Ved aktivering kan WordPress '
            . 'hente seneste kurser server-side. Af hensyn til webhotellets belastning forsøges '
            . 'højst én ny ekstern kursforespørgsel pr. sidevisning (maks. tre sekunder), '
            . 'og samme ticker genhentes højst hvert 15. minut. '
            . 'De øvrige kurser vises fra cache. Et baggrundsjob (WP-Cron) henter desuden kurser for alle '
            . 'aktier på brugernes overvågningslister og i porteføljerne hvert 15. minut. '
            . 'Din PC behøver ikke køre.</p>';
        echo '<p><strong>Bemærk:</strong> Yahoo chart endpoint er uofficielt og kan stoppe uden varsel. '
            . 'Yahoo begrænser videredistribution. Brug kun som eksperimentel, personlig og '
            . 'loginbeskyttet visning, og kontrollér vilkår for din anvendelse. '
            . 'Kurser er ikke garanteret realtid, og børsforsinkelser varierer.</p>';
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_quote_options">';
        wp_nonce_field('asc_quote_options');
        echo '<p><label><input type="checkbox" name="asc_enable_yahoo" value="yes" '
            . checked(self::enabled(), true, false)
            . '> Aktivér uofficielle Yahoo-kurser til privat test</label></p>';
        submit_button('Gem kursindstilling', 'secondary', 'submit', false);
        echo '</form>';
    }

    /** Returns a quote or null, never a synthetic/guessed market price. */
    public static function get(string $ticker): ?array {
        if (!self::enabled()) { return null; }
        if (!preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker)) { return null; }

        $key = 'asc_quote_' . md5($ticker);
        $cached = get_transient($key);
        if (is_array($cached) && !empty($cached['price'])) {
            return $cached;
        }
        // Throttle failures as well as successes to avoid hammering an unavailable service.
        $cooldown = 'asc_quote_attempt_' . md5($ticker);
        if (get_transient($cooldown) !== false) {
            return self::last_known($ticker);
        }
        if (!self::$in_cron && self::$fetches_this_page >= self::MAX_FETCH_PER_PAGE) {
            // Frontend must not time out while adding/viewing the third holding.
            // Return known data immediately instead of stacking slow HTTP calls.
            return self::last_known($ticker);
        }
        self::$fetches_this_page++;
        set_transient($cooldown, 1, self::RETRY_AFTER);
        $url = 'https://query1.finance.yahoo.com/v8/finance/chart/'
            . rawurlencode($ticker) . '?range=6mo&interval=1d';
        $response = wp_safe_remote_get($url, [
            'timeout' => 3,
            'redirection' => 0,
            'limit_response_size' => self::MAX_RESPONSE,
            'headers' => [
                'Accept' => 'application/json',
                'User-Agent' => 'Mozilla/5.0 (compatible; Hangar18-Stock-Scanner/0.3)',
            ],
        ]);
        if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
            return self::last_known($ticker);
        }
        $payload = json_decode((string)wp_remote_retrieve_body($response), true);
        if (!is_array($payload)) { return self::last_known($ticker); }
        $result = $payload['chart']['result'][0] ?? null;
        if (!is_array($result)) { return self::last_known($ticker); }
        $meta = $result['meta'] ?? null;
        if (!is_array($meta)) { return self::last_known($ticker); }

        // meta.regularMarketPrice is the current quoted (or most recent) price.
        $price = $meta['regularMarketPrice'] ?? null;
        $currency = strtoupper((string)($meta['currency'] ?? ''));
        $market_time = $meta['regularMarketTime'] ?? null;
        if (!is_numeric($price) || !is_finite((float)$price) || (float)$price <= 0
            || !preg_match('/^[A-Z]{3}$/D', $currency)
            || !is_numeric($market_time) || (int)$market_time < 1577836800
            || (int)$market_time > time() + 300) {
            return self::last_known($ticker);
        }
        $history = self::parse_history($result);
        $quote = [
            'ticker' => $ticker,
            'price' => (float)$price,
            'currency' => $currency,
            'market_time' => (int)$market_time,
            'received_at' => time(),
            'provider' => 'Yahoo Finance (uofficiel)',
            'history' => $history,
        ];
        $outstanding = $meta['sharesOutstanding'] ?? null;
        if (is_numeric($outstanding) && is_finite((float)$outstanding)
            && (float)$outstanding > 0) {
            $quote['shares_outstanding'] = (float)$outstanding;
        }
        set_transient($key, $quote, self::CACHE_AGE);
        update_option(self::LAST_RUN, time(), false);
        // Keep previous successful quote as fallback for up to 7 days; clearly label stale.
        update_option('asc_last_quote_' . md5($ticker), $quote, false);
        return $quote;
    }

    /**
     * Fem års daglige bars til aktiesiden (range=5y). Egen cache i 6 timer og egen cooldown ved fejl;
     * tæller ikke med i MAX_FETCH_PER_PAGE, men følger Yahoo-kilden: slået fra giver null.
     * Samme validering som get(). Returnerer aldrig gættede eller opfundne priser: null ved enhver fejl.
     * @return array{ticker: string, currency: string, bars: array, market_time: int, received_at: int, provider: string}|null
     */
    public static function history(string $ticker): ?array {
        if (!self::enabled()) { return null; }
        if (!preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker)) { return null; }

        $key = 'asc_hist5y_' . md5($ticker);
        $cached = get_transient($key);
        if (is_array($cached) && !empty($cached['bars'])) {
            return $cached;
        }
        $cooldown = 'asc_hist5y_attempt_' . md5($ticker);
        if (get_transient($cooldown) !== false) { return null; }
        set_transient($cooldown, 1, self::HISTORY_RETRY_AFTER);
        $url = 'https://query1.finance.yahoo.com/v8/finance/chart/'
            . rawurlencode($ticker) . '?range=5y&interval=1d';
        $response = wp_safe_remote_get($url, [
            'timeout' => 6,
            'redirection' => 0,
            'limit_response_size' => self::HISTORY_MAX_RESPONSE,
            'headers' => [
                'Accept' => 'application/json',
                'User-Agent' => 'Mozilla/5.0 (compatible; Hangar18-Stock-Scanner/0.3)',
            ],
        ]);
        if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
            return null;
        }
        // Et svar, der er klippet af grænsen, er ugyldig JSON og afvises her.
        $payload = json_decode((string)wp_remote_retrieve_body($response), true);
        if (!is_array($payload)) { return null; }
        $result = $payload['chart']['result'][0] ?? null;
        if (!is_array($result)) { return null; }
        $meta = $result['meta'] ?? null;
        if (!is_array($meta)) { return null; }

        $price = $meta['regularMarketPrice'] ?? null;
        $currency = strtoupper((string)($meta['currency'] ?? ''));
        $market_time = $meta['regularMarketTime'] ?? null;
        if (!is_numeric($price) || !is_finite((float)$price) || (float)$price <= 0
            || !preg_match('/^[A-Z]{3}$/D', $currency)
            || !is_numeric($market_time) || (int)$market_time < 1577836800
            || (int)$market_time > time() + 300) {
            return null;
        }
        $bars = self::parse_history($result, self::HISTORY_MAX_BARS, self::HISTORY_MAX_BARS);
        if (count($bars) < 20) { return null; }
        $history = [
            'ticker' => $ticker,
            'currency' => $currency,
            'bars' => $bars,
            'market_time' => (int)$market_time,
            'received_at' => time(),
            'provider' => 'Yahoo Finance (uofficiel)',
        ];
        set_transient($key, $history, self::HISTORY_AGE);
        return $history;
    }

    /**
     * Intradagsbars til grafens 1 D (5 minutter) og 1 U (15 minutter). Egen cache i 10 minutter og egen cooldown
     * ved fejl; tæller ikke med i MAX_FETCH_PER_PAGE (kaldes kun fra REST-ruten, aldrig ved sidevisning).
     * Samme validering som history(). Priser gættes aldrig: null ved enhver fejl.
     * @return array{ticker: string, range: string, currency: string, bars: array, gmtoffset: int, previous_close: ?float, market_time: int, received_at: int, provider: string}|null
     */
    public static function intraday(string $ticker, string $range): ?array {
        if (!self::enabled()) { return null; }
        if (!preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker)) { return null; }
        if (!isset(self::INTRADAY_RANGES[$range])) { return null; }

        $hash = md5($ticker . '|' . $range);
        $key = 'asc_intra_' . $hash;
        $cached = get_transient($key);
        if (is_array($cached) && !empty($cached['bars'])) {
            return $cached;
        }
        $cooldown = 'asc_intra_attempt_' . $hash;
        if (get_transient($cooldown) !== false) { return null; }
        set_transient($cooldown, 1, self::INTRADAY_RETRY_AFTER);
        $url = 'https://query1.finance.yahoo.com/v8/finance/chart/'
            . rawurlencode($ticker) . '?range=' . $range . '&interval=' . self::INTRADAY_RANGES[$range];
        $response = wp_safe_remote_get($url, [
            'timeout' => 6,
            'redirection' => 0,
            'limit_response_size' => self::INTRADAY_MAX_RESPONSE,
            'headers' => [
                'Accept' => 'application/json',
                'User-Agent' => 'Mozilla/5.0 (compatible; Hangar18-Stock-Scanner/0.3)',
            ],
        ]);
        if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
            return null;
        }
        $payload = json_decode((string)wp_remote_retrieve_body($response), true);
        if (!is_array($payload)) { return null; }
        $result = $payload['chart']['result'][0] ?? null;
        if (!is_array($result)) { return null; }
        $meta = $result['meta'] ?? null;
        if (!is_array($meta)) { return null; }

        $price = $meta['regularMarketPrice'] ?? null;
        $currency = strtoupper((string)($meta['currency'] ?? ''));
        $market_time = $meta['regularMarketTime'] ?? null;
        if (!is_numeric($price) || !is_finite((float)$price) || (float)$price <= 0
            || !preg_match('/^[A-Z]{3}$/D', $currency)
            || !is_numeric($market_time) || (int)$market_time < 1577836800
            || (int)$market_time > time() + 300) {
            return null;
        }
        $bars = self::parse_history($result, self::INTRADAY_MAX_BARS, self::INTRADAY_MAX_BARS);
        if (count($bars) < 2) { return null; }
        // Børsens tidsforskel til UTC (sekunder), så grafen kan vise børsens lokale klokkeslæt.
        $offset = $meta['gmtoffset'] ?? null;
        $offset = is_numeric($offset) && abs((float)$offset) <= 50400 ? (int)$offset : 0;
        $previous = $meta['chartPreviousClose'] ?? null;
        $previous = is_numeric($previous) && is_finite((float)$previous) && (float)$previous > 0 ? (float)$previous : null;
        $data = [
            'ticker' => $ticker,
            'range' => $range,
            'currency' => $currency,
            'bars' => $bars,
            'gmtoffset' => $offset,
            'previous_close' => $previous,
            'market_time' => (int)$market_time,
            'received_at' => time(),
            'provider' => 'Yahoo Finance (uofficiel)',
        ];
        set_transient($key, $data, self::INTRADAY_AGE);
        return $data;
    }

    /**
     * Sanitized OHLCV bars in ascending order; excludes nonexistent sessions.
     * The number of bars is bounded to minimize WP database and UI size.
     * Standarden (160 læst, 130 gemt) er kursopslagets; history() bruger større grænser.
     */
    private static function parse_history(array $result, int $limit = 160, int $keep = 130): array {
        $times = $result['timestamp'] ?? [];
        $ohlcv = $result['indicators']['quote'][0] ?? null;
        if (!is_array($times) || !is_array($ohlcv)) { return []; }
        $opens = $ohlcv['open'] ?? [];
        $highs = $ohlcv['high'] ?? [];
        $lows = $ohlcv['low'] ?? [];
        $closes = $ohlcv['close'] ?? [];
        $volumes = $ohlcv['volume'] ?? [];
        if (!is_array($opens) || !is_array($highs)
            || !is_array($lows) || !is_array($closes) || !is_array($volumes)) {
            return [];
        }
        $bars = [];
        $count = min(count($times), $limit);
        for ($i = 0; $i < $count; $i++) {
            $t = $times[$i] ?? null;
            $o = $opens[$i] ?? null;
            $h = $highs[$i] ?? null;
            $l = $lows[$i] ?? null;
            $c = $closes[$i] ?? null;
            $v = is_numeric($volumes[$i] ?? null) ? $volumes[$i] : 0;  // Indeks og valuta har ingen volumen.
            if (!is_numeric($t) || !is_numeric($o) || !is_numeric($h)
                || !is_numeric($l) || !is_numeric($c)) {
                continue;
            }
            $t = (int)$t;
            $o = (float)$o; $h = (float)$h; $l = (float)$l; $c = (float)$c;
            $v = (float)$v;
            if ($t < 1577836800 || $t > time() + 300
                || !is_finite($o) || !is_finite($h)
                || !is_finite($l) || !is_finite($c) || !is_finite($v)
                || min($o, $h, $l, $c) <= 0 || $v < 0
                || $h < max($o, $c) || $l > min($o, $c)) {
                continue;
            }
            $bars[] = [
                'time' => $t, 'open' => $o, 'high' => $h, 'low' => $l,
                'close' => $c, 'volume' => $v,
            ];
        }
        usort($bars, static fn(array $a, array $b): int => $a['time'] <=> $b['time']);
        return array_slice($bars, -$keep);
    }

    private static function number(float $n, int $decimals = 0): string {
        return esc_html(number_format($n, $decimals, ',', '.'));
    }

    private static function daily_stats(array $bars, int $count): ?array {
        $slice = array_slice($bars, -$count);
        $days = count($slice);
        if ($days === 0) { return null; }
        $shares = 0.0;
        $turnover = 0.0;
        foreach ($slice as $bar) {
            $shares += (float)$bar['volume'];
            // Estimate: close × daily volume; not actual transaction-level turnover.
            $turnover += (float)$bar['close'] * (float)$bar['volume'];
        }
        return [
            'days' => $days,
            'shares_per_day' => $shares / $days,
            'value_per_day' => $turnover / $days,
        ];
    }

    /** Escaped inline SVG candlesticks, no CDN, scripts or external JS. */
    public static function chart_markup(string $ticker, array $quote): string {
        $bars = is_array($quote['history'] ?? null) ? $quote['history'] : [];
        $currency = (string)($quote['currency'] ?? '');
        $week = self::daily_stats($bars, 5);
        $month = self::daily_stats($bars, 21);
        if (count($bars) < 2) {
            return '<p>Ingen valide historiske OHLCV-data til dette diagram.</p>';
        }
        $candles = array_slice($bars, -55);
        $min = min(array_column($candles, 'low'));
        $max = max(array_column($candles, 'high'));
        if ($max <= $min) { $max = $min + max(0.01, $min * 0.005); }
        $width = 960; $height = 345;
        $left = 65; $right = 20; $top = 23; $candleBottom = 255;
        $innerHeight = $candleBottom - $top;
        $usable = $width - $left - $right;
        $step = $usable / count($candles);
        $bodyWidth = max(2, min(12, $step * .64));
        $range = $max - $min;
        $volumeMax = max(array_column($candles, 'volume'));
        $result = '<div class="asc-chart-container"><svg xmlns="http://www.w3.org/2000/svg" '
            . 'viewBox="0 0 ' . $width . ' ' . $height . '" role="img" '
            . 'aria-label="Daglige candlesticks og volumen for ' . esc_attr($ticker) . '">'
            . '<title>OHLC og handelsvolumen: ' . esc_html($ticker) . '</title>'
            . '<rect width="960" height="345" fill="#fff" rx="12"/>';
        foreach ([0, .25, .5, .75, 1] as $fraction) {
            $y = $top + $innerHeight * $fraction;
            $level = $max - $range * $fraction;
            $result .= '<line x1="' . $left . '" x2="' . ($width - $right)
                . '" y1="' . round($y, 2) . '" y2="' . round($y, 2)
                . '" stroke="#e5eaf0" stroke-width="1"/>';
            $result .= '<text x="5" y="' . round($y + 4, 2)
                . '" fill="#354355" font-size="12">'
                . self::number($level, $level < 10 ? 2 : 1) . '</text>';
        }
        $last = count($candles) - 1;
        foreach ($candles as $i => $bar) {
            $x = $left + $step * ($i + .5);
            $yHigh = $top + ($max - $bar['high']) / $range * $innerHeight;
            $yLow = $top + ($max - $bar['low']) / $range * $innerHeight;
            $yOpen = $top + ($max - $bar['open']) / $range * $innerHeight;
            $yClose = $top + ($max - $bar['close']) / $range * $innerHeight;
            $up = $bar['close'] >= $bar['open'];
            $color = $up ? '#167b59' : '#c8394c';
            $bodyY = min($yOpen, $yClose);
            $bodyHeight = max(1.5, abs($yClose - $yOpen));
            $volHeight = $volumeMax > 0 ? min(57, $bar['volume'] / $volumeMax * 57) : 0;
            $result .= '<line x1="' . round($x, 2) . '" x2="' . round($x, 2)
                . '" y1="' . round($yHigh, 2) . '" y2="' . round($yLow, 2)
                . '" stroke="' . $color . '" stroke-width="1.4"/>';
            $result .= '<rect x="' . round($x - $bodyWidth / 2, 2)
                . '" y="' . round($bodyY, 2) . '" width="' . round($bodyWidth, 2)
                . '" height="' . round($bodyHeight, 2)
                . '" fill="' . $color . '" rx="1"/>';
            $result .= '<rect x="' . round($x - $bodyWidth / 2, 2)
                . '" y="' . round(328 - $volHeight, 2) . '" width="'
                . round($bodyWidth, 2) . '" height="' . round($volHeight, 2)
                . '" fill="' . $color . '" opacity=".5"/>';
            if ($i === 0 || $i === $last || $i === (int)floor($last / 2)) {
                $result .= '<text x="' . round($x, 2)
                    . '" y="342" text-anchor="middle" font-size="11" fill="#475569">'
                    . esc_html(wp_date('d/m', (int)$bar['time'])) . '</text>';
            }
        }
        $result .= '<text x="7" y="302" font-size="12" fill="#475569">Vol.</text>'
            . '</svg></div><div class="asc-trading-stats">';
        foreach ([['Uge (5 børsdage)', $week], ['Måned (21 børsdage)', $month]] as $period) {
            [$label, $stats] = $period;
            if ($stats === null) { continue; }
            $result .= '<div><strong>' . esc_html($label) . '</strong>'
                . '<span>Gns. antal handlede aktier/dag: '
                . self::number((float)$stats['shares_per_day']) . '</span>'
                . '<span>Estimeret handlet beløb/dag: '
                . self::number((float)$stats['value_per_day']) . ' '
                . esc_html($currency) . '</span>'
                . '<small>Beregnet ud fra ' . esc_html((string)$stats['days'])
                . ' handelsdage.</small></div>';
        }
        $result .= '</div>';
        // Sector-first scanners often flag abnormal trading volume. Here we use
        // only observable OHLCV volume, without pretending to know fund flows.
        if ($week !== null && $month !== null && $month['shares_per_day'] > 0
            && $week['days'] >= 5 && $month['days'] >= 21) {
            $ratio = $week['shares_per_day'] / $month['shares_per_day'];
            if ($ratio >= 1.5) {
                $result .= '<p class="asc-warning">Volumenadvarsel: seneste 5 '
                    . 'handelsdage har i gennemsnit '
                    . self::number($ratio, 2)
                    . ' × 21-dages gennemsnittet. Dette er ikke et købssignal.</p>';
            }
        }
        $outstanding = $quote['shares_outstanding'] ?? null;
        $result .= '<p class="asc-disclaimer">Udestående aktier: '
            . (is_numeric($outstanding) && (float)$outstanding > 0
                ? self::number((float)$outstanding) : 'ikke tilgængeligt')
            . '. Selskabets bogførte egenkapital (net worth): ikke tilgængelig fra OHLCV-data. '
            . 'Estimeret handelsværdi er lukkekurs × volumen, ikke faktisk handelsomsætning. '
            . 'Seneste tilgængelige dagskurser kan være forsinkede. Uofficiel Yahoo-integration '
            . 'med brugs- og licensforbehold.</p>';
        return $result;
    }

    // ------------------------------------------------------------ Aktiesidens graf

    /**
     * Glidende gennemsnit (SMA50, SMA200) af lukkekurser, beregnet på al hentet historik, så de også findes
     * i starten af en periode. null hvor der er for få bars forud.
     */
    private static function with_sma(array $bars): array {
        $bars = array_values($bars);
        $sums = [50 => 0.0, 200 => 0.0];
        $out = [];
        foreach ($bars as $i => $bar) {
            foreach ([50, 200] as $n) {
                $sums[$n] += (float)$bar['close'];
                if ($i >= $n) { $sums[$n] -= (float)$bars[$i - $n]['close']; }
                $bar['sma' . $n] = $i >= $n - 1 ? $sums[$n] / $n : null;
            }
            $out[] = $bar;
        }
        return $out;
    }

    /** Daglige bars samlet til uger (ISO-uge): første åbning, højeste høj, laveste lav, sidste lukning, sum af volumen. */
    private static function weekly(array $bars): array {
        $weeks = [];
        foreach ($bars as $bar) {
            $key = gmdate('o-W', (int)$bar['time']);
            if (!isset($weeks[$key])) {
                $weeks[$key] = $bar;
                continue;
            }
            $week = $weeks[$key];
            $week['high'] = max((float)$week['high'], (float)$bar['high']);
            $week['low'] = min((float)$week['low'], (float)$bar['low']);
            $week['close'] = (float)$bar['close'];
            $week['volume'] = (float)$week['volume'] + (float)$bar['volume'];
            $week['sma50'] = $bar['sma50'];
            $week['sma200'] = $bar['sma200'];
            $week['end'] = (int)$bar['end'];
            $weeks[$key] = $week;
        }
        return array_values($weeks);
    }

    /**
     * Placerer markører (købs- og salgsdatoer) på barer i den viste periode. Datoer uden for perioden springes over;
     * en dato uden handel (weekend) hører til barren før.
     * @return array<int, array{index: int, kind: string, date: string}>
     */
    private static function place_markers(array $view, array $markers): array {
        $starts = [];
        foreach ($view as $i => $bar) {
            $starts[$i] = gmdate('Y-m-d', (int)$bar['time']);
        }
        $first = $starts[0];
        $last_end = gmdate('Y-m-d', (int)$view[count($view) - 1]['end']);
        $placed = [];
        foreach ($markers as $marker) {
            $date = is_array($marker) && is_string($marker['date'] ?? null) ? $marker['date'] : '';
            $kind = is_array($marker) && is_string($marker['kind'] ?? null) ? $marker['kind'] : '';
            if (!isset(self::MARKER_KINDS[$kind]) || preg_match('/^\d{4}-\d\d-\d\d$/D', $date) !== 1) { continue; }
            if ($date < $first || $date > $last_end) { continue; }
            $index = 0;
            foreach ($starts as $i => $start) {
                if ($start <= $date) { $index = $i; } else { break; }
            }
            $placed[] = ['index' => $index, 'kind' => $kind, 'date' => $date];
        }
        return $placed;
    }

    /**
     * Aktiesidens graf som serverrenderet, escaped SVG uden eksterne biblioteker: candles og volumen for perioden
     * (1m, 6m og 1y daglige, 5y samlet til uger), SMA50 og SMA200 med forklaring og markører for køb og salg.
     * $markers: [['date' => 'Y-m-d', 'kind' => 'buy'|'sim_buy'|'sim_sell'], ...].
     */
    public static function stock_chart(string $ticker, array $bars, string $currency, string $period, array $markers = []): string {
        $none = '<p>Ingen valide historiske OHLCV-data til dette diagram.</p>';
        $days = array_key_exists($period, self::PERIOD_DAYS) ? self::PERIOD_DAYS[$period] : self::PERIOD_DAYS['6m'];
        $all = self::with_sma($bars);
        if (count($all) < 2) { return $none; }
        $last_time = (int)$all[count($all) - 1]['time'];
        $view = [];
        foreach ($all as $bar) {
            if ($days === null || (int)$bar['time'] >= $last_time - $days * 86400) {
                $bar['end'] = (int)$bar['time'];
                $view[] = $bar;
            }
        }
        $weekly = $days === null;
        if ($weekly) { $view = self::weekly($view); }
        $count = count($view);
        if ($count < 2) { return $none; }

        $min = (float)min(array_column($view, 'low'));
        $max = (float)max(array_column($view, 'high'));
        $has = ['sma50' => false, 'sma200' => false];
        foreach ($view as $bar) {
            foreach (['sma50', 'sma200'] as $key) {
                if ($bar[$key] !== null) {
                    $has[$key] = true;
                    $min = min($min, (float)$bar[$key]);
                    $max = max($max, (float)$bar[$key]);
                }
            }
        }
        $pad = max(($max - $min) * 0.03, $max * 0.002);
        $min = max(0.0, $min - $pad);
        $max = $max + $pad;
        $range = $max - $min;

        $width = 720; $height = 398;
        $left = 58; $right = 10; $top = 14; $price_bottom = 292;
        $inner = $price_bottom - $top;
        $vol_bottom = 368; $vol_height = 58;
        $step = ($width - $left - $right) / $count;
        $body = max(1.0, min(10.0, $step * .64));
        $wick = $count > 150 ? 1 : 1.4;
        $volume_max = (float)max(array_column($view, 'volume'));
        $y_of = static fn(float $value): float => $top + ($max - $value) / $range * $inner;

        $svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' . $width . ' ' . $height . '" role="img" '
            . 'aria-label="Candlestick-graf med volumen og glidende gennemsnit for ' . esc_attr($ticker) . '">'
            . '<title>Kursgraf med volumen: ' . esc_html($ticker) . '</title>'
            . '<rect width="' . $width . '" height="' . $height . '" fill="#fff"/>';
        foreach ([0, .25, .5, .75, 1] as $fraction) {
            $y = $top + $inner * $fraction;
            $level = $max - $range * $fraction;
            $svg .= '<line x1="' . $left . '" x2="' . ($width - $right) . '" y1="' . round($y, 1) . '" y2="' . round($y, 1)
                . '" stroke="#e5eaf0" stroke-width="1"/>'
                . '<text x="4" y="' . round($y + 4, 1) . '" fill="#334155" font-size="13">'
                . self::number($level, $level < 10 ? 2 : ($level < 1000 ? 1 : 0)) . '</text>';
        }
        foreach ($view as $i => $bar) {
            $x = $left + $step * ($i + .5);
            $up = (float)$bar['close'] >= (float)$bar['open'];
            $color = $up ? '#167b59' : '#c8394c';
            $y_open = $y_of((float)$bar['open']);
            $y_close = $y_of((float)$bar['close']);
            $vol = $volume_max > 0 ? (float)$bar['volume'] / $volume_max * $vol_height : 0.0;
            $svg .= '<line x1="' . round($x, 1) . '" x2="' . round($x, 1) . '" y1="' . round($y_of((float)$bar['high']), 1)
                . '" y2="' . round($y_of((float)$bar['low']), 1) . '" stroke="' . $color . '" stroke-width="' . $wick . '"/>'
                . '<rect x="' . round($x - $body / 2, 1) . '" y="' . round(min($y_open, $y_close), 1)
                . '" width="' . round($body, 1) . '" height="' . round(max(1.2, abs($y_close - $y_open)), 1)
                . '" fill="' . $color . '"/>'
                . '<rect x="' . round($x - $body / 2, 1) . '" y="' . round($vol_bottom - $vol, 1)
                . '" width="' . round($body, 1) . '" height="' . round($vol, 1) . '" fill="' . $color . '" opacity=".5"/>';
        }
        $svg .= '<text x="4" y="' . ($vol_bottom - 20) . '" font-size="13" fill="#334155">Vol.</text>';

        // Datoer på aksen: begyndelsen, tre punkter undervejs og slutningen.
        $date_format = ($days === null || $days >= 366) ? 'M y' : 'd/m';
        $label_at = array_unique([0, (int)floor(($count - 1) * .25), (int)floor(($count - 1) * .5),
            (int)floor(($count - 1) * .75), $count - 1]);
        foreach ($label_at as $i) {
            $anchor = $i === 0 ? 'start' : ($i === $count - 1 ? 'end' : 'middle');
            $x = $i === 0 ? $left : ($i === $count - 1 ? $width - $right : $left + $step * ($i + .5));
            $svg .= '<text x="' . round($x, 1) . '" y="' . ($height - 8) . '" text-anchor="' . $anchor
                . '" font-size="13" fill="#334155">' . esc_html((string)wp_date($date_format, (int)$view[$i]['time'])) . '</text>';
        }

        foreach (['sma50' => '#d97706', 'sma200' => '#7c3aed'] as $key => $color) {
            $points = [];
            foreach ($view as $i => $bar) {
                if ($bar[$key] !== null) {
                    $points[] = round($left + $step * ($i + .5), 1) . ',' . round($y_of((float)$bar[$key]), 1);
                }
            }
            if (count($points) >= 2) {
                $svg .= '<polyline class="asc-sma-line" data-line="' . $key . '" fill="none" stroke="' . $color
                    . '" stroke-width="1.8" stroke-linejoin="round" points="' . implode(' ', $points) . '"/>';
            }
        }

        $used = [];
        $slots = [];
        $drawn = [];
        foreach (self::place_markers($view, $markers) as $mark) {
            $once = $mark['index'] . '|' . $mark['kind'];
            if (isset($drawn[$once])) { continue; }
            $drawn[$once] = true;
            $used[$mark['kind']] = true;
            [$letter, $label, $direction] = self::MARKER_KINDS[$mark['kind']];
            $slot = $slots[$mark['index']] ?? 0;
            $slots[$mark['index']] = $slot + 1;
            $x = $left + $step * ($mark['index'] + .5);
            $y = $top + 2 + $slot * 16;
            $triangle = $direction === 'up'
                ? round($x - 6, 1) . ',' . round($y + 12, 1) . ' ' . round($x + 6, 1) . ',' . round($y + 12, 1) . ' ' . round($x, 1) . ',' . round($y, 1)
                : round($x - 6, 1) . ',' . round($y, 1) . ' ' . round($x + 6, 1) . ',' . round($y, 1) . ' ' . round($x, 1) . ',' . round($y + 12, 1);
            $near_right = $x > $width - 40;
            $date = substr($mark['date'], 8, 2) . '-' . substr($mark['date'], 5, 2) . '-' . substr($mark['date'], 0, 4);
            $svg .= '<g class="asc-marker" data-kind="' . esc_attr($mark['kind']) . '"><title>' . esc_html($label . ' ' . $date) . '</title>'
                . '<line x1="' . round($x, 1) . '" x2="' . round($x, 1) . '" y1="' . $top . '" y2="' . $price_bottom
                . '" stroke="#0369a1" stroke-width="1" stroke-dasharray="3 3" opacity=".7"/>'
                . '<polygon points="' . $triangle . '" fill="#0369a1"/>'
                . '<text x="' . round($near_right ? $x - 9 : $x + 9, 1) . '" y="' . round($y + 11, 1)
                . '" text-anchor="' . ($near_right ? 'end' : 'start') . '" font-size="13" font-weight="700" fill="#0369a1">'
                . esc_html($letter) . '</text></g>';
        }
        $svg .= '</svg>';

        $first = $view[0];
        $latest = $view[$count - 1];
        $change = (float)$first['close'] > 0 ? ((float)$latest['close'] / (float)$first['close'] - 1) * 100 : null;
        $unit = $weekly ? 'uge' : 'handelsdag';
        $html = '<div class="asc-stock-chart"><div class="asc-stock-chart-scroll">' . $svg . '</div>'
            . '<ul class="asc-chart-legend">'
            . '<li><i class="asc-leg asc-leg-up"></i>Stigende ' . esc_html($unit) . '</li>'
            . '<li><i class="asc-leg asc-leg-down"></i>Faldende ' . esc_html($unit) . '</li>'
            . '<li><i class="asc-leg asc-leg-sma50"></i>SMA50 (50 dages gennemsnit)'
            . ($has['sma50'] ? '' : ' – for lidt historik') . '</li>'
            . '<li><i class="asc-leg asc-leg-sma200"></i>SMA200 (200 dages gennemsnit)'
            . ($has['sma200'] ? '' : ' – for lidt historik') . '</li>';
        foreach (self::MARKER_KINDS as $kind => $info) {
            if (isset($used[$kind])) {
                $html .= '<li><i class="asc-leg asc-leg-mark">' . esc_html($info[0]) . '</i>' . esc_html($info[1]) . '</li>';
            }
        }
        $html .= '</ul><p class="asc-subtle">'
            . esc_html((string)wp_date('d-m-Y', (int)$first['time'])) . ' – ' . esc_html((string)wp_date('d-m-Y', (int)$latest['end']))
            . '. Hver kerte er en ' . esc_html($unit) . '. Højeste ' . self::number((float)max(array_column($view, 'high')), 2)
            . ' og laveste ' . self::number((float)min(array_column($view, 'low')), 2) . ' ' . esc_html($currency)
            . ($change === null ? '' : '. Ændring i perioden ' . esc_html(($change > 0 ? '+' : '') . number_format($change, 1, ',', '.')) . ' %')
            . '.</p></div>';

        $stats = '';
        foreach ([['Uge (5 børsdage)', self::daily_stats($all, 5)], ['Måned (21 børsdage)', self::daily_stats($all, 21)]] as $item) {
            [$label, $values] = $item;
            if ($values === null) { continue; }
            $stats .= '<div><strong>' . esc_html($label) . '</strong>'
                . '<span>Gns. antal handlede aktier/dag: ' . self::number((float)$values['shares_per_day']) . '</span>'
                . '<span>Estimeret handlet beløb/dag: ' . self::number((float)$values['value_per_day']) . ' ' . esc_html($currency) . '</span>'
                . '<small>Beregnet ud fra ' . esc_html((string)$values['days']) . ' handelsdage.</small></div>';
        }
        if ($stats !== '') { $html .= '<div class="asc-trading-stats">' . $stats . '</div>'; }
        return $html;
    }

    private static function last_known(string $ticker): ?array {
        $last = get_option('asc_last_quote_' . md5($ticker), null);
        if (!is_array($last) || ($last['ticker'] ?? '') !== $ticker
            || !is_numeric($last['price'] ?? null)
            || (int)($last['received_at'] ?? 0) < time() - 604800) {
            return null;
        }
        $last['stale'] = true;
        return $last;
    }
}
