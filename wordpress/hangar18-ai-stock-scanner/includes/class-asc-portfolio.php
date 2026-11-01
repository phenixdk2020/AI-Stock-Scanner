<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/** Login-protected, per-user portfolio with multiple acquisition lots. */
final class ASC_Portfolio {
    private const USER_META = 'asc_portfolio_positions_v1';
    private const MAX_POSITIONS = 100;

    public static function register(): void {
        add_shortcode('ai_stock_portfolio', [self::class, 'render']);
        add_action('template_redirect', [self::class, 'private_page_no_cache'], 0);
        add_shortcode('ai_stock_home', [self::class, 'render_home']);
        add_action('admin_post_asc_portfolio_add', [self::class, 'add']);
        add_action('admin_post_asc_portfolio_delete', [self::class, 'delete']);
        add_action('admin_post_asc_portfolio_price', [self::class, 'set_manual_price']);
        add_action('admin_post_asc_portfolio_export', [self::class, 'export_csv']);
        add_action('admin_post_asc_portfolio_edit', [self::class, 'edit']);
        add_action('admin_post_asc_create_home', [self::class, 'create_home']);
    }

    /** Prevent shared page caches from showing stale/private holdings after a save. */
    public static function private_page_no_cache(): void {
        if (!is_user_logged_in()) { return; }
        $home_id = (int)get_option('asc_home_page_id', 0);
        if (is_front_page() || ($home_id > 0 && is_page($home_id))
            || (is_singular() && (
                has_shortcode((string)get_post_field('post_content', get_queried_object_id()), 'ai_stock_portfolio')
                || has_shortcode((string)get_post_field('post_content', get_queried_object_id()), 'ai_stock_home')
            ))) {
            if (!defined('DONOTCACHEPAGE')) { define('DONOTCACHEPAGE', true); }
            nocache_headers();
        }
    }

    private static function positions(int $user_id): array {
        $data = get_user_meta($user_id, self::USER_META, true);
        return is_array($data) ? array_values(array_filter($data, 'is_array')) : [];
    }

    private static function field(string $key): string {
        $value = $_POST[$key] ?? '';
        return is_string($value) ? trim(sanitize_text_field(wp_unslash($value))) : '';
    }

    private static function decimal(string $raw): ?float {
        $value = trim(str_replace(["\xc2\xa0", ' '], '', $raw));
        if (str_contains($value, ',') && str_contains($value, '.')) {
            if (strrpos($value, ',') > strrpos($value, '.')) {
                $value = str_replace(['.', ','], ['', '.'], $value); // Danish 1.234,56
            } else {
                $value = str_replace(',', '', $value); // English 1,234.56
            }
        } else {
            $value = str_replace(',', '.', $value);
        }
        if (!preg_match('/^[0-9]+(?:\.[0-9]+)?$/D', $value)) { return null; }
        $n = (float)$value;
        return is_finite($n) && $n > 0 && $n <= 1000000000 ? $n : null;
    }

    private static function valid_date(string $date): bool {
        $d = DateTimeImmutable::createFromFormat('!Y-m-d', $date);
        return $d instanceof DateTimeImmutable && $d->format('Y-m-d') === $date
            && $date <= wp_date('Y-m-d');
    }

    private static function redirect(string $status): void {
        $referer = wp_get_referer();
        $url = is_string($referer) && $referer !== ''
            ? wp_validate_redirect($referer, home_url('/'))
            : home_url('/');
        $url = remove_query_arg('asc_portfolio_status', $url);
        wp_safe_redirect(add_query_arg('asc_portfolio_status', $status, $url) . '#asc-portfolio');
        exit;
    }

    public static function add(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_portfolio_add');
        $ticker = strtoupper(self::field('asc_ticker'));
        $name = self::field('asc_label');
        if (function_exists('mb_substr')) { $name = mb_substr($name, 0, 80); }
        else { $name = substr($name, 0, 80); }
        $currency = strtoupper(self::field('asc_currency'));
        $quantity = self::decimal(self::field('asc_quantity'));
        $buy_price = self::decimal(self::field('asc_buy_price'));
        $initial_raw = self::field('asc_initial_price');
        $initial_price = $initial_raw !== '' ? self::decimal($initial_raw) : null;
        $buy_date = self::field('asc_buy_date');

        // Distinct errors make a rejected third purchase diagnosable after redirect.
        if (preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker) !== 1) {
            self::redirect('invalid_ticker');
        }
        if (preg_match('/^(DKK|SEK|NOK|EUR|USD)$/D', $currency) !== 1) {
            self::redirect('invalid_currency');
        }
        if ($quantity === null) { self::redirect('invalid_quantity'); }
        if ($buy_price === null || $quantity * $buy_price > 1.0e12) {
            self::redirect('invalid_buy_price');
        }
        if ($initial_raw !== '' && $initial_price === null) {
            self::redirect('invalid_current_price');
        }
        if ($buy_date !== '' && !self::valid_date($buy_date)) {
            self::redirect('invalid_date');
        }
        $positions = self::positions(get_current_user_id());
        if (count($positions) >= self::MAX_POSITIONS) { self::redirect('limit'); }
        $entry = [
            'id' => wp_generate_uuid4(),
            'ticker' => $ticker,
            'label' => $name,
            'quantity' => $quantity,
            'buy_price' => $buy_price,
            'currency' => $currency,
            'buy_date' => $buy_date,
            'created_at' => gmdate('Y-m-d\TH:i:s\Z'),
        ];
        if ($initial_price !== null) {
            $entry['manual_price'] = $initial_price;
            $entry['manual_price_at'] = gmdate('Y-m-d\TH:i:s\Z');
        }
        $positions[] = $entry;
        $user_id = get_current_user_id();
        $written = update_user_meta($user_id, self::USER_META, $positions);
        // Confirm that the new purchase exists in the actual user-meta store,
        // rather than displaying a false positive when a database write fails.
        $saved = self::positions($user_id);
        $stored = false;
        foreach ($saved as $row) {
            if (($row['id'] ?? '') === $entry['id']) { $stored = true; break; }
        }
        if ($written === false || !$stored) {
            error_log('AI Stock Scanner: portfolio save did not persist for logged-in user.');
            self::redirect('save_failed');
        }
        self::redirect('added');
    }

    public static function delete(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_portfolio_delete');
        $id = self::field('asc_position_id');
        $before = self::positions(get_current_user_id());
        $after = array_values(array_filter($before,
            static fn(array $p): bool => (string)($p['id'] ?? '') !== $id));
        if ($id === '' || count($before) === count($after)) { self::redirect('notfound'); }
        update_user_meta(get_current_user_id(), self::USER_META, $after);
        self::redirect('deleted');
    }

    /** Update the purchase lot, preserving its manual quote and its stable identifier. */
    public static function edit(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_portfolio_edit');
        $id = self::field('asc_position_id');
        $quantity = self::decimal(self::field('asc_quantity'));
        $price = self::decimal(self::field('asc_buy_price'));
        if ($id === '' || $quantity === null || $price === null
            || $quantity * $price > 1.0e12) {
            self::redirect('invalid');
        }
        $positions = self::positions(get_current_user_id());
        $found = false;
        foreach ($positions as &$p) {
            if (($p['id'] ?? '') === $id) {
                $p['quantity'] = $quantity;
                $p['buy_price'] = $price;
                $found = true;
                break;
            }
        }
        unset($p);
        if (!$found) { self::redirect('notfound'); }
        update_user_meta(get_current_user_id(), self::USER_META, $positions);
        self::redirect('edited');
    }

    /** Export personal purchase lots. Formula characters in CSV cells are neutralized. */
    public static function export_csv(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_portfolio_export');
        $rows = self::positions(get_current_user_id());
        nocache_headers();
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="min-aktieportefolje.csv"');
        header('X-Content-Type-Options: nosniff');
        $out = fopen('php://output', 'wb');
        if ($out === false) { exit; }
        fwrite($out, "\xEF\xBB\xBF");
        fputcsv($out, ['Aktie','Navn','Antal','Købskurs','Valuta','Købsdato',
            'Manuel kurs','Tidspunkt for manuel kurs'], ';');
        foreach ($rows as $p) {
            $ticker = (string)($p['ticker'] ?? '');
            $name = (string)($p['label'] ?? '');
            // CSV injection: spreadsheet applications treat leading = + - @ as formulas.
            if (preg_match('/^[\s\x00-\x1f]*[=+\-@]/u', $ticker)) { $ticker = "'" . $ticker; }
            if (preg_match('/^[\s\x00-\x1f]*[=+\-@]/u', $name)) { $name = "'" . $name; }
            fputcsv($out, [
                $ticker, $name, (string)($p['quantity'] ?? ''),
                (string)($p['buy_price'] ?? ''), (string)($p['currency'] ?? ''),
                (string)($p['buy_date'] ?? ''), (string)($p['manual_price'] ?? ''),
                (string)($p['manual_price_at'] ?? ''),
            ], ';');
        }
        fclose($out);
        exit;
    }

    /** Optional manual quote when an authorized data feed has not been configured. */
    public static function set_manual_price(): void {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer('asc_portfolio_price');
        $id = self::field('asc_position_id');
        $price = self::decimal(self::field('asc_current_price'));
        if ($price === null) { self::redirect('invalid'); }
        $positions = self::positions(get_current_user_id());
        $found = false;
        foreach ($positions as &$p) {
            if ($id !== '' && (string)($p['id'] ?? '') === $id) {
                $p['manual_price'] = $price;
                $p['manual_price_at'] = gmdate('Y-m-d\TH:i:s\Z');
                $found = true;
                break;
            }
        }
        unset($p);
        if (!$found) { self::redirect('notfound'); }
        update_user_meta(get_current_user_id(), self::USER_META, $positions);
        self::redirect('priced');
    }

    /**
     * Admin-only explicit action. Avoid altering the site's homepage on activation
     * or plugin upgrade. Only invoked when admin clicks "Opret startside".
     */
    public static function create_home(): void {
        if (!current_user_can('manage_options')) { wp_die('Ingen adgang.'); }
        check_admin_referer('asc_create_home');
        $id = (int)get_option('asc_home_page_id', 0);
        if ($id <= 0 || get_post_type($id) !== 'page') {
            $created = wp_insert_post([
                'post_type' => 'page', 'post_status' => 'publish',
                'post_title' => 'Min aktieoversigt',
                'post_name' => 'min-aktieoversigt',
                'post_content' => '[ai_stock_home]',
                'comment_status' => 'closed',
            ], true);
            if (is_wp_error($created)) { wp_die('Kunne ikke oprette WordPress-side.'); }
            $id = (int)$created;
            update_option('asc_home_page_id', $id, false);
        }
        update_option('show_on_front', 'page');
        update_option('page_on_front', $id);
        wp_safe_redirect(admin_url('admin.php?page=asc-dashboard&asc_home=created'));
        exit;
    }

    private static function login(): string {
        wp_enqueue_style('hangar18-asc');
        ob_start();
        echo '<section class="asc-dashboard asc-login">';
        echo '<header class="asc-heading"><h2>Velkommen til min aktieoversigt</h2><p>Følg din portefølje, også når din PC er slukket.</p></header>';
        wp_login_form([
            'echo' => true, 'remember' => true,
            'redirect' => home_url('/'),
            'label_username' => 'Brugernavn eller e-mail',
            'label_password' => 'Adgangskode',
            'label_remember' => 'Husk mig',
            'label_log_in' => 'Log ind',
        ]);
        echo '<p class="asc-disclaimer">Brug din normale WordPress-bruger, ikke scannerens Application Password.</p>';
        echo '<div class="asc-demo-overview"><h3>Eksempel på en portefølje</h3>';
        echo '<p class="asc-demo-tag">Illustration – ikke rigtige aktiekurser</p>';
        echo '<div class="asc-demo-metrics"><div><span>100 aktier til 100,00 kr.</span><strong>Investeret: 10.000 kr.</strong></div>';
        echo '<div><span>Manuel kurs 112,00 kr.</span><strong>Værdi: 11.200 kr.</strong></div>';
        echo '<div><span>Gevinst før omkostninger</span><strong class="asc-positive">+1.200 kr. (+12,00 %)</strong></div></div>';
        echo '<p>Efter login kan du oprette dine egne aktier, opdatere kursen, redigere køb og eksportere dine data.</p></div>';
        echo '</section>';
        return (string)ob_get_clean();
    }

    public static function render_home(): string {
        if (!is_user_logged_in()) { return self::login(); }
        wp_enqueue_style('hangar18-asc');
        $user = wp_get_current_user();
        $first = trim((string)$user->first_name);
        $first = $first !== '' ? $first : $user->display_name;
        ob_start();
        echo '<section class="asc-dashboard asc-home">';
        echo '<header class="asc-heading"><h2>Velkommen ' . esc_html($first) . '</h2>';
        echo '<p>Din portefølje og dine aktieanalyser samlet ét sted.</p>';
        echo '<nav class="asc-home-nav"><a href="#asc-portfolio">Min portefølje</a>'
            . '<a href="#asc-watchlist">Min watchlist</a>'
            . '<a href="#asc-research">Aktiescanner</a>'
            . '<a href="' . esc_url(wp_logout_url(home_url('/'))) . '">Log ud</a></nav></header>';
        echo self::markup();
        echo ASC_Watchlist::render();
        echo '<div id="asc-research">' . do_shortcode('[ai_stock_scanner]') . '</div>';
        echo '</section>';
        return (string)ob_get_clean();
    }

    public static function render(): string {
        if (!is_user_logged_in()) { return self::login(); }
        wp_enqueue_style('hangar18-asc');
        return '<section class="asc-dashboard">' . self::markup() . '</section>';
    }

    private static function amount(float $num): string {
        return esc_html(number_format($num, 2, ',', '.'));
    }

    private static function external_link(string $ticker): string {
        // Known, grounded Nordnet pages. Never guess arbitrary URLs from a ticker.
        $links = [
            'NOBI.ST' => 'https://www.nordnet.dk/aktier/kurser/nobia-nobi-xsto',
            'HARB-B.CO' => 'https://www.nordnet.dk/aktier/kurser/harboes-bryggeri-b-harb-b-xcse',
        ];
        return isset($links[$ticker])
            ? ' <a href="' . esc_url($links[$ticker]) . '" target="_blank" rel="noopener noreferrer">Nordnet</a>'
            : '';
    }

    private static function markup(): string {
        $positions = self::positions(get_current_user_id());
        $quotes = [];
        foreach ($positions as $p) {
            $ticker = (string)($p['ticker'] ?? '');
            if ($ticker !== '' && !array_key_exists($ticker, $quotes)) {
                $quotes[$ticker] = ASC_Market_Quotes::get($ticker);
            }
        }
        $totals = [];
        $position_counts = [];
        $priced_count = 0;
        ob_start();
        echo '<section id="asc-portfolio" class="asc-portfolio">';
        echo '<div class="asc-section-title"><h2>Min portefølje</h2><p>Kun du kan se og ændre dine køb.</p></div>';
        $status = isset($_GET['asc_portfolio_status']) && is_string($_GET['asc_portfolio_status'])
            ? sanitize_key($_GET['asc_portfolio_status']) : '';
        $messages = [
            'added' => 'Aktiekøbet er gemt og verificeret i WordPress.',
            'deleted' => 'Beholdningen er slettet.',
            'priced' => 'Din manuelle kurs er opdateret.',
            'edited' => 'Antal og købskurs er opdateret.',
            'invalid' => 'Kontrollér antal og købskurs.',
            'invalid_ticker' => 'Aktiesymbolet er ugyldigt. Brug fx NOVO-B.CO, SAP.DE eller MSFT (uden mellemrum).',
            'invalid_currency' => 'Valutaen skal være DKK, SEK, NOK, EUR eller USD.',
            'invalid_quantity' => 'Antal aktier skal være et positivt tal (fx 10 eller 2,5).',
            'invalid_buy_price' => 'Købskursen skal være et positivt tal og beløbet inden for grænsen.',
            'invalid_current_price' => 'Den manuelle aktuelle kurs skal være et positivt tal, eller feltet skal stå tomt.',
            'invalid_date' => 'Købsdatoen er ugyldig eller ligger i fremtiden.',
            'save_failed' => 'WordPress kunne ikke gemme købet i databasen. Forsøg igen, eller undersøg webhotellets PHP-fejllog.',
            'limit' => 'Der kan højst gemmes 100 køb pr. bruger.',
            'notfound' => 'Kunne ikke finde den valgte beholdning.',
        ];
        if (isset($messages[$status])) {
            $ok = in_array($status, ['added', 'deleted', 'priced', 'edited'], true);
            echo '<div class="asc-notice ' . ($ok ? 'asc-notice-ok' : 'asc-notice-error')
                . '" role="' . ($ok ? 'status' : 'alert') . '"><strong>'
                . ($ok ? 'OK: ' : 'Fejl: ') . esc_html($messages[$status])
                . '</strong><div class="asc-subtle">Kode: ' . esc_html($status) . '</div></div>';
        }
        echo '<p class="asc-saved-count">Gemte aktiekøb: <strong>' . esc_html((string)count($positions))
            . '</strong> af ' . esc_html((string)self::MAX_POSITIONS) . '</p>';
        echo '<div class="asc-portfolio-actions"><form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_portfolio_export">';
        wp_nonce_field('asc_portfolio_export');
        echo '<button type="submit">Eksportér mine køb (CSV)</button></form></div>';
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        echo '<th scope="col">Aktie</th><th scope="col">Antal</th><th scope="col">Købskurs</th>';
        echo '<th scope="col">Seneste kurs</th><th scope="col">Investeret</th>';
        echo '<th scope="col">Værdi</th><th scope="col">Gevinst/tab</th><th scope="col">Handling</th>';
        echo '</tr></thead><tbody>';
        if (!$positions) {
            echo '<tr><td colspan="8">Du har endnu ingen aktier. Indtast dit første køb nedenfor. Angiv også en manuel aktuel kurs for at se gevinst/tab med det samme.</td></tr>';
        }
        foreach ($positions as $p) {
            $ticker = (string)($p['ticker'] ?? '');
            $currency = (string)($p['currency'] ?? '');
            $quantity = (float)($p['quantity'] ?? 0);
            $cost = (float)($p['buy_price'] ?? 0);
            if ($quantity <= 0 || $cost <= 0) { continue; }
            $basis = $quantity * $cost;
            $quote = $quotes[$ticker] ?? null;
            $price = null;
            $label = '';
            $price_at = '';
            if (is_array($quote) && ($quote['currency'] ?? '') === $currency
                && is_numeric($quote['price'] ?? null) && (float)$quote['price'] > 0) {
                $price = (float)$quote['price'];
                $price_at = wp_date('d-m-Y H:i', (int)($quote['market_time'] ?? time()));
                $label = 'Yahoo, ' . $price_at . (!empty($quote['stale']) ? ' (gammel)' : '');
            } elseif (is_numeric($p['manual_price'] ?? null) && (float)$p['manual_price'] > 0) {
                $price = (float)$p['manual_price'];
                $price_at = (string)($p['manual_price_at'] ?? '');
                $label = 'Manuel kurs ' . $price_at;
            } elseif (is_array($quote) && ($quote['currency'] ?? '') !== $currency) {
                $label = 'Kursvaluta matcher ikke købsvaluta';
            } else {
                $label = ASC_Market_Quotes::enabled() ? 'Kurs ikke tilgængelig' : 'Automatisk kurskilde ikke aktiveret';
            }

            echo '<tr><th scope="row">' . esc_html((string)($p['label'] ?: $ticker))
                . '<div class="asc-subtle">' . esc_html($ticker) . self::external_link($ticker) . '</div>'
                . '<div class="asc-subtle">' . esc_html((string)($p['buy_date'] ?? '')) . '</div></th>';
            echo '<td>' . self::amount($quantity) . '</td><td>' . self::amount($cost) . ' ' . esc_html($currency) . '</td>';
            echo '<td>' . ($price !== null ? self::amount($price) . ' ' . esc_html($currency) : '—')
                . '<div class="asc-subtle">' . esc_html($label) . '</div></td>';
            echo '<td>' . self::amount($basis) . ' ' . esc_html($currency) . '</td>';
            if ($price !== null) {
                $value = $quantity * $price;
                $pnl = $value - $basis;
                $pct = 100 * ($price / $cost - 1);
                $class = $pnl >= 0 ? 'asc-positive' : 'asc-negative';
                echo '<td>' . self::amount($value) . ' ' . esc_html($currency) . '</td>';
                echo '<td class="' . esc_attr($class) . '">' . ($pnl > 0 ? '+' : '')
                    . self::amount($pnl) . ' ' . esc_html($currency) . '<div>'
                    . ($pct > 0 ? '+' : '') . self::amount($pct) . '%</div></td>';
                if (!isset($totals[$currency])) { $totals[$currency] = ['cost' => 0.0, 'value' => 0.0]; }
                $totals[$currency]['cost'] += $basis;
                $totals[$currency]['value'] += $value;
                $position_counts[$currency] = ($position_counts[$currency] ?? 0) + $quantity;
                $priced_count++;
            } else {
                echo '<td>—</td><td>—</td>';
            }

            echo '<td><details><summary>Opdater</summary>';
            echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" class="asc-inline-form">';
            echo '<input type="hidden" name="action" value="asc_portfolio_edit">';
            echo '<input type="hidden" name="asc_position_id" value="' . esc_attr((string)$p['id']) . '">';
            wp_nonce_field('asc_portfolio_edit');
            echo '<label>Antal aktier <input name="asc_quantity" type="text" inputmode="decimal" value="' . esc_attr((string)$quantity) . '" required></label>';
            echo '<label>Købskurs <input name="asc_buy_price" type="text" inputmode="decimal" value="' . esc_attr((string)$cost) . '" required></label>';
            echo '<button type="submit">Gem beholdning</button></form>';
            echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" class="asc-inline-form">';
            echo '<input type="hidden" name="action" value="asc_portfolio_price">';
            echo '<input type="hidden" name="asc_position_id" value="' . esc_attr((string)$p['id']) . '">';
            wp_nonce_field('asc_portfolio_price');
            echo '<label>Manuel aktuel kurs <input name="asc_current_price" type="text" inputmode="decimal" placeholder="100,50" required></label>';
            echo '<button type="submit">Gem kurs</button></form>';
            echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" class="asc-inline-form">';
            echo '<input type="hidden" name="action" value="asc_portfolio_delete">';
            echo '<input type="hidden" name="asc_position_id" value="' . esc_attr((string)$p['id']) . '">';
            wp_nonce_field('asc_portfolio_delete');
            echo '<button type="submit" class="asc-delete">Slet køb</button></form>';
            echo '</details></td></tr>';
            if (is_array($quote) && !empty($quote['history'])) {
                echo '<tr class="asc-chart-row"><td colspan="8">';
                echo '<details><summary>Vis kursgraf og handelsvolumen for ' . esc_html($ticker) . '</summary>';
                echo ASC_Market_Quotes::chart_markup($ticker, $quote);
                echo '</details></td></tr>';
            }
        }
        echo '</tbody></table></div>';
        echo '<p class="asc-disclaimer">Porteføljeberegninger er før kurtage, skat og udbytte. '
            . 'Beløb i forskellige valutaer lægges ikke sammen uden en valutakurs. '
            . 'Kun beholdninger med kendt kurs indgår i summerne.</p>';
        if ($totals) {
            echo '<div class="asc-metrics asc-portfolio-summary">';
            foreach ($totals as $currency => $summary) {
                $gain = $summary['value'] - $summary['cost'];
                $pct = $summary['cost'] > 0 ? $gain / $summary['cost'] * 100 : 0;
                echo '<div><span>Porteføljens værdi / net worth (' . esc_html($currency) . ')</span>';
                echo '<strong>' . self::amount($summary['value']) . ' ' . esc_html($currency) . '</strong>';
                echo '<span>Investeret: ' . self::amount($summary['cost']) . ' '
                    . esc_html($currency) . '</span>';
                echo '<span>Antal aktier: ' . self::amount((float)($position_counts[$currency] ?? 0)) . '</span>';
                echo '<span class="' . esc_attr($gain >= 0 ? 'asc-positive' : 'asc-negative') . '">'
                    . ($gain > 0 ? '+' : '') . self::amount($gain) . ' (' . ($pct > 0 ? '+' : '')
                    . self::amount($pct) . '%)</span></div>';
            }
            echo '</div>';
        }
        if ($priced_count < count($positions)) {
            echo '<p class="asc-warning">Nogle aktier mangler kurs. Deres gevinst/tab er ikke beregnet endnu.</p>';
        }
        echo '<div class="asc-add-position" id="asc-add-position"><h3>Tilføj et aktiekøb</h3>';
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_portfolio_add">';
        wp_nonce_field('asc_portfolio_add');
        echo '<label>Ticker (Yahoo-symbol)<input type="text" name="asc_ticker" maxlength="20" '
            . 'placeholder="NOBI.ST eller HARB-B.CO" required></label>';
        echo '<label>Navn (valgfrit)<input type="text" name="asc_label" maxlength="80" placeholder="F.eks. Nobia"></label>';
        echo '<label>Antal aktier<input type="text" name="asc_quantity" inputmode="decimal" placeholder="100" required></label>';
        echo '<label>Købskurs pr. aktie<input type="text" name="asc_buy_price" inputmode="decimal" placeholder="12,50" required></label>';
        echo '<label>Aktuel kurs (valgfrit, manuel)<input type="text" name="asc_initial_price" inputmode="decimal" placeholder="13,25"></label>';
        echo '<label>Valuta<select name="asc_currency">';
        foreach (['DKK', 'SEK', 'NOK', 'EUR', 'USD'] as $currency) {
            echo '<option value="' . esc_attr($currency) . '">' . esc_html($currency) . '</option>';
        }
        echo '</select></label>';
        echo '<label>Købsdato (valgfri)<input type="date" name="asc_buy_date" max="' . esc_attr(wp_date('Y-m-d')) . '"></label>';
        echo '<button type="submit">Gem aktiekøb og beregn</button></form>';
        echo '<p class="asc-disclaimer">Du kan starte med en manuel kurs. Automatisk kursopdatering kræver en kurskilde; ingen forbindelse til PC-scanneren er nødvendig.</p></div>';
        if (!ASC_Market_Quotes::enabled()) {
            echo '<p class="asc-disclaimer">Der er ikke aktiveret en automatisk kurskilde. '
                . 'Du kan indtaste en manuel kurs, eller administratoren kan vælge en eksperimentel kurskilde under AI Stock Scanner → Forbindelse.</p>';
        } else {
            echo '<p class="asc-disclaimer">Automatiske kurser kommer fra en uofficiel Yahoo-integration. '
                . 'De kan være forsinkede eller utilgængelige. Gennemgå datavilkårene før aktivering.</p>';
        }
        echo '</section>';
        return (string)ob_get_clean();
    }
}
