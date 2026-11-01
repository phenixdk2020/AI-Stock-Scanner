<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * GitHub-opdatering til privat repository – ingen token i browser eller URL.
 * Token indstilles KUN i wp-config.php: define('ASC_GITHUB_TOKEN', 'github_pat_...');
 * Kræver GitHub fine-grained Contents: Read-only for dette ene repository.
 */
final class ASC_GitHub_Updater {
    public const PLUGIN = 'hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php';
    private const SLUG = 'hangar18-ai-stock-scanner';
    private const REPO = 'https://github.com/phenixdk2020/AI-Stock-Scanner';
    private const API = 'https://api.github.com/repos/phenixdk2020/AI-Stock-Scanner/contents/';
    private const CACHE = 'asc_github_manifest_v2';
    private static bool $was_active = false;
    private static bool $was_network_active = false;
    private static string $last_error = '';

    public static function register(): void {
        add_filter('update_plugins_github.com', [self::class, 'update_uri'], 10, 4);
        add_filter('pre_set_site_transient_update_plugins', [self::class, 'updates'], 20);
        add_filter('plugins_api', [self::class, 'plugin_info'], 20, 3);
        add_filter('upgrader_pre_download', [self::class, 'download'], 20, 4);
        // WordPress's Plugin_Upgrader deactivates on upgrader_pre_install priority 10.
        add_filter('upgrader_pre_install', [self::class, 'remember_activation'], 4, 2);
        add_filter('upgrader_post_install', [self::class, 'reactivate'], 20, 2);
        add_action('upgrader_process_complete', [self::class, 'clear_cache'], 20, 2);
        add_action('admin_post_asc_github_check', [self::class, 'check_now']);
        add_action('admin_post_asc_github_install', [self::class, 'install_now']);
    }

    public static function configured(): bool {
        return defined('ASC_GITHUB_TOKEN')
            && is_string(ASC_GITHUB_TOKEN)
            && strlen(trim(ASC_GITHUB_TOKEN)) >= 20;
    }
    private static function error(string $message): void {
        self::$last_error = $message;
        set_transient('asc_github_update_error_' . get_current_user_id(), $message, 15 * MINUTE_IN_SECONDS);
    }
    public static function last_error(): string {
        return self::$last_error;
    }
    public static function clear_cache($upgrader = null, $extra = null): void {
        delete_site_transient(self::CACHE);
    }

    /** GitHub contents API returns base64 data; no public/raw URL or redirect needed. */
    private static function github_file(string $path, int $max_bytes) {
        if (!self::configured()) {
            return new WP_Error('asc_token', 'GitHub-token mangler i wp-config.php.');
        }
        if (!preg_match('~^(?:update\\.json|dist/hangar18-ai-stock-scanner-v[0-9]+\\.[0-9]+\\.[0-9]+\\.zip)$~D', $path)) {
            return new WP_Error('asc_untrusted_path', 'Uventet GitHub-filnavn.');
        }
        $response = wp_safe_remote_get(self::API . $path . '?ref=main', [
            'timeout' => 25,
            'redirection' => 0,
            'limit_response_size' => (int)($max_bytes * 1.5) + 8192,
            'headers' => [
                'Accept' => 'application/vnd.github+json',
                'Authorization' => 'Bearer ' . trim(ASC_GITHUB_TOKEN),
                'X-GitHub-Api-Version' => '2022-11-28',
                'User-Agent' => 'Hangar18-AI-Stock-Scanner/' . ASC_PLUGIN_VERSION,
            ],
        ]);
        if (is_wp_error($response)) { return $response; }
        if ((int)wp_remote_retrieve_response_code($response) !== 200) {
            return new WP_Error('asc_github_http', 'GitHub kan ikke læse filen (HTTP '
                . (int)wp_remote_retrieve_response_code($response) . '). Kontrollér token/repository.');
        }
        $body = json_decode((string)wp_remote_retrieve_body($response), true);
        if (!is_array($body) || ($body['type'] ?? '') !== 'file'
            || ($body['encoding'] ?? '') !== 'base64'
            || !is_string($body['content'] ?? null)
            || (int)($body['size'] ?? -1) > $max_bytes) {
            return new WP_Error('asc_github_content', 'GitHub returnerede ikke gyldigt filindhold.');
        }
        $decoded = base64_decode($body['content'], true);
        if (!is_string($decoded) || strlen($decoded) > $max_bytes) {
            return new WP_Error('asc_github_decode', 'GitHub-filen kunne ikke afkodes.');
        }
        return $decoded;
    }
    private static function valid_manifest($m): bool {
        if (!is_array($m)) { return false; }
        $v = (string)($m['version'] ?? '');
        return ($m['slug'] ?? '') === self::SLUG
            && preg_match('/^\\d+\\.\\d+\\.\\d+$/D', $v) === 1
            && preg_match('/^[a-f0-9]{64}$/D', (string)($m['sha256'] ?? '')) === 1
            && ($m['package_path'] ?? '') === 'dist/' . self::SLUG . '-v' . $v . '.zip';
    }
    public static function manifest(bool $refresh = false): ?array {
        if (!self::configured()) { return null; }
        if (!$refresh) {
            $cached = get_site_transient(self::CACHE);
            if (self::valid_manifest($cached)) { return $cached; }
        }
        $raw = self::github_file('update.json', 16384);
        if (is_wp_error($raw)) { self::error($raw->get_error_message()); return null; }
        $manifest = json_decode($raw, true);
        if (!self::valid_manifest($manifest)) {
            self::error('Ugyldigt versioneret update.json på GitHub.');
            return null;
        }
        set_site_transient(self::CACHE, $manifest, 10 * MINUTE_IN_SECONDS);
        return $manifest;
    }
    private static function package_url(array $m): string {
        return self::API . $m['package_path'] . '?ref=main';
    }
    private static function update_object(array $m): stdClass {
        $obj = new stdClass();
        $obj->id = self::REPO;
        $obj->slug = self::SLUG;
        $obj->plugin = self::PLUGIN;
        $obj->new_version = $m['version'];
        $obj->url = self::REPO;
        $obj->package = self::package_url($m);
        $obj->requires = '6.4';
        $obj->requires_php = '8.0';
        return $obj;
    }
    public static function update_uri($update, array $plugin_data, string $plugin_file, array $locales) {
        if ($plugin_file !== self::PLUGIN) { return $update; }
        $m = self::manifest();
        if (!$m) { return $update; }
        return [
            'id' => self::REPO, 'slug' => self::SLUG,
            'version' => $m['version'], 'url' => self::REPO,
            'package' => self::package_url($m),
            'requires_php' => '8.0', 'autoupdate' => false,
        ];
    }
    public static function updates($transient) {
        if (!is_object($transient) || !is_array($transient->checked ?? null)) { return $transient; }
        $m = self::manifest();
        if (!$m) { return $transient; }
        $info = self::update_object($m);
        if (version_compare($m['version'], ASC_PLUGIN_VERSION, '>')) {
            $transient->response[self::PLUGIN] = $info;
            unset($transient->no_update[self::PLUGIN]);
        } else {
            $transient->no_update[self::PLUGIN] = $info;
            unset($transient->response[self::PLUGIN]);
        }
        return $transient;
    }
    public static function plugin_info($result, string $action, $args) {
        if ($action !== 'plugin_information' || !is_object($args)
            || ($args->slug ?? '') !== self::SLUG) { return $result; }
        $m = self::manifest();
        if (!$m) { return $result; }
        $info = new stdClass();
        $info->name = 'Hangar18 AI Stock Scanner';
        $info->slug = self::SLUG;
        $info->version = $m['version'];
        $info->author = 'Hangar18';
        $info->homepage = self::REPO;
        $info->requires = '6.4';
        $info->requires_php = '8.0';
        $info->download_link = self::package_url($m);
        $info->sections = ['description' => 'Loginbeskyttet aktiescanner med lokal Ollama.',
            'changelog' => 'Version ' . esc_html($m['version'])];
        return $info;
    }
    private static function our_upgrade(array $extra): bool {
        if (($extra['type'] ?? '') !== 'plugin' || ($extra['action'] ?? '') !== 'update') {
            return false;
        }
        $plugins = is_array($extra['plugins'] ?? null) ? $extra['plugins'] : [];
        return ($extra['plugin'] ?? '') === self::PLUGIN || in_array(self::PLUGIN, $plugins, true);
    }

    /** Only intercept this plugin; never interfere with other WordPress updates. */
    public static function download($reply, string $package, $upgrader, array $extra = []) {
        if ($reply !== false || !self::our_upgrade($extra)) { return $reply; }
        $m = self::manifest(true);
        if (!$m || !hash_equals(self::package_url($m), $package)) {
            return new WP_Error('asc_untrusted_zip', 'Ukendt GitHub-installationspakke.');
        }
        $zip_bytes = self::github_file($m['package_path'], 2097152);
        if (is_wp_error($zip_bytes)) { return $zip_bytes; }
        $digest = hash('sha256', $zip_bytes);
        if (!hash_equals((string)$m['sha256'], $digest)) {
            return new WP_Error('asc_bad_digest', 'GitHub ZIP SHA-256 matcher ikke manifestet.');
        }
        if (!class_exists('ZipArchive')) {
            return new WP_Error('asc_zip_missing', 'PHP ZipArchive er påkrævet for sikker opdatering.');
        }
        $tmp = tempnam(get_temp_dir(), 'asc-wp-');
        if (!$tmp || file_put_contents($tmp, $zip_bytes) !== strlen($zip_bytes)) {
            if ($tmp) { @unlink($tmp); }
            return new WP_Error('asc_tmp', 'Kan ikke skrive midlertidig opdateringsfil.');
        }
        $zip = new ZipArchive();
        if ($zip->open($tmp) !== true) {
            @unlink($tmp);
            return new WP_Error('asc_zip_invalid', 'Opdateringspakken er ikke en gyldig ZIP.');
        }
        $main = $zip->getFromName(self::PLUGIN);
        $valid = is_string($main)
            && preg_match('/^\\s*\\* Version:\\s*' . preg_quote($m['version'], '/') . '\\s*$/m', $main) === 1
            && str_contains($main, 'Plugin Name: Hangar18 AI Stock Scanner')
            && $zip->numFiles <= 250;
        $seen = [];
        for ($i = 0; $i < $zip->numFiles && $valid; $i++) {
            $name = $zip->getNameIndex($i);
            $parts = explode('/', (string)$name);
            $key = strtolower((string)$name);
            if (isset($seen[$key]) || !str_starts_with((string)$name, self::SLUG . '/')
                || str_contains((string)$name, '\\')
                || in_array('..', $parts, true)) { $valid = false; }
            $seen[$key] = true;
        }
        $zip->close();
        if (!$valid) {
            @unlink($tmp);
            return new WP_Error('asc_zip_identity', 'ZIP-indhold, version eller mappestruktur er forkert.');
        }
        return $tmp;
    }

    /** Called before WordPress Plugin_Upgrader::deactivate_plugin_before_upgrade. */
    public static function remember_activation($result, array $extra = []) {
        if (is_wp_error($result) || !self::our_upgrade($extra)) { return $result; }
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
        self::$was_active = is_plugin_active(self::PLUGIN);
        self::$was_network_active = is_plugin_active_for_network(self::PLUGIN);
        return $result;
    }
    public static function restore_activation(bool $was_active, bool $was_network) {
        if (!$was_active && !$was_network) { return true; }
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
        if ($was_network ? is_plugin_active_for_network(self::PLUGIN) : is_plugin_active(self::PLUGIN)) {
            return true;
        }
        if (!is_file(WP_PLUGIN_DIR . '/' . self::PLUGIN)) {
            return new WP_Error('asc_missing', 'Pluginfilen mangler efter opdatering.');
        }
        $answer = activate_plugin(self::PLUGIN, '', $was_network, true);
        if (is_wp_error($answer)) { return $answer; }
        if ($was_network ? !is_plugin_active_for_network(self::PLUGIN) : !is_plugin_active(self::PLUGIN)) {
            return new WP_Error('asc_inactive', 'Pluginet blev ikke genaktiveret.');
        }
        return true;
    }
    public static function reactivate($result, array $extra = []) {
        if (is_wp_error($result) || !self::our_upgrade($extra)) { return $result; }
        $restored = self::restore_activation(self::$was_active, self::$was_network_active);
        if (is_wp_error($restored)) {
            self::error($restored->get_error_message());
            return $restored;
        }
        return $result;
    }

    private static function redirect(string $state): void {
        wp_safe_redirect(add_query_arg('asc_update', $state,
            admin_url('tools.php?page=hangar18-ai-stock-scanner')));
        exit;
    }
    public static function check_now(): void {
        if (!current_user_can('update_plugins')) { wp_die('Ingen adgang.'); }
        check_admin_referer('asc_github_check');
        self::clear_cache();
        $m = self::manifest(true);
        self::redirect(!$m ? 'error' :
            (version_compare($m['version'], ASC_PLUGIN_VERSION, '>') ? 'available' : 'current'));
    }
    public static function install_now(): void {
        if (!current_user_can('update_plugins')) { wp_die('Ingen adgang.'); }
        check_admin_referer('asc_github_install');
        $m = self::manifest(true);
        if (!$m) { self::redirect('error'); }
        if (version_compare($m['version'], ASC_PLUGIN_VERSION, '<=')) {
            self::redirect('current');
        }
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
        require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
        require_once ABSPATH . 'wp-admin/includes/update.php';
        $before_active = is_plugin_active(self::PLUGIN);
        $before_network = is_plugin_active_for_network(self::PLUGIN);

        // Set the exact validated version into WordPress's native upgrader.
        $checked = get_site_transient('update_plugins');
        if (!is_object($checked)) { $checked = new stdClass(); }
        if (!is_array($checked->checked ?? null)) { $checked->checked = []; }
        if (!is_array($checked->response ?? null)) { $checked->response = []; }
        $checked->checked[self::PLUGIN] = ASC_PLUGIN_VERSION;
        $checked->response[self::PLUGIN] = self::update_object($m);
        if (is_array($checked->no_update ?? null)) { unset($checked->no_update[self::PLUGIN]); }
        set_site_transient('update_plugins', $checked);

        $upgrader = new Plugin_Upgrader(new Automatic_Upgrader_Skin());
        $installed = $upgrader->upgrade(self::PLUGIN);
        // Fallback in case another updater did not honor the activation hook.
        $restored = self::restore_activation($before_active, $before_network);
        if (is_wp_error($restored)) {
            self::error($restored->get_error_message());
            // Plugin menu may be unavailable, so show Plugins page instead.
            wp_safe_redirect(admin_url('plugins.php'));
            exit;
        }
        if ($installed !== true) {
            self::error(is_wp_error($installed) ? $installed->get_error_message()
                : 'Plugin_Upgrader kunne ikke installere opdateringen.');
            self::redirect('error');
        }
        self::clear_cache();
        self::redirect('installed');
    }

    public static function render_panel(): void {
        if (!current_user_can('update_plugins')) { return; }
        $m = self::manifest();
        $has_update = $m && version_compare($m['version'], ASC_PLUGIN_VERSION, '>');
        $result = sanitize_key((string)($_GET['asc_update'] ?? ''));
        $labels = [
            'installed' => 'Opdateringen blev installeret – aktiveringstilstand gendannet.',
            'available' => 'Der er en nyere GitHub-version.',
            'current' => 'Du har den nyeste version.',
            'error' => 'GitHub-opdateringen mislykkedes. Se status og kontrollér token/rettigheder.',
        ];
        echo '<hr><h2>GitHub – Opdater plugin</h2>';
        if (isset($labels[$result])) {
            echo '<div class="notice ' . esc_attr($result === 'error' ? 'notice-error' : 'notice-success')
                . '"><p>' . esc_html($labels[$result]) . '</p></div>';
        }
        echo '<p>Installeret version: <strong>' . esc_html(ASC_PLUGIN_VERSION) . '</strong></p>';
        if (!self::configured()) {
            echo '<p><strong>GitHub-token mangler.</strong> Tilføj <code>define(\'ASC_GITHUB_TOKEN\', \'github_pat_...\');</code> i wp-config.php.';
            echo ' Vælg kun dette private repository og Contents: Read-only.</p>';
        } elseif ($m) {
            echo '<p>Seneste GitHub-version: <strong>' . esc_html($m['version']) . '</strong> – '
                . ($has_update ? 'ny version tilgængelig' : 'opdateret') . '</p>';
        } else {
            echo '<p>GitHub-manifestet kunne ikke læses. Kontrollér token og update.json.</p>';
        }
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_github_check">';
        wp_nonce_field('asc_github_check');
        submit_button('Tjek GitHub-opdatering', 'secondary', 'submit', false);
        echo '</form>';
        if ($has_update) {
            echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" style="margin-top:12px">';
            echo '<input type="hidden" name="action" value="asc_github_install">';
            wp_nonce_field('asc_github_install');
            submit_button('Backup og opdater plugin', 'primary', 'submit', false);
            echo '<p class="description">WordPress 6.4+ tager midlertidig kodebackup ved opdatering. Pluginet genaktiveres automatisk, hvis det var aktivt før opdatering. Eksisterende scannerdata gemmes i databasen.</p>';
            echo '</form>';
        }
        $error = get_transient('asc_github_update_error_' . get_current_user_id());
        if (is_string($error) && $error !== '') {
            echo '<p><strong>Seneste fejl:</strong> ' . esc_html($error) . '</p>';
        }
        echo '<p class="description">Kun administratorer kan opdatere. GitHub-token læses server-side og sendes ikke til browseren. Ingen automatisk cron-opdatering i denne version.</p>';
    }
}
