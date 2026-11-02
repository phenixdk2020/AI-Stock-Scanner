<?php
/**
 * Plugin Name: Hangar18 AI Stock Scanner
 * Description: Loginbeskyttet dashboard til validerede forskningsresultater fra lokal Python-scanner.
 * Version: 0.6.1
 * Requires at least: 6.4
 * Requires PHP: 8.0
 * Author: Hangar18
 * Update URI: https://github.com/phenixdk2020/AI-Stock-Scanner
 * Text Domain: hangar18-ai-stock-scanner
 */
declare(strict_types=1);

if (!defined('ABSPATH')) {
    exit;
}
define('ASC_PLUGIN_VERSION', '0.6.1');
define('ASC_OPTION_SNAPSHOT', 'asc_latest_snapshot_v1');

// Must initialize before user-profile / REST authentication determines HTTPS.
require_once __DIR__ . '/includes/class-asc-https-proxy.php';
ASC_HTTPS_Proxy::bootstrap();

// Portfolio stays per-user in WordPress user metadata; quote source is optional.
require_once __DIR__ . '/includes/class-asc-market-quotes.php';
ASC_Market_Quotes::register();
// ECB reference-rate conversion is separate from unlicensed quote providers.
require_once __DIR__ . '/includes/class-asc-fx-rates.php';
require_once __DIR__ . '/includes/class-asc-portfolio.php';
ASC_Portfolio::register();
require_once __DIR__ . '/includes/class-asc-playbook.php';
ASC_Playbook::register();
require_once __DIR__ . '/includes/class-asc-watchlist.php';
ASC_Watchlist::register();
require_once __DIR__ . '/includes/class-asc-analysis.php';
ASC_Analysis::register();
require_once __DIR__ . '/includes/class-asc-danish-catalog.php';
ASC_Danish_Catalog::register();


register_activation_hook(__FILE__, 'asc_activate');
function asc_activate(): void {
    add_role('asc_sync_agent', 'AI Stock Scanner Sync Agent', [
        'read' => true, 'asc_sync' => true,
    ]);
    $role = get_role('asc_sync_agent');
    if ($role) { $role->add_cap('asc_sync'); }
    $admin = get_role('administrator');
    if ($admin) { $admin->add_cap('asc_sync'); }
    if (get_option(ASC_OPTION_SNAPSHOT, null) === null) {
        add_option(ASC_OPTION_SNAPSHOT, [], '', false);
    }
}

add_action('rest_api_init', 'asc_register_routes');
function asc_register_routes(): void {
    register_rest_route('ai-stock-scanner/v1', '/snapshot', [
        'methods'             => 'POST',
        'callback'            => 'asc_accept_snapshot',
        'permission_callback' => 'asc_snapshot_permission',
    ]);
    // Read-only authentication probe; allows testing without modifying scanner data.
    register_rest_route('ai-stock-scanner/v1', '/auth-check', [
        'methods'             => 'GET',
        'callback'            => static function () {
            return rest_ensure_response(['ok' => true, 'authenticated' => true]);
        },
        'permission_callback' => 'asc_snapshot_permission',
    ]);
}

/**
 * Scoped fallback for hosting providers that strip the standard Authorization header.
 * X-ASC-Authorization is accepted ONLY for our scanner routes (snapshot, auth-check,
 * tickers and playbook; all use this permission callback). It contains the
 * original WordPress Application Password as HTTP Basic's base64 representation,
 * validated by WordPress itself. It never appears in query strings or persisted data.
 *
 * The Python client enforces HTTPS and never follows redirects.
 */
function asc_snapshot_permission(WP_REST_Request $request) {
    if (current_user_can('asc_sync')) { return true; }

    // Never weaken WordPress Application Password HTTPS availability checks.
    if (!is_ssl() || !wp_is_application_passwords_available()) {
        return new WP_Error('asc_https_required',
            'WordPress skal registrere HTTPS før Application Passwords kan bruges.',
            ['status' => 401]);
    }

    $raw = trim((string)$request->get_header('x-asc-authorization'));
    if (strlen($raw) < 10 || strlen($raw) > 1024 ||
        preg_match('~^Basic ([A-Za-z0-9+/]+={0,2})$~D', $raw, $match) !== 1) {
        return new WP_Error('asc_auth_required',
            'Ingen gyldig godkendelse. Kontrollér Application Password og serverens headers.',
            ['status' => 401]);
    }
    $decoded = base64_decode($match[1], true);
    if (!is_string($decoded) || strlen($decoded) > 512 || !str_contains($decoded, ':')) {
        return new WP_Error('asc_auth_invalid', 'Ugyldig godkendelse.', ['status' => 401]);
    }
    [$username, $password] = explode(':', $decoded, 2);
    if ($username === '' || $password === '' || strlen($username) > 120 ||
        strlen($password) > 128) {
        return new WP_Error('asc_auth_invalid', 'Ugyldig godkendelse.', ['status' => 401]);
    }
    $user = wp_authenticate_application_password(null, $username, $password);
    if (!($user instanceof WP_User)) {
        // Do not reveal whether the user exists, or whether a password was wrong.
        return new WP_Error('asc_auth_failed',
            'WordPress kunne ikke godkende brugernavn og Application Password.',
            ['status' => 401]);
    }
    if (!user_can($user, 'asc_sync')) {
        return new WP_Error('asc_sync_forbidden',
            'Den godkendte bruger mangler asc_sync-rettigheden.',
            ['status' => 403]);
    }
    return true;
}

/**
 * Kald fra en lokal klient autentificeret med WordPress Application Password.
 * REST-ruten kan ikke køre kommandoer eller kalde Ollama.
 */
function asc_accept_snapshot(WP_REST_Request $request) {
    if (strlen($request->get_body()) > 65536) {
        return new WP_Error('asc_too_large', 'Payload er for stor.', ['status' => 413]);
    }
    $input = $request->get_json_params();
    if (!is_array($input) ||
        ($input['schema_version'] ?? null) !== 1 ||
        !in_array(($input['mode'] ?? null), ['demo', 'research'], true) ||
        !is_string($input['generated_at'] ?? null) ||
        !is_array($input['rows'] ?? null)
    ) {
        return new WP_Error('asc_invalid', 'Ugyldigt payload-format.', ['status' => 400]);
    }
    $generated = (string)$input['generated_at'];
    if (!preg_match('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/', $generated)) {
        return new WP_Error('asc_date', 'Tidspunkt skal være UTC ISO8601.', ['status' => 400]);
    }
    $epoch = strtotime($generated);
    if (!$epoch || $epoch > time() + 300 || $epoch < time() - 86400) {
        return new WP_Error('asc_time', 'Snapshot skal være nyere end 24 timer.', ['status' => 400]);
    }
    $current = get_option(ASC_OPTION_SNAPSHOT, []);
    if (is_array($current) && !empty($current['generated_at'])) {
        $previous = strtotime((string)$current['generated_at']);
        if ($previous !== false && $epoch <= $previous) {
            return new WP_Error('asc_replay', 'Snapshot er ikke nyere end den seneste.', ['status' => 409]);
        }
    }

    $items = $input['rows'];
    if (count($items) < 1 || count($items) > 50 || array_values($items) !== $items) {
        return new WP_Error('asc_count', 'Antallet skal være mellem 1 og 50.', ['status' => 400]);
    }
    $markets = ['Danmark', 'Tyskland', 'Sverige', 'Norge', 'USA', 'Frankrig', 'Holland', 'Spanien', 'Finland'];
    $signals = ['Interessant', 'Hold øje', 'Afvent'];
    $accepted = [];
    $seen = [];
    foreach ($items as $row) {
        if (!is_array($row) ||
            !is_string($row['ticker'] ?? null) ||
            !is_string($row['market'] ?? null) ||
            !is_string($row['market_date'] ?? null) ||
            !is_int($row['score'] ?? null) ||
            !is_string($row['signal'] ?? null)
        ) {
            return new WP_Error('asc_row', 'Ugyldigt aktieresultat.', ['status' => 400]);
        }
        $ticker = strtoupper(trim($row['ticker']));
        $market = $row['market'];
        $date = $row['market_date'];
        $score = $row['score'];
        $signal = $row['signal'];
        $instrument_type = $row['instrument_type'] ?? 'Ukendt';
        if (!preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/', $ticker) ||
            isset($seen[$ticker]) ||
            !in_array($market, $markets, true) ||
            !in_array($signal, $signals, true) ||
            !in_array($instrument_type, ['Aktie', 'ETF', 'Ukendt'], true) ||
            $score < 0 || $score > 100 ||
            !preg_match('/^\d{4}-\d\d-\d\d$/', $date)
        ) {
            return new WP_Error('asc_value', 'Resultatet indeholder ugyldige felter.', ['status' => 400]);
        }
        $dt = DateTimeImmutable::createFromFormat('!Y-m-d', $date);
        if (!$dt || $dt->format('Y-m-d') !== $date ||
            $dt->getTimestamp() > time() + 86400) {
            return new WP_Error('asc_market_date', 'Ugyldig markedsdato.', ['status' => 400]);
        }
        $seen[$ticker] = true;
        $accepted[] = [
            'ticker' => $ticker,
            'market' => $market,
            'instrument_type' => $instrument_type,
            'market_date' => $date,
            'score' => $score,
            'signal' => $signal,
        ];
    }
    $snapshot = [
        'schema_version' => 1,
        'generated_at' => $generated,
        'mode' => $input['mode'],
        'rows' => $accepted,
    ];
    update_option(ASC_OPTION_SNAPSHOT, $snapshot, false);
    return rest_ensure_response([
        'ok' => true,
        'count' => count($accepted),
        'generated_at' => $generated,
        'mode' => $input['mode'],
    ]);
}

add_action('wp_enqueue_scripts', static function (): void {
    wp_register_style(
        'hangar18-asc',
        plugins_url('assets/dashboard.css', __FILE__),
        [],
        ASC_PLUGIN_VERSION
    );
});

add_shortcode('ai_stock_scanner', 'asc_render_dashboard');
function asc_render_dashboard(): string {
    if (!is_user_logged_in()) {
        $url = wp_login_url(get_permalink());
        return '<p>Log ind for at se AI-Stock-Scanner. <a href="' .
            esc_url($url) . '">Log ind</a></p>';
    }
    wp_enqueue_style('hangar18-asc');
    $data = get_option(ASC_OPTION_SNAPSHOT, []);
    $rows = is_array($data) && isset($data['rows']) && is_array($data['rows'])
        ? $data['rows'] : [];
    // These filters are read-only and apply only to the snapshot rendered here.
    $requested_market = isset($_GET['asc_market']) && is_string($_GET['asc_market'])
        ? sanitize_text_field(wp_unslash($_GET['asc_market'])) : '';
    $requested_type = isset($_GET['asc_type']) && is_string($_GET['asc_type'])
        ? sanitize_text_field(wp_unslash($_GET['asc_type'])) : '';
    $requested_signal = isset($_GET['asc_signal']) && is_string($_GET['asc_signal'])
        ? sanitize_text_field(wp_unslash($_GET['asc_signal'])) : '';
    $requested_min = isset($_GET['asc_score_min']) && is_string($_GET['asc_score_min'])
        ? (int)$_GET['asc_score_min'] : 0;
    $requested_min = max(0, min(100, $requested_min));
    $markets = ['Danmark','Tyskland','Sverige','Norge','USA','Frankrig','Holland','Spanien','Finland'];
    if (!in_array($requested_market, $markets, true)) { $requested_market = ''; }
    if (!in_array($requested_type, ['Aktie','ETF','Ukendt'], true)) { $requested_type = ''; }
    if (!in_array($requested_signal, ['Interessant','Hold øje','Afvent'], true)) { $requested_signal = ''; }
    $all_count = count($rows);
    $rows = array_values(array_filter($rows, static function ($row) use ($requested_market, $requested_type, $requested_signal, $requested_min): bool {
        return is_array($row) &&
            ($requested_market === '' || ($row['market'] ?? '') === $requested_market) &&
            ($requested_type === '' || ($row['instrument_type'] ?? 'Ukendt') === $requested_type) &&
            ($requested_signal === '' || ($row['signal'] ?? '') === $requested_signal) &&
            (int)($row['score'] ?? -1) >= $requested_min;
    }));
    ob_start();
    echo '<section class="asc-dashboard" aria-label="AI-Stock-Scanner">';
    echo '<div class="asc-heading"><h2>AI Stock Scanner</h2><p>Aktier og ETF-instrumenter fra ni markeder</p></div>';
    echo '<form class="asc-filter-form" method="get">';
    if (isset($_GET['asc_view']) && $_GET['asc_view'] === 'scanner') {
        echo '<input type="hidden" name="asc_view" value="scanner">';
    }
    echo '<label>Marked<select name="asc_market"><option value="">Alle markeder</option>';
    foreach ($markets as $market) {
        echo '<option value="' . esc_attr($market) . '" '
            . selected($requested_market, $market, false) . '>' . esc_html($market) . '</option>';
    }
    echo '</select></label><label>Instrument<select name="asc_type"><option value="">Alle typer</option>';
    foreach (['Aktie','ETF','Ukendt'] as $type) {
        echo '<option value="' . esc_attr($type) . '" '
            . selected($requested_type, $type, false) . '>' . esc_html($type) . '</option>';
    }
    echo '</select></label><label>Signal<select name="asc_signal"><option value="">Alle signaler</option>';
    foreach (['Interessant','Hold øje','Afvent'] as $signal) {
        echo '<option value="' . esc_attr($signal) . '" '
            . selected($requested_signal, $signal, false) . '>' . esc_html($signal) . '</option>';
    }
    echo '</select></label><label>Minimumscore<input type="number" min="0" max="100" step="1" name="asc_score_min" value="'
        . esc_attr((string)$requested_min) . '"></label><button type="submit">Anvend filtre</button></form>';
    echo '<p class="asc-updated">Viser ' . esc_html((string)count($rows))
        . ' af ' . esc_html((string)$all_count) . ' modtagne værdipapirer.</p>';
    if (!$rows) {
        echo '<div class="asc-empty">'
            . ($all_count === 0 ? 'Ingen scanninger modtaget endnu. Installer den lokale scanner, og send først et demo-snapshot.'
                : 'Ingen resultater passer til filtrene. Prøv andre søgekriterier.')
            . '</div>';
    } else {
        $when = (string)($data['generated_at'] ?? '');
        $mode = (string)($data['mode'] ?? '');
        $demo = $mode === 'demo';
        $timestamp = strtotime($when);
        $stale = $timestamp === false || (time() - $timestamp) > 86400;
        echo '<div class="asc-metrics">';
        echo '<div><strong>' . esc_html((string)count($rows)) . '</strong><span>Værdipapirer</span></div>';
        echo '<div><strong>' . esc_html((string)count(array_unique(array_column($rows, 'market')))) . '</strong><span>Markeder</span></div>';
        echo '<div><strong>' . esc_html((string)count(array_filter($rows, static function ($r) {return ($r['score'] ?? 0) >= 80;}))) . '</strong><span>Score 80+</span></div>';
        echo '</div>';
        if ($demo) { echo '<p class="asc-warning">DEMODATA – ikke aktuelle aktiekurser eller investeringssignaler.</p>'; }
        if ($stale) { echo '<p class="asc-warning">Data er mere end 24 timer gamle. Den lokale PC/scanner er muligvis offline.</p>'; }
        echo '<p class="asc-updated">Seneste synkronisering (UTC): ' . esc_html($when) . '</p>';
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        echo '<th scope="col">Værdipapir</th><th scope="col">Type</th><th scope="col">Marked</th><th scope="col">Handelsdato</th>';
        echo '<th scope="col">Teknisk score</th><th scope="col">Signal</th></tr></thead><tbody>';
        foreach ($rows as $row) {
            $score = (int)$row['score'];
            $class = $score >= 80 ? 'asc-strong' : ($score >= 60 ? 'asc-watch' : 'asc-weak');
            echo '<tr><th scope="row">' . esc_html($row['ticker']) . '</th>';
            echo '<td>' . esc_html((string)($row['instrument_type'] ?? 'Ukendt')) . '</td>';
            echo '<td>' . esc_html($row['market']) . '</td>';
            echo '<td>' . esc_html($row['market_date']) . '</td>';
            echo '<td><span class="asc-score ' . esc_attr($class) . '">' .
                 esc_html((string)$score) . '/100</span></td>';
            echo '<td>' . esc_html($row['signal']) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }
    echo '<p class="asc-disclaimer">Tekniske researchsignaler er ikke køb/salg-anbefalinger. Score er ikke en sandsynlighed for afkast. Kursdata og AI-udtalelser skal vurderes selvstændigt.</p>';
    echo '</section>';
    return (string)ob_get_clean();
}

add_action('admin_menu', 'asc_register_admin_menu');
function asc_register_admin_menu(): void {
    // Synligt hovedmenupunkt i stedet for den tidligere placering under Værktøjer.
    add_menu_page(
        'AI Stock Scanner', 'AI Stock Scanner', 'manage_options',
        'asc-dashboard', 'asc_admin_page', 'dashicons-chart-area', 31
    );
    add_submenu_page(
        'asc-dashboard', 'Oversigt', 'Oversigt', 'manage_options',
        'asc-dashboard', 'asc_admin_page'
    );
    add_submenu_page(
        'asc-dashboard', 'Opdateringer', 'Opdateringer', 'update_plugins',
        'asc-updates', 'asc_admin_updates'
    );
    add_submenu_page(
        'asc-dashboard', 'Forbindelse', 'Forbindelse', 'manage_options',
        'asc-connection', 'asc_admin_connection'
    );
}
add_filter('plugin_action_links_' . plugin_basename(__FILE__), static function (array $links): array {
    if (current_user_can('update_plugins')) {
        array_unshift($links, '<a href="' . esc_url(admin_url('admin.php?page=asc-updates')) . '">Opdateringer</a>');
    }
    return $links;
});
function asc_admin_page(): void {
    if (!current_user_can('manage_options')) { return; }
    $data = get_option(ASC_OPTION_SNAPSHOT, []);
    $when = is_array($data) ? (string)($data['generated_at'] ?? 'Aldrig') : 'Aldrig';
    echo '<div class="wrap"><h1>AI Stock Scanner</h1>';
    echo '<p>Pluginversion: <strong>' . esc_html(ASC_PLUGIN_VERSION) . '</strong></p>';
    echo '<p>Seneste data modtaget (UTC): <strong>' . esc_html($when) . '</strong></p>';
    echo ASC_Playbook::admin_status_line();
    echo '<p>Startside: <strong>Personligt login, portefølje og watchlist</strong>. '
        . 'Du kan tilføje køb og manuel aktuel kurs, redigere beholdninger og eksportere egne køb som CSV – helt uden PC-scanneren.</p>';
    echo '<p>Med en aktiveret kurskilde kan du også se candlesticks, gennemsnitlig handelsvolumen og estimeret handelsværdi over 5/21 børsdage.</p>';
    echo '<p><strong>v0.6.0:</strong> Playbook: mandagsliste, screenere, aktie-scores og papirportefølje fra PC-appen, positionsstørrelse pr. bruger og salgsregel i porteføljen.</p>';
    echo '<p><strong>v0.5.2:</strong> Fast venstremenu ved scroll og sikker sammenligning med dateret børsaktieliste (CSV). Manglende aktier markeres til kontrol, aldrig slettes.</p>';
    echo '<p><strong>v0.5.1:</strong> Søg i danske aktier med katalog, navn, ticker, sektor og ISIN via CSV-import. Følg aktier eller registrér køb fra resultatlisten.</p>';
    echo '<p><strong>v0.5.0:</strong> Ny venstremenu, ni markeder, ETF-understøttelse, scannerfiltre og scenarioanalyse.</p>';
    echo '<p><strong>v0.4.4:</strong> Angiv betalt i alt i DKK pr. køb. '
        . 'Visning af investeret, aktuel værdi og gevinst/tab i DKK, '
        . 'med ECB-valutakurs og tydelige skøn ved manglende valutakurser.</p>';
    echo '<p><strong>v0.4.1:</strong> Mere præcise fejlbeskeder ved køb, tæller for faktisk gemte køb og højst ét hurtigt Yahoo-kursopslag pr. sideindlæsning. '
        . 'De eksisterende aktiekøb bevares ved opdatering.</p>';
    echo '<p>For at gøre porteføljen til websitets startside: klik nedenfor. Dette erstatter den nuværende forside, men sletter ikke indhold.</p>';
    echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
    echo '<input type="hidden" name="action" value="asc_create_home">';
    wp_nonce_field('asc_create_home');
    submit_button('Opret porteføljeside og sæt som forside', 'primary', 'submit', false);
    echo '</form>';
    if (isset($_GET['asc_home']) && $_GET['asc_home'] === 'created') {
        echo '<div class="notice notice-success"><p>Startsiden er oprettet/aktiveret.</p></div>';
    }
    echo '<p>Alternativt: Opret en WordPress-side med <code>[ai_stock_home]</code>, <code>[ai_stock_portfolio]</code> eller <code>[ai_stock_watchlist]</code> eller <code>[ai_stock_playbook]</code> (mandagsliste og screenere).</p>';
    echo '<p>Scanner-dashboardet findes fortsat via <code>[ai_stock_scanner]</code>. Kun indloggede brugere ser aktiedata.</p>';
    echo '<p>Python-scanneren og Ollama kører lokalt på din computer; hjemmesiden viser kun de senest modtagne data.</p>';
    echo '<p><a class="button button-primary" href="' . esc_url(admin_url('admin.php?page=asc-updates')) . '">GitHub-opdateringer</a> ';
    echo '<a class="button" href="' . esc_url(admin_url('admin.php?page=asc-connection')) . '">Forbindelse til PC</a></p>';
    echo '</div>';
}
function asc_admin_updates(): void {
    if (!current_user_can('update_plugins')) { wp_die('Ingen adgang.'); }
    echo '<div class="wrap"><h1>AI Stock Scanner – Opdateringer</h1>';
    ASC_GitHub_Updater::render_panel();
    echo '</div>';
}
function asc_admin_connection(): void {
    if (!current_user_can('manage_options')) { wp_die('Ingen adgang.'); }
    $snapshot = get_option(ASC_OPTION_SNAPSHOT, []);
    $when = is_array($snapshot) ? (string)($snapshot['generated_at'] ?? 'Aldrig') : 'Aldrig';
    echo '<div class="wrap"><h1>AI Stock Scanner – Forbindelse</h1>';
    echo '<p>Seneste data modtaget (UTC): <strong>' . esc_html($when) . '</strong></p>';
    echo '<p>Opret en særskilt WordPress-bruger med rollen <strong>AI Stock Scanner Sync Agent</strong>,';
    echo ' og opret et Application Password på denne brugers profil. Brug aldrig en administrator-konto til synkronisering.</p>';
    echo '<p>REST endpoint: <code>' . esc_html(rest_url('ai-stock-scanner/v1/snapshot')) . '</code></p>';
    echo '<p>PC\'ens Python-scanner sender data over HTTPS. Ingen lokal Ollama-port skal åbnes mod internettet.</p>';
    echo '<p>Hvis hosting fjerner HTTP Authorization-headeren, bruger scanneren automatisk en ekstra header, som kontrolleres mod WordPress Application Passwords. Ingen ændring af .htaccess er nødvendig.</p>';
    ASC_Market_Quotes::render_settings();
    ASC_HTTPS_Proxy::render_panel();
    echo '<p>Se installationsvejledningen i projektets GitHub-repository.</p>';
    echo '</div>';
}

require_once __DIR__ . '/includes/class-asc-github-updater.php';
ASC_GitHub_Updater::register();
