<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Searchable Copenhagen stock directory. Public third-party CC0 reference
 * snapshot, not an exchange-certified live master or quote service.
 *
 * Source CSV: kjhq/Denmark-Stock-Symbols-and-Metadata (CC0 1.0, Sep 2025)
 * https://huggingface.co/datasets/kjhq/Denmark-Stock-Symbols-and-Metadata
 *
 * Full current coverage requires an updated, properly licensed CSV import.
 * Existing portfolio/watchlist records are never touched by directory imports.
 */
final class ASC_Danish_Catalog {
    private const OPTION = 'asc_danish_catalog_v1';
    private const COOLDOWN = 'asc_danish_catalog_fetch_cooldown_v1';
    private const SOURCE = 'https://huggingface.co/datasets/kjhq/Denmark-Stock-Symbols-and-Metadata/raw/main/denmark.csv';
    private const MAX_BYTES = 100000;
    private const MAX_ROWS = 600;
    private const PER_PAGE = 25;

    public static function register(): void {
        add_shortcode('ai_stock_catalog', [self::class, 'render']);
        add_action('admin_post_asc_catalog_refresh', [self::class, 'refresh_action']);
        add_action('admin_post_asc_catalog_import', [self::class, 'import_action']);
    }

    private static function source_meta(array $rows, string $source): array {
        return [
            'rows' => $rows,
            'source' => $source,
            'updated_at' => gmdate('Y-m-d H:i:s') . ' UTC',
        ];
    }

    private static function canonical_symbol(string $original): ?string {
        $ticker = strtoupper(trim($original));
        if (preg_match('/^[A-Z0-9][A-Z0-9._-]{0,19}$/D', $ticker) !== 1) {
            return null;
        }
        // Nordic market-symbol formats use "_" for share classes. This is
        // a Yahoo *candidate*, not a verified quote identifier.
        if (str_ends_with($ticker, '.CO')) { return $ticker; }
        if (strpos($ticker, '.') !== false) { return null; }
        $ticker = str_replace('_', '-', $ticker);
        return strlen($ticker) <= 17 ? $ticker . '.CO' : null;
    }

    /**
     * Public for offline regression tests. Supports the CC0 source CSV and
     * administrator-supplied CSV with optional ISIN and sector.
     */
    public static function parse_csv(string $body): array {
        if ($body === '' || strlen($body) > self::MAX_BYTES ||
            str_contains($body, "\0")) { return []; }
        $body = preg_replace('/^\xEF\xBB\xBF/', '', $body) ?? $body;
        $first = strtok($body, "\r\n");
        if (!is_string($first)) { return []; }
        $delimiter = substr_count($first, ';') > substr_count($first, ',') ? ';' : ',';
        $fp = fopen('php://temp', 'w+');
        if ($fp === false) { return []; }
        fwrite($fp, $body);
        rewind($fp);
        try {
            $header = fgetcsv($fp, 0, $delimiter, '"', '');
            if (!is_array($header)) { return []; }
            $headers = array_map(static fn($h) => strtolower(trim((string)$h)), $header);
            $column = static function(array $aliases) use ($headers): ?int {
                foreach ($aliases as $name) {
                    $index = array_search($name, $headers, true);
                    if ($index !== false) { return $index; }
                }
                return null;
            };
            $i_name = $column(['name', 'company_name', 'company', 'navn', 'selskab']);
            $i_ticker = $column(['ticker_yahoo', 'yahoo_symbol', 'ticker', 'symbol']);
            $i_original = $column(['ticker', 'symbol']);
            $i_isin = $column(['isin']);
            $i_sector = $column(['sector', 'sektor']);
            $i_market = $column(['market', 'exchange', 'bors', 'børs']);
            if ($i_name === null || $i_ticker === null) { return []; }
            $seen = [];
            $rows = [];
            while (($fields = fgetcsv($fp, 0, $delimiter, '"', '')) !== false) {
                if (count($rows) >= self::MAX_ROWS) { return []; }
                if (count($fields) < count($headers)) { continue; }
                $name = trim(strip_tags((string)($fields[$i_name] ?? '')));
                $name = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $name) ?? '';
                $name = trim($name);
                $raw = trim((string)($fields[$i_ticker] ?? ''));
                $ticker = self::canonical_symbol($raw);
                if ($ticker === null || $name === '' || strlen($name) > 160 ||
                    isset($seen[$ticker])) { continue; }
                if ($i_market !== null) {
                    $market = strtoupper(trim((string)($fields[$i_market] ?? '')));
                    if ($market !== '' && !in_array($market, [
                        'OMXCOP', 'XCSE', 'XCPH', 'COPENHAGEN', 'DENMARK',
                        'DANMARK', 'DK',
                    ], true)) { continue; }
                }
                $isin = strtoupper(trim((string)($i_isin !== null ? ($fields[$i_isin] ?? '') : '')));
                if ($isin !== '' && preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D', $isin) !== 1) {
                    $isin = '';
                }
                $sector = $i_sector !== null
                    ? trim(strip_tags((string)($fields[$i_sector] ?? ''))) : '';
                $sector = (string)substr($sector, 0, 72);
                $original = $i_original !== null
                    ? strtoupper(trim((string)($fields[$i_original] ?? ''))) : $raw;
                $rows[] = [
                    'name' => $name,
                    'ticker' => $ticker,
                    'symbol' => $original,
                    'isin' => $isin,
                    'sector' => $sector,
                    'currency' => 'DKK',
                    'type' => 'Aktie',
                ];
                $seen[$ticker] = true;
            }
            usort($rows, static fn($a, $b) => strcasecmp($a['name'], $b['name']));
            return $rows;
        } finally {
            fclose($fp);
        }
    }

    private static function fallback(): array {
        // Bundled 2025 CC0 reference snapshot, not a guaranteed live listing.
        $file = dirname(__DIR__) . '/assets/danish-stocks-snapshot.csv';
        if (is_readable($file)) {
            $body = file_get_contents($file);
            $rows = is_string($body) ? self::parse_csv($body) : [];
            if (count($rows) >= 100) { return $rows; }
        }
        // Minimal offline examples. Do NOT label these as all listed stocks.
        $examples = [
            ['Novo Nordisk B', 'NOVO-B.CO'],
            ['DSV', 'DSV.CO'],
            ['Vestas Wind Systems', 'VWS.CO'],
            ['A.P. Møller - Mærsk B', 'MAERSK-B.CO'],
            ['Carlsberg B', 'CARL-B.CO'],
            ['Danske Bank', 'DANSKE.CO'],
            ['Genmab', 'GMAB.CO'],
            ['Harboes Bryggeri B', 'HARB-B.CO'],
            ['Tryg', 'TRYG.CO'],
            ['Pandora', 'PNDORA.CO'],
            ['Bavarian Nordic', 'BAVA.CO'],
            ['Ørsted', 'ORSTED.CO'],
        ];
        return array_map(static fn($e) => [
            'name' => $e[0], 'ticker' => $e[1],
            'symbol' => str_replace('.CO', '', $e[1]),
            'isin' => '', 'sector' => '', 'currency' => 'DKK', 'type' => 'Aktie',
        ], $examples);
    }

    /** A failed/partial fetch never overwrites a previously valid catalogue. */
    private static function pull_public(): bool {
        $response = wp_safe_remote_get(self::SOURCE, [
            'timeout' => 6,
            'redirection' => 2,
            'limit_response_size' => self::MAX_BYTES,
            'headers' => ['Accept' => 'text/csv,text/plain'],
        ]);
        if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
            return false;
        }
        $rows = self::parse_csv((string)wp_remote_retrieve_body($response));
        // An unexpectedly tiny feed is treated as a failed refresh.
        if (count($rows) < 100) { return false; }
        update_option(self::OPTION, self::source_meta($rows, 'CC0-snapshot (2025, ikke børsgodkendt)'), false);
        return true;
    }

    private static function catalog(): array {
        $stored = get_option(self::OPTION, []);
        $valid = is_array($stored) && is_array($stored['rows'] ?? null)
            && count($stored['rows']) > 0;
        if (!$valid) {
            $seed = self::fallback();
            $source = count($seed) >= 100
                ? 'Bundlet CC0-snapshot (2025, ikke live)'
                : 'Offline-eksempler (ufuldstændige)';
            $stored = self::source_meta($seed, $source);
            update_option(self::OPTION, $stored, false);
            // Avoid blocking the first page view with an external request.
            set_transient(self::COOLDOWN, 1, DAY_IN_SECONDS);
            return $stored;
        }
        $loaded_at = strtotime((string)($stored['updated_at'] ?? '')) ?: 0;
        $age = time() - $loaded_at;
        $is_public = str_contains((string)($stored['source'] ?? ''), 'CC0');
        if ($is_public && $age > 7 * DAY_IN_SECONDS &&
            get_transient(self::COOLDOWN) === false) {
            set_transient(self::COOLDOWN, 1, DAY_IN_SECONDS);
            if (self::pull_public()) {
                $stored = get_option(self::OPTION, $stored);
            }
        }
        return $stored;
    }

    private static function redirect(string $status): void {
        $referer = wp_get_referer();
        $base = is_string($referer) && $referer !== ''
            ? wp_validate_redirect($referer, home_url('/')) : home_url('/');
        $base = remove_query_arg('asc_catalog_status', $base);
        $base = add_query_arg('asc_view', 'stocks', $base);
        wp_safe_redirect(add_query_arg('asc_catalog_status', $status, $base) . '#asc-catalog');
        exit;
    }

    public static function refresh_action(): void {
        if (!current_user_can('manage_options')) { wp_die('Ingen adgang.'); }
        check_admin_referer('asc_catalog_refresh');
        // Explicit administrator action may refresh even during cooldown.
        $ok = self::pull_public();
        if ($ok) { set_transient(self::COOLDOWN, 1, DAY_IN_SECONDS); }
        self::redirect($ok ? 'refreshed' : 'fetch_failed');
    }

    public static function import_action(): void {
        if (!current_user_can('manage_options')) { wp_die('Ingen adgang.'); }
        check_admin_referer('asc_catalog_import');
        $file = $_FILES['asc_catalog_csv'] ?? null;
        if (!is_array($file) || ($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK ||
            !is_int($file['size'] ?? null) || $file['size'] <= 0 ||
            $file['size'] > self::MAX_BYTES ||
            !is_string($file['tmp_name'] ?? null) ||
            !is_uploaded_file($file['tmp_name'])) {
            self::redirect('file_error');
        }
        $content = file_get_contents($file['tmp_name'], false, null, 0, self::MAX_BYTES + 1);
        $rows = is_string($content) ? self::parse_csv($content) : [];
        if (!$rows) { self::redirect('invalid_csv'); }
        update_option(self::OPTION, self::source_meta($rows, 'Administratorimport (CSV)'), false);
        set_transient(self::COOLDOWN, 1, DAY_IN_SECONDS);
        self::redirect('imported');
    }

    public static function render(): string {
        if (!is_user_logged_in()) { return '<p>Log ind for at se aktiekataloget.</p>'; }
        wp_enqueue_style('hangar18-asc');
        $data = self::catalog();
        $rows = $data['rows'];
        $query = isset($_GET['asc_query']) && is_string($_GET['asc_query'])
            ? trim(sanitize_text_field(wp_unslash($_GET['asc_query']))) : '';
        if (strlen($query) > 90) { $query = substr($query, 0, 90); }
        $sector = isset($_GET['asc_sector']) && is_string($_GET['asc_sector'])
            ? sanitize_text_field(wp_unslash($_GET['asc_sector'])) : '';
        $sectors = array_values(array_unique(array_filter(array_column($rows, 'sector'))));
        sort($sectors, SORT_STRING);
        if (!in_array($sector, $sectors, true)) { $sector = ''; }
        $filtered = array_values(array_filter($rows, static function ($r) use ($query, $sector) {
            if ($sector !== '' && $r['sector'] !== $sector) { return false; }
            if ($query === '') { return true; }
            foreach (['name','ticker','symbol','isin','sector'] as $field) {
                $value = (string)($r[$field] ?? '');
                if (function_exists('mb_stripos')
                    ? mb_stripos($value, $query, 0, 'UTF-8') !== false
                    : stripos($value, $query) !== false) {
                    return true;
                }
            }
            return false;
        }));
        $page = isset($_GET['asc_catalog_page']) && is_string($_GET['asc_catalog_page'])
            ? max(1, min(1000, (int)$_GET['asc_catalog_page'])) : 1;
        $pages = max(1, (int)ceil(count($filtered) / self::PER_PAGE));
        $page = min($page, $pages);
        $page_rows = array_slice($filtered, ($page - 1) * self::PER_PAGE, self::PER_PAGE);
        $page_url = get_permalink(get_queried_object_id()) ?: home_url('/');
        $page_url = add_query_arg('asc_view', 'stocks', $page_url);
        $filter_url = add_query_arg(['asc_query' => $query, 'asc_sector' => $sector], $page_url);

        ob_start();
        echo '<section id="asc-catalog" class="asc-stock-catalog">';
        echo '<h2>Søg i danske aktier</h2>';
        echo '<p>Søg efter selskab, ticker, sektor eller ISIN, når ISIN er oplyst. '
            . 'Der vises ingen opfundne kurser eller købssignaler.</p>';
        echo '<p class="asc-catalog-info"><strong>' . esc_html((string)count($rows))
            . ' registrerede papirer</strong> · Kilde: '
            . esc_html((string)$data['source']) . ' · Indlæst: '
            . esc_html((string)($data['updated_at'] ?? '')) . '</p>';
        echo '<p class="asc-disclaimer">Det åbne grunddatasæt blev udgivet i 2025 og '
            . 'kan indeholde afnoterede papirer eller mangle nye noteringer. '
            . 'Listen er derfor ikke en garanteret komplet, opdateret Nasdaq Copenhagen-liste. '
            . 'Yahoo-symboler er kandidater og bør kontrolleres, før de bruges til kurser.</p>';
        $statuses = [
            'refreshed' => 'Det åbne katalog er opdateret.',
            'imported' => 'CSV-kataloget blev indlæst. Tidligere køb og watchlist er uændrede.',
            'fetch_failed' => 'Kunne ikke hente det åbne katalog. Den senest gemte liste bruges fortsat.',
            'file_error' => 'Ugyldig CSV-fil eller fil større end 100 KB.',
            'invalid_csv' => 'Kunne ikke læse CSV. Brug mindst kolonnerne name og ticker.',
        ];
        $status = isset($_GET['asc_catalog_status']) && is_string($_GET['asc_catalog_status'])
            ? sanitize_key(wp_unslash($_GET['asc_catalog_status'])) : '';
        if (isset($statuses[$status])) {
            echo '<p role="status" class="asc-notice">' . esc_html($statuses[$status]) . '</p>';
        }
        echo '<form class="asc-filter-form" method="get" action="">';
        echo '<input type="hidden" name="asc_view" value="stocks">';
        echo '<label>Søg<input name="asc_query" type="search" placeholder="Harboe, NOVO, DK..." value="'
            . esc_attr($query) . '" maxlength="90"></label>';
        echo '<label>Sektor<select name="asc_sector"><option value="">Alle sektorer</option>';
        foreach ($sectors as $value) {
            echo '<option value="' . esc_attr($value) . '" '
                . selected($sector, $value, false) . '>' . esc_html($value) . '</option>';
        }
        echo '</select></label><button type="submit">Søg</button></form>';
        echo '<p>' . esc_html((string)count($filtered)) . ' resultater, side '
            . esc_html((string)$page) . ' af ' . esc_html((string)$pages) . '.</p>';
        echo '<div class="asc-table-wrap"><table><thead><tr><th>Selskab</th><th>Ticker</th>'
            . '<th>ISIN</th><th>Sektor</th><th>Handlinger</th></tr></thead><tbody>';
        foreach ($page_rows as $r) {
            $portfolio_url = add_query_arg([
                'asc_view' => 'portfolio',
                'asc_ticker' => $r['ticker'],
                'asc_name' => $r['name'],
                'asc_currency' => 'DKK',
            ], get_permalink(get_queried_object_id()) ?: home_url('/'));
            echo '<tr><th scope="row">' . esc_html($r['name']) . '</th>';
            echo '<td><strong>' . esc_html($r['ticker']) . '</strong>'
                . '<span class="asc-subtle">Kildekode: ' . esc_html($r['symbol']) . '</span></td>';
            echo '<td>' . esc_html($r['isin'] !== '' ? $r['isin'] : '—') . '</td>';
            echo '<td>' . esc_html($r['sector'] !== '' ? $r['sector'] : '—') . '</td>';
            echo '<td class="asc-catalog-actions">';
            echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
            echo '<input type="hidden" name="action" value="asc_watch_add">';
            echo '<input type="hidden" name="asc_watch_ticker" value="' . esc_attr($r['ticker']) . '">';
            wp_nonce_field('asc_watch_add');
            echo '<button type="submit">Følg</button></form>';
            echo '<a href="' . esc_url($portfolio_url) . '">Registrér køb</a></td></tr>';
        }
        if (!$page_rows) {
            echo '<tr><td colspan="5">Ingen aktier fundet. Prøv et andet søgeord.</td></tr>';
        }
        echo '</tbody></table></div>';
        if ($pages > 1) {
            echo '<nav class="asc-catalog-pages" aria-label="Resultatsider">';
            if ($page > 1) {
                echo '<a href="' . esc_url(add_query_arg('asc_catalog_page', $page - 1, $filter_url)) . '">Forrige</a>';
            }
            if ($page < $pages) {
                echo '<a href="' . esc_url(add_query_arg('asc_catalog_page', $page + 1, $filter_url)) . '">Næste</a>';
            }
            echo '</nav>';
        }
        if (current_user_can('manage_options')) {
            echo '<details class="asc-catalog-admin"><summary>Administrer aktiekatalog (administrator)</summary>';
            echo '<p>Hent igen fra det åbne CC0-datasæt, eller importér en nyere '
                . 'CSV-fil fra en datakilde, du har ret til at bruge. '
                . 'Importerede data gemmes i databasen, ikke i pluginmappen.</p>';
            echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
            echo '<input type="hidden" name="action" value="asc_catalog_refresh">';
            wp_nonce_field('asc_catalog_refresh');
            echo '<button type="submit">Hent åbent katalog</button></form>';
            echo '<form method="post" enctype="multipart/form-data" action="'
                . esc_url(admin_url('admin-post.php')) . '">';
            echo '<input type="hidden" name="action" value="asc_catalog_import">';
            wp_nonce_field('asc_catalog_import');
            echo '<label>Importer CSV (maks. 100 KB)<input type="file" name="asc_catalog_csv" '
                . 'accept=".csv,text/csv" required></label>';
            echo '<button type="submit">Importer liste</button></form>';
            echo '<p class="asc-disclaimer">CSV-kolonner: name,ticker,market,sector,isin '
                . '(kun name og ticker er påkrævet). '
                . 'Brug Yahoo-ticker med .CO, eller børssymbol (fx HARB_B). '
                . 'Valider de foreslåede Yahoo-symboler mod den faktiske notering.</p>';
            echo '</details>';
        }
        echo '<p class="asc-disclaimer">Kilde: <a href="'
            . esc_url('https://huggingface.co/datasets/kjhq/Denmark-Stock-Symbols-and-Metadata')
            . '" target="_blank" rel="noopener noreferrer">Åbent CC0-datasæt</a>. '
            . 'Sammenlign med <a href="' . esc_url('https://www.nasdaq.com/products/european-markets/copenhagen')
            . '" target="_blank" rel="noopener noreferrer">Nasdaq Copenhagen</a> før handel.</p>';
        echo '</section>';
        return (string)ob_get_clean();
    }
}
