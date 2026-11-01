<?php
declare(strict_types=1);
/**
 * Offline WordPress user-meta regression:
 * - Simulate three independent POST requests (each add() exits after redirect).
 * - Assert that all three purchases persist and remain unchanged.
 * - Does not contact WordPress, Yahoo, or an exchange.
 */
define('ABSPATH', __DIR__ . '/');
function is_user_logged_in(): bool { return true; }
function get_current_user_id(): int { return 42; }
function check_admin_referer(string $name): void {}
function sanitize_text_field(string $value): string { return trim(strip_tags($value)); }
function wp_unslash(string $value): string { return stripslashes($value); }
function wp_date(string $format): string { return gmdate($format); }
function wp_generate_uuid4(): string { return bin2hex(random_bytes(16)); }
function wp_get_referer(): string { return 'https://example.test/'; }
function home_url(string $path = '/'): string { return 'https://example.test' . $path; }
function wp_validate_redirect(string $url, string $fallback): string { return $url; }
function remove_query_arg(string $key, string $url): string { return $url; }
function add_query_arg(string $key, string $value, string $url): string {
    return $url . (strpos($url, '?') === false ? '?' : '&') . $key . '=' . $value;
}
function wp_safe_redirect(string $url): bool { echo "REDIRECT: " . $url . "\n"; return true; }
function auth_redirect(): void { throw new RuntimeException('Unexpected login redirect'); }
function get_user_meta(int $id, string $key, bool $single): array {
    $data = json_decode((string)file_get_contents($GLOBALS['fixture']), true);
    return is_array($data) ? $data : [];
}
function update_user_meta(int $id, string $key, array $value): bool {
    return file_put_contents($GLOBALS['fixture'], json_encode($value)) !== false;
}

require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-portfolio.php';

if (($argv[1] ?? '') === 'child') {
    if (count($argv) < 5 || count($argv) > 6) { exit(2); }
    $GLOBALS['fixture'] = $argv[2];
    $_POST = [
        'asc_ticker' => $argv[3],
        'asc_label' => $argv[4],
        'asc_quantity' => $argv[5] ?? '10',
        'asc_buy_price' => '120,50',
        'asc_initial_price' => '131,25',
        'asc_currency' => 'DKK',
        'asc_buy_date' => '',
    ];
    ASC_Portfolio::add();
    exit(4);  // Unreachable on a successful redirect.
}

$temp = tempnam(sys_get_temp_dir(), 'asc-portfolio-');
if ($temp === false) { throw new RuntimeException('Unable to create fixture'); }
file_put_contents($temp, '[]');
$stocks = ['NOVO-B.CO', 'VWS.CO', 'DSV.CO'];
try {
    foreach ($stocks as $i => $ticker) {
        $args = [
            escapeshellarg(PHP_BINARY),
            escapeshellarg(__FILE__),
            'child',
            escapeshellarg($temp),
            escapeshellarg($ticker),
            escapeshellarg('Test ' . ($i + 1)),
        ];
        $output = [];
        $status = -1;
        exec(implode(' ', $args) . ' 2>&1', $output, $status);
        if ($status !== 0) {
            throw new RuntimeException('Add #' . ($i + 1) . ' failed: ' . implode(' ', $output));
        }
        $data = json_decode((string)file_get_contents($temp), true);
        if (!is_array($data) || count($data) !== $i + 1) {
            throw new RuntimeException('Expected ' . ($i + 1) . ' saved purchases, got '
                . (is_array($data) ? count($data) : 'invalid payload'));
        }
        foreach (array_slice($stocks, 0, $i + 1) as $j => $expected) {
            if (($data[$j]['ticker'] ?? '') !== $expected
                || (float)($data[$j]['quantity'] ?? 0) !== 10.0
                || (float)($data[$j]['buy_price'] ?? 0) !== 120.5
                || (float)($data[$j]['manual_price'] ?? 0) !== 131.25) {
                throw new RuntimeException('Purchase #' . ($j + 1) . ' was overwritten or malformed.');
            }
        }
    }
    // Fractional share quantities must be rejected and must not create another lot.
    foreach (['2,5', '3.25', '2,00', '0', '-1'] as $invalid) {
        $args = [
            escapeshellarg(PHP_BINARY), escapeshellarg(__FILE__), 'child',
            escapeshellarg($temp), escapeshellarg('AAPL'),
            escapeshellarg('Invalid quantity test'), escapeshellarg($invalid),
        ];
        $output = []; $status = -1;
        exec(implode(' ', $args) . ' 2>&1', $output, $status);
        if ($status !== 0 || strpos(implode(' ', $output), 'asc_portfolio_status=invalid_quantity') === false) {
            throw new RuntimeException('Fractional/invalid quantity was not rejected: ' . $invalid);
        }
        $check = json_decode((string)file_get_contents($temp), true);
        if (count($check) !== 3) { throw new RuntimeException('Rejected quantity modified persisted positions'); }
    }

    // A properly grouped Danish whole number is accepted as 1,000 shares.
    $args = [escapeshellarg(PHP_BINARY), escapeshellarg(__FILE__), 'child',
        escapeshellarg($temp), escapeshellarg('MSFT'), escapeshellarg('Grouped integer'),
        escapeshellarg('1.000')];
    $output = []; $status = -1;
    exec(implode(' ', $args) . ' 2>&1', $output, $status);
    $check = json_decode((string)file_get_contents($temp), true);
    if ($status !== 0 || count($check) !== 4
        || (int)($check[3]['quantity'] ?? 0) !== 1000) {
        throw new RuntimeException('1.000 was not accepted as one thousand shares');
    }
    echo "PASS: 3 independent buys, fractional quantities rejected, 1.000 stored as 1000.\n";
} finally {
    @unlink($temp);
}
