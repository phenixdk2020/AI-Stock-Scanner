<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * WordPress HTTPS diagnostic and *opt-in* trusted reverse proxy support.
 *
 * Never enable Application Passwords on plain HTTP using a WordPress filter.
 * A proxy must replace X-Forwarded-Proto, and its REMOTE_ADDR must be trusted.
 */
final class ASC_HTTPS_Proxy {
    private const OPTION = 'asc_trusted_https_proxy_ip';
    private static bool $adjusted = false;

    public static function bootstrap(): void {
        add_action('admin_post_asc_https_proxy_save', [self::class, 'save_proxy']);
        if (is_ssl()) { return; }
        if (!self::https_forwarded() || !self::expected_host()) { return; }
        $remote_ip = self::remote_ip();
        if ($remote_ip === '') { return; }
        $stored = (string)get_option(self::OPTION, '');
        $configured = defined('ASC_TRUSTED_PROXY_IPS') ? ASC_TRUSTED_PROXY_IPS : [];
        if (is_string($configured)) {
            $configured = array_map('trim', explode(',', $configured));
        }
        if (!is_array($configured)) { $configured = []; }
        // Loopback reverse proxy can be trusted without a configuration step.
        $trusted = in_array($remote_ip, ['127.0.0.1', '::1'], true)
            || ($stored !== '' && hash_equals($stored, $remote_ip))
            || in_array($remote_ip, $configured, true);
        if ($trusted) {
            $_SERVER['HTTPS'] = 'on';
            self::$adjusted = true;
        }
    }

    private static function remote_ip(): string {
        $ip = (string)($_SERVER['REMOTE_ADDR'] ?? '');
        return filter_var($ip, FILTER_VALIDATE_IP) !== false ? $ip : '';
    }

    /** Require a single, unambiguous value; refuse untrusted forwarded chains. */
    private static function https_forwarded(): bool {
        return strtolower(trim((string)($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? ''))) === 'https';
    }

    /** Never rely on a forwarded Host header. Match HTTP_HOST to canonical site. */
    private static function expected_host(): bool {
        $canonical = wp_parse_url(home_url('/'), PHP_URL_HOST);
        $requested = wp_parse_url('http://' . (string)($_SERVER['HTTP_HOST'] ?? ''), PHP_URL_HOST);
        return is_string($canonical) && is_string($requested)
            && $canonical !== '' && strcasecmp($canonical, $requested) === 0;
    }

    public static function save_proxy(): void {
        if (!current_user_can('manage_options')) { wp_die('Ingen adgang.'); }
        check_admin_referer('asc_https_proxy_save');
        $raw = isset($_POST['asc_proxy_ip']) && is_string($_POST['asc_proxy_ip'])
            ? sanitize_text_field(wp_unslash($_POST['asc_proxy_ip'])) : '';
        $ip = trim($raw);
        if ($ip !== '' && filter_var($ip, FILTER_VALIDATE_IP) === false) {
            self::redirect('invalid');
        }
        // An empty field disables the explicit proxy trust.
        update_option(self::OPTION, $ip, false);
        self::redirect($ip === '' ? 'cleared' : 'saved');
    }

    private static function redirect(string $status): void {
        wp_safe_redirect(add_query_arg('asc_https', $status, admin_url('admin.php?page=asc-connection')));
        exit;
    }

    public static function render_panel(): void {
        if (!current_user_can('manage_options')) { return; }
        $status = sanitize_key((string)($_GET['asc_https'] ?? ''));
        echo '<hr><h2>HTTPS / Application Passwords</h2>';
        if ($status === 'saved') {
            echo '<div class="notice notice-success"><p>Proxy-IP er gemt. Åbn siden igen for at kontrollere HTTPS-status.</p></div>';
        } elseif ($status === 'cleared') {
            echo '<div class="notice notice-info"><p>Eksplicit tillid til proxy-IP er fjernet.</p></div>';
        } elseif ($status === 'invalid') {
            echo '<div class="notice notice-error"><p>Angiv en gyldig IPv4- eller IPv6-adresse.</p></div>';
        }
        $ssl = is_ssl();
        $apps = function_exists('wp_is_application_passwords_available')
            ? wp_is_application_passwords_available() : false;
        $trusted = (string)get_option(self::OPTION, '');
        $remote = self::remote_ip();
        $proto = (string)($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '');
        $https = (string)($_SERVER['HTTPS'] ?? '(ikke sat)');
        $port = (string)($_SERVER['SERVER_PORT'] ?? '(ukendt)');
        echo '<table class="widefat striped" style="max-width:780px"><tbody>';
        $rows = [
            'WordPress ser HTTPS' => $ssl ? 'Ja' : 'Nej',
            'Application Passwords tilgængelige' => $apps ? 'Ja' : 'Nej',
            'WP_HOME' => home_url('/'),
            'WP_SITEURL' => site_url('/'),
            'HTTPS-servervariabel' => $https,
            'SERVER_PORT' => $port,
            'X-Forwarded-Proto' => $proto !== '' ? $proto : '(ikke sendt)',
            'REMOTE_ADDR (forbindelse til PHP)' => $remote !== '' ? $remote : '(ukendt)',
            'Eksplicit betroet proxy' => $trusted !== '' ? $trusted : '(ingen)',
            'HTTPS registreret via plugin' => self::$adjusted ? 'Ja (betroet proxy)' : 'Nej',
        ];
        foreach ($rows as $label => $value) {
            echo '<tr><th scope="row">' . esc_html($label) . '</th><td><code>'
                . esc_html((string)$value) . '</code></td></tr>';
        }
        echo '</tbody></table>';

        if ($ssl && $apps) {
            echo '<p><strong>WordPress registrerer HTTPS.</strong> Opret nu Application Password på den tekniske brugers profil.</p>';
        } elseif ($ssl) {
            echo '<p><strong>HTTPS er registreret, men Application Passwords er deaktiveret.</strong> Kontrollér sikkerhedsplugins og WordPress-filtre.</p>';
        } else {
            echo '<p><strong>WordPress registrerer ikke HTTPS.</strong> Kontrollér først at browseren bruger et gyldigt HTTPS-certifikat og at WordPress-adresserne starter med https://.</p>';
        }

        echo '<h3>Betroet reverse proxy (kun ved behov)</h3>';
        echo '<p>Hvis dit webhotel håndterer TLS i en reverse proxy, kan du her angive den IP, som PHP faktisk ser i REMOTE_ADDR.</p>';
        echo '<p><strong>Sikkerhed:</strong> Brug kun denne mulighed, hvis proxyen selv fjerner klienters X-Forwarded-Proto og sætter den til den korrekte protokol. Ellers skal fejlen rettes på webserveren. Funktionen slår <em>ikke</em> HTTPS-kravet fra.</p>';
        echo '<p>Hvis X-Forwarded-Proto mangler eller ikke er præcis <code>https</code>, vil denne indstilling ikke hjælpe: webhotellet skal sende headeren korrekt.</p>';
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_https_proxy_save">';
        wp_nonce_field('asc_https_proxy_save');
        echo '<p><label for="asc-proxy-ip">Betroet proxy-IP (blank = deaktiveret)</label></p>';
        echo '<p><input id="asc-proxy-ip" class="regular-text" name="asc_proxy_ip" type="text" value="'
            . esc_attr($trusted) . '" placeholder="f.eks. 127.0.0.1" autocomplete="off"></p>';
        submit_button('Gem betroet proxy-IP', 'secondary', 'submit', false);
        echo '</form>';
        echo '<p class="description">Du kan alternativt sætte <code>ASC_TRUSTED_PROXY_IPS</code> i wp-config.php til en liste med verificerede proxy-IP-adresser. Ændringer her påvirker kun denne WordPress-installation.</p>';
    }
}
