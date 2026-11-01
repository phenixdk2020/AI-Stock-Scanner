<?php
declare(strict_types=1);
/**
 * Offline PHP-regressionstest: updateren skal genskabe aktiveringsstatus.
 * Kør: php tests/wp_updater_reactivation.php
 */
$root = sys_get_temp_dir() . '/asc-updater-tests-' . getmypid();
@mkdir($root . '/wp-admin/includes', 0700, true);
@mkdir($root . '/plugins/hangar18-ai-stock-scanner', 0700, true);
file_put_contents($root . '/wp-admin/includes/plugin.php', '<?php // WordPress mock');
file_put_contents($root . '/plugins/hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php', '<?php // Mock plugin');
define('ABSPATH', $root . '/');
define('WP_PLUGIN_DIR', $root . '/plugins');
define('ASC_PLUGIN_VERSION', '0.2.0');
define('MINUTE_IN_SECONDS', 60);

class WP_Error {
    public function __construct(private string $error, private string $message) {}
    public function get_error_message(): string { return $this->message; }
}
function is_wp_error($v): bool { return $v instanceof WP_Error; }
function is_plugin_active($plugin): bool { return $GLOBALS['active']; }
function is_plugin_active_for_network($plugin): bool { return $GLOBALS['network_active']; }
function activate_plugin($plugin, $redirect = '', $network = false, $silent = false) {
    $GLOBALS['activations']++;
    if ($network) { $GLOBALS['network_active'] = true; }
    else { $GLOBALS['active'] = true; }
    return null;
}
function add_filter($name, $fn, $priority = 10, $args = 1): void {
    $GLOBALS['hooks'][$name][] = $priority;
}
function add_action($name, $fn, $priority = 10, $args = 1): void {
    $GLOBALS['hooks'][$name][] = $priority;
}
function assert_true($v, string $message): void {
    if (!$v) { fwrite(STDERR, "FAIL: " . $message . PHP_EOL); exit(1); }
}
require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-github-updater.php';
ASC_GitHub_Updater::register();

assert_true(in_array(4, $GLOBALS['hooks']['upgrader_pre_install'], true),
    'Capture activation before WordPress priority 10');
assert_true(in_array(20, $GLOBALS['hooks']['upgrader_post_install'], true),
    'Reactivate after WordPress updater');

$extra = [
    'type' => 'plugin',
    'action' => 'update',
    'plugin' => ASC_GitHub_Updater::PLUGIN,
];

$GLOBALS['active'] = true;
$GLOBALS['network_active'] = false;
$GLOBALS['activations'] = 0;
ASC_GitHub_Updater::remember_activation(true, $extra);
$GLOBALS['active'] = false; // WordPress temporarily deactivated the plugin
ASC_GitHub_Updater::reactivate(true, $extra);
assert_true($GLOBALS['active'] === true && $GLOBALS['activations'] === 1,
    'Previously active plugin must be active after update');

$GLOBALS['active'] = false;
$GLOBALS['network_active'] = false;
$GLOBALS['activations'] = 0;
ASC_GitHub_Updater::remember_activation(true, $extra);
ASC_GitHub_Updater::reactivate(true, $extra);
assert_true($GLOBALS['active'] === false && $GLOBALS['activations'] === 0,
    'Previously inactive plugin must stay inactive');

$GLOBALS['active'] = false;
$GLOBALS['network_active'] = true;
$GLOBALS['activations'] = 0;
ASC_GitHub_Updater::remember_activation(true, $extra);
$GLOBALS['network_active'] = false;
ASC_GitHub_Updater::reactivate(true, $extra);
assert_true($GLOBALS['network_active'] === true && $GLOBALS['activations'] === 1,
    'Network activated plugin must retain network activation');

$GLOBALS['active'] = false;
$GLOBALS['network_active'] = false;
$GLOBALS['activations'] = 0;
$result = ASC_GitHub_Updater::remember_activation(true, [
    'type' => 'plugin', 'action' => 'update', 'plugin' => 'another/other.php'
]);
assert_true($result === true, 'Other plugins must be ignored');

@unlink($root . '/plugins/hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php');
@unlink($root . '/wp-admin/includes/plugin.php');
@rmdir($root . '/plugins/hangar18-ai-stock-scanner');
@rmdir($root . '/plugins');
@rmdir($root . '/wp-admin/includes');
@rmdir($root . '/wp-admin');
@rmdir($root);
echo "OK: WordPress activation restoration contracts passed" . PHP_EOL;
