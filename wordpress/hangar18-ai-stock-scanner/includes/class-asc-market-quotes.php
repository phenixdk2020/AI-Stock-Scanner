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
            . rawurlencode($ticker) . '?range=5d&interval=1d';
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
        $quote = [
            'ticker' => $ticker,
            'price' => (float)$price,
            'currency' => $currency,
            'market_time' => (int)$market_time,
            'received_at' => time(),
            'provider' => 'Yahoo Finance (uofficiel)',
        ];
        set_transient($key, $quote, self::AGE);
        // Keep previous successful quote as fallback for up to 7 days; clearly label stale.
        update_option('asc_last_quote_' . md5($ticker), $quote, false);
        return $quote;
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
