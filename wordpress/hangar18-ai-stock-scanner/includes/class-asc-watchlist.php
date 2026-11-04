<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/** A private list of ticker symbols to follow independently of purchases. */
final class ASC_Watchlist {
    private const META = 'asc_watchlist_v1';
    private const MAX = 50;

    public static function register(): void {
        add_shortcode('ai_stock_watchlist', [self::class, 'render']);
        add_action('admin_post_asc_watch_add', [self::class, 'add']);
        add_action('admin_post_asc_watch_remove', [self::class, 'remove']);
    }

    private static function symbols(): array {
        $raw = get_user_meta(get_current_user_id(), self::META, true);
        if (!is_array($raw)) { return []; }
        return array_values(array_filter($raw, static fn($s) =>
            is_string($s) && preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $s) === 1));
    }

    /** Følger den indloggede bruger aktien? (til aktiesidens knap) */
    public static function is_followed(string $ticker): bool {
        return in_array($ticker, self::symbols(), true);
    }

    private static function redirect(string $status): void {
        $referer = wp_get_referer();
        $url = is_string($referer) ? wp_validate_redirect($referer, home_url('/')) : home_url('/');
        // When a stock is followed from the catalogue, show the resulting
        // watchlist (and the notice) instead of leaving the user on a hidden tab.
        if (strpos($url, 'asc_view=stocks') !== false) {
            $url = remove_query_arg(['asc_catalog_page', 'asc_query', 'asc_sector'], $url);
            $url = add_query_arg('asc_view', 'watchlist', $url);
        }
        $url = add_query_arg('asc_watch_status', $status, remove_query_arg('asc_watch_status', $url));
        wp_safe_redirect($url . '#asc-watchlist');
        exit;
    }

    public static function add(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_watch_add');
        $raw = $_POST['asc_watch_ticker'] ?? '';
        $ticker = is_string($raw) ? strtoupper(trim(sanitize_text_field(wp_unslash($raw)))) : '';
        if (preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker) !== 1) {
            self::redirect('invalid');
        }
        $symbols = self::symbols();
        if (in_array($ticker, $symbols, true)) { self::redirect('exists'); }
        if (count($symbols) >= self::MAX) { self::redirect('limit'); }
        $symbols[] = $ticker;
        update_user_meta(get_current_user_id(), self::META, $symbols);
        self::redirect('added');
    }

    public static function remove(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_watch_remove');
        $raw = $_POST['asc_watch_ticker'] ?? '';
        $ticker = is_string($raw) ? strtoupper(trim(sanitize_text_field(wp_unslash($raw)))) : '';
        if (preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker) !== 1) {
            self::redirect('invalid');
        }
        $after = array_values(array_filter(self::symbols(), static fn($s) => $s !== $ticker));
        update_user_meta(get_current_user_id(), self::META, $after);
        self::redirect('removed');
    }

    public static function render(): string {
        if (!is_user_logged_in()) { return '<p>Log ind for at se din personlige overvågningsliste.</p>'; }
        wp_enqueue_style('hangar18-asc');
        $symbols = self::symbols();
        $messages = [
            'added' => 'Aktien er tilføjet din overvågningsliste.',
            'removed' => 'Aktien er fjernet fra listen.',
            'exists' => 'Aktien er allerede på listen.',
            'invalid' => 'Ugyldigt aktiesymbol.',
            'limit' => 'Du kan overvåge højst 50 aktier.',
        ];
        $status = isset($_GET['asc_watch_status']) && is_string($_GET['asc_watch_status'])
            ? sanitize_key(wp_unslash($_GET['asc_watch_status'])) : '';
        ob_start();
        echo '<section class="asc-portfolio asc-watchlist" id="asc-watchlist">';
        echo '<div class="asc-section-title"><h2>Min overvågningsliste</h2>'
            . '<p>Følg aktier uden at registrere et køb. Listen er privat.</p></div>';
        if (isset($messages[$status])) {
            echo '<p role="status" class="asc-notice">' . esc_html($messages[$status]) . '</p>';
        }
        echo '<form class="asc-watch-add" method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_watch_add">';
        wp_nonce_field('asc_watch_add');
        echo '<label>Aktiesymbol <input name="asc_watch_ticker" type="text" maxlength="20" '
            . 'placeholder="NOVO-B.CO, SAP.DE eller MSFT" required></label>';
        echo '<button type="submit">Følg aktie</button></form>';
        if ($symbols) {
            echo '<div class="asc-table-wrap"><table><thead><tr>'
                . '<th>Aktie</th><th>Seneste kurs</th><th>Valuta</th>'
                . '<th>Kursdato</th><th>Handling</th></tr></thead><tbody>';
            foreach ($symbols as $ticker) {
                $quote = ASC_Market_Quotes::get($ticker);
                $price = is_array($quote) && is_numeric($quote['price'] ?? null)
                    ? number_format((float)$quote['price'], 2, ',', '.') : '—';
                $currency = is_array($quote) ? (string)($quote['currency'] ?? '') : '';
                $date = is_array($quote) && isset($quote['market_time'])
                    ? wp_date('d-m-Y H:i', (int)$quote['market_time']) : 'Ikke tilgængelig';
                if (is_array($quote) && !empty($quote['stale'])) { $date .= ' (forældet)'; }
                echo '<tr><th scope="row">' . ASC_Stock_Page::link((string)$ticker) . '</th>'
                    . '<td>' . esc_html($price) . '</td><td>' . esc_html($currency) . '</td>'
                    . '<td>' . esc_html($date) . '</td><td>';
                echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
                echo '<input type="hidden" name="action" value="asc_watch_remove">';
                echo '<input type="hidden" name="asc_watch_ticker" value="' . esc_attr($ticker) . '">';
                wp_nonce_field('asc_watch_remove');
                echo '<button type="submit" class="asc-delete">Fjern</button></form></td></tr>';
                if (is_array($quote) && !empty($quote['history'])) {
                    echo '<tr class="asc-chart-row"><td colspan="5"><details><summary>Candlesticks og handelsvolumen – '
                        . esc_html($ticker) . '</summary>';
                    echo ASC_Market_Quotes::chart_markup($ticker, $quote);
                    echo '</details></td></tr>';
                }
            }
            echo '</tbody></table></div>';
        } else {
            echo '<p class="asc-empty">Ingen overvågede aktier endnu.</p>';
        }
        echo '<p class="asc-disclaimer">Automatiske kurser kræver en aktiveret og lovlig datakilde. '
            . 'Yahoo-kurser er eksperimentelle og kan være forsinkede. Din PC behøver ikke være tændt.</p>';
        echo ASC_Market_Quotes::auto_refresh_markup();
        echo '</section>';
        return (string)ob_get_clean();
    }
}
