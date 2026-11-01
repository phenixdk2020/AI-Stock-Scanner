<?php
/**
 * Plugin Name: Hangar18 AI Stock Scanner
 * Description: Loginbeskyttet dashboard til validerede forskningsresultater fra lokal Python-scanner.
 * Version: 0.2.0
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
define('ASC_PLUGIN_VERSION', '0.2.0');
define('ASC_OPTION_SNAPSHOT', 'asc_latest_snapshot_v1');

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
        'permission_callback' => static function (): bool {
            return current_user_can('asc_sync');
        },
    ]);
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
    if (count($items) < 1 || count($items) > 25 || array_values($items) !== $items) {
        return new WP_Error('asc_count', 'Antallet skal være mellem 1 og 25.', ['status' => 400]);
    }
    $markets = ['Danmark', 'Tyskland', 'Sverige', 'Norge', 'USA'];
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
        if (!preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/', $ticker) ||
            isset($seen[$ticker]) ||
            !in_array($market, $markets, true) ||
            !in_array($signal, $signals, true) ||
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
    ob_start();
    echo '<section class="asc-dashboard" aria-label="AI-Stock-Scanner">';
    echo '<div class="asc-heading"><h2>AI Stock Scanner</h2><p>Research for Danmark, Tyskland, Sverige, Norge og USA</p></div>';
    if (!$rows) {
        echo '<div class="asc-empty">Ingen scanninger modtaget endnu. Installer den lokale scanner, og send først et demo-snapshot.</div>';
    } else {
        $when = (string)($data['generated_at'] ?? '');
        $mode = (string)($data['mode'] ?? '');
        $demo = $mode === 'demo';
        $timestamp = strtotime($when);
        $stale = $timestamp === false || (time() - $timestamp) > 86400;
        echo '<div class="asc-metrics">';
        echo '<div><strong>' . esc_html((string)count($rows)) . '</strong><span>Aktier</span></div>';
        echo '<div><strong>' . esc_html((string)count(array_unique(array_column($rows, 'market')))) . '</strong><span>Markeder</span></div>';
        echo '<div><strong>' . esc_html((string)count(array_filter($rows, static function ($r) {return ($r['score'] ?? 0) >= 80;}))) . '</strong><span>Score 80+</span></div>';
        echo '</div>';
        if ($demo) { echo '<p class="asc-warning">DEMODATA – ikke aktuelle aktiekurser eller investeringssignaler.</p>'; }
        if ($stale) { echo '<p class="asc-warning">Data er mere end 24 timer gamle. Den lokale PC/scanner er muligvis offline.</p>'; }
        echo '<p class="asc-updated">Seneste synkronisering (UTC): ' . esc_html($when) . '</p>';
        echo '<div class="asc-table-wrap"><table><thead><tr>';
        echo '<th scope="col">Aktie</th><th scope="col">Marked</th><th scope="col">Handelsdato</th>';
        echo '<th scope="col">Teknisk score</th><th scope="col">Signal</th></tr></thead><tbody>';
        foreach ($rows as $row) {
            $score = (int)$row['score'];
            $class = $score >= 80 ? 'asc-strong' : ($score >= 60 ? 'asc-watch' : 'asc-weak');
            echo '<tr><th scope="row">' . esc_html($row['ticker']) . '</th>';
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

add_action('admin_menu', static function (): void {
    add_management_page(
        'AI Stock Scanner', 'AI Stock Scanner', 'manage_options',
        'hangar18-ai-stock-scanner', 'asc_admin_page'
    );
});
function asc_admin_page(): void {
    if (!current_user_can('manage_options')) { return; }
    $data = get_option(ASC_OPTION_SNAPSHOT, []);
    $when = is_array($data) ? (string)($data['generated_at'] ?? 'Aldrig') : 'Aldrig';
    echo '<div class="wrap"><h1>AI Stock Scanner</h1>';
    echo '<p>Pluginversion: <strong>' . esc_html(ASC_PLUGIN_VERSION) . '</strong></p>';
    echo '<p>Seneste data modtaget (UTC): <strong>' . esc_html($when) . '</strong></p>';
    echo '<p>Opret en WordPress-bruger med rollen <strong>AI Stock Scanner Sync Agent</strong>,';
    echo ' og opret et separat Application Password på brugerens profil.</p>';
    echo '<p>Dette er forbindelsesrollen, ikke en rolle til normale webbrugere.</p>';
    echo '<p>REST endpoint: <code>' . esc_html(rest_url('ai-stock-scanner/v1/snapshot')) . '</code></p>';
    echo '<p>Opret en side med shortcoden <code>[ai_stock_scanner]</code>.';
    echo ' Kun indloggede brugere kan se resultaterne.</p>';
    echo '<p>Python/Ollama kører på din PC; pluginet kører ikke Python eller Ollama på webhotellet.</p>';
    echo '<p>GitHub-opdatering bruger en læsebegrænset token i wp-config.php. Pluginet genaktiveres efter en normal opdatering, hvis det var aktivt før.</p>';
    ASC_GitHub_Updater::render_panel();
    echo '</div>';
}

require_once __DIR__ . '/includes/class-asc-github-updater.php';
ASC_GitHub_Updater::register();
