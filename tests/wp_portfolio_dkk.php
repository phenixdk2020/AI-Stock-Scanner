<?php
declare(strict_types=1);
/** Offline unit checks for DKK P/L; no WordPress, external FX source or browser. */
define('ABSPATH', __DIR__ . '/');
define('DAY_IN_SECONDS', 86400);
require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-portfolio.php';
require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-fx-rates.php';

function equal_near(float $actual, float $expected, string $what): void {
    if (!is_finite($actual) || abs($actual - $expected) > 0.00001) {
        throw new RuntimeException($what . ': expected ' . $expected . ', got ' . $actual);
    }
}
$d = ASC_Portfolio::calculate_dkk_values(
    10.0, 20.0, 30.0, 'USD', 1500.0, 6.9
);
if ($d === null) { throw new RuntimeException('Missing DKK calculation'); }
equal_near((float)$d['purchase_rate'], 7.5, 'Effective purchase FX');
equal_near((float)$d['invested_dkk'], 1500.0, 'Actual paid DKK');
equal_near((float)$d['value_dkk'], 2070.0, 'Current value DKK');
equal_near((float)$d['profit_dkk'], 570.0, 'DKK P/L including FX and fees');
if ($d['used_purchase_fx_fallback'] || $d['estimated_invested_dkk']) {
    throw new RuntimeException('Actual DKK + current FX was wrongly marked estimated');
}

$fallback = ASC_Portfolio::calculate_dkk_values(
    10.0, 20.0, 30.0, 'USD', 1500.0, null
);
if ($fallback === null || !$fallback['used_purchase_fx_fallback']) {
    throw new RuntimeException('Missing labeled purchase FX fallback');
}
equal_near((float)$fallback['profit_dkk'], 750.0, 'Purchase FX fallback P/L');

$no_paid = ASC_Portfolio::calculate_dkk_values(
    10.0, 20.0, 30.0, 'USD', null, 6.9
);
if ($no_paid === null || !$no_paid['estimated_invested_dkk']) {
    throw new RuntimeException('Historical DKK cost without paid amount must be marked estimate');
}
equal_near((float)$no_paid['invested_dkk'], 1380.0, 'Estimated invested DKK');
equal_near((float)$no_paid['profit_dkk'], 690.0, 'Estimated DKK price change');
if (ASC_Portfolio::calculate_dkk_values(10.0, 20.0, 30.0, 'USD', null, null) !== null) {
    throw new RuntimeException('Missing FX and historical paid DKK must not invent a rate');
}
$dkk = ASC_Portfolio::calculate_dkk_values(10.0, 20.0, 30.0, 'DKK', 220.0, null);
if ($dkk === null) { throw new RuntimeException('DKK native position missing'); }
equal_near((float)$dkk['invested_dkk'], 220.0, 'Actual DKK cost including fees');
equal_near((float)$dkk['value_dkk'], 300.0, 'DKK current value');
equal_near((float)$dkk['profit_dkk'], 80.0, 'DKK gain after fees');

$fixture = [
    'eur_rates' => ['EUR' => 1.0, 'DKK' => 7.4600, 'USD' => 1.1600, 'SEK' => 10.5000],
];
equal_near((float)ASC_FX_Rates::rate_from_snapshot($fixture, 'USD'), 7.4600 / 1.1600, 'ECB cross-rate USD/DKK');
equal_near((float)ASC_FX_Rates::rate_from_snapshot($fixture, 'DKK'), 1.0, 'DKK reference');
if (ASC_FX_Rates::rate_from_snapshot($fixture, 'NOK') !== null) {
    throw new RuntimeException('Missing NOK must not receive fabricated FX');
}

echo "PASS: Actual DKK paid, ECB current value, effective purchase FX, fallback, fees and multi-currency conversion.\n";
