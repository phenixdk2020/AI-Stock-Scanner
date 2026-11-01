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
    private const MAX_RESPONSE = 262144;
    private const MAX_FETCH_PER_PAGE = 4;
    private static int $fetches_this_page = 0;

    public static function enabled(): bool {
        return get_option(self::OPTION, 'no') === 'yes';
    }

    public static function register(): void {
        add_action('admin_post_asc_quote_options', [self::class, 'save_options']);
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
        echo '<p>Porteføljen kan gemmes og bruges uden kurskilde. Ved aktivering prøver WordPress '
            . 'at hente seneste kurs server-side fra Yahoo Finance hvert 15. minut pr. aktie, '
            . 'når en logget ind bruger åbner siden. Din PC behøver ikke køre.</p>';
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
        if (self::$fetches_this_page >= self::MAX_FETCH_PER_PAGE) {
            return self::last_known($ticker);
        }
        self::$fetches_this_page++;
        set_transient($cooldown, 1, self::AGE);
        $url = 'https://query1.finance.yahoo.com/v8/finance/chart/'
            . rawurlencode($ticker) . '?range=6mo&interval=1d';
        $response = wp_safe_remote_get($url, [
            'timeout' => 4,
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
        set_transient($key, $quote, self::AGE);
        // Keep previous successful quote as fallback for up to 7 days; clearly label stale.
        update_option('asc_last_quote_' . md5($ticker), $quote, false);
        return $quote;
    }

    /**
     * Sanitized OHLCV bars in ascending order; excludes nonexistent sessions.
     * The number of bars is bounded to minimize WP database and UI size.
     */
    private static function parse_history(array $result): array {
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
        $count = min(count($times), 160);
        for ($i = 0; $i < $count; $i++) {
            $t = $times[$i] ?? null;
            $o = $opens[$i] ?? null;
            $h = $highs[$i] ?? null;
            $l = $lows[$i] ?? null;
            $c = $closes[$i] ?? null;
            $v = $volumes[$i] ?? null;
            if (!is_numeric($t) || !is_numeric($o) || !is_numeric($h)
                || !is_numeric($l) || !is_numeric($c) || !is_numeric($v)) {
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
        return array_slice($bars, -130);
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
