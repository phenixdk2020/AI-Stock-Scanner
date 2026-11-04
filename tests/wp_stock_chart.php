<?php
declare(strict_types=1);
// Røgtest af aktiesidens graf uden WordPress: skriver SVG-markup for syntetiske kursdata og kontrollerer den.
// Kør: php tests/wp_stock_chart.php          (tilføj --print for at se den udskrevne HTML)
define('ABSPATH', __DIR__);
function esc_html($text): string { return htmlspecialchars((string)$text, ENT_QUOTES, 'UTF-8'); }
function esc_attr($text): string { return esc_html($text); }
function wp_date($format, $timestamp = null) { return gmdate((string)$format, $timestamp === null ? time() : (int)$timestamp); }

require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-market-quotes.php';

function check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, 'FEJL: ' . $message . PHP_EOL);
        exit(1);
    }
}

// 700 handelsdage (uden weekender) med en rolig, deterministisk kurve.
$bars = [];
$time = strtotime('2024-01-02 08:00:00 UTC');
for ($i = 0; count($bars) < 700; $i++) {
    $stamp = $time + $i * 86400;
    if ((int)gmdate('N', $stamp) >= 6) { continue; }
    $n = count($bars);
    $base = 100 + 10 * sin($n / 20) + $n * 0.05;
    $open = $base;
    $close = $base + sin($n) * 0.8;
    $bars[] = [
        'time' => $stamp, 'open' => $open, 'high' => max($open, $close) + 1.0,
        'low' => min($open, $close) - 1.0, 'close' => $close, 'volume' => 1000.0 + ($n % 7) * 100,
    ];
}
$last_date = gmdate('Y-m-d', $bars[699]['time']);
$inside = gmdate('Y-m-d', $bars[690]['time']);
$markers = [
    ['date' => $inside, 'kind' => 'buy'],
    ['date' => $inside, 'kind' => 'sim_buy'],
    ['date' => $last_date, 'kind' => 'sim_sell'],
    ['date' => '2000-01-03', 'kind' => 'buy'],          // uden for perioden: springes over
    ['date' => 'ikke-en-dato', 'kind' => 'buy'],        // ugyldig: springes over
    ['date' => $inside, 'kind' => 'ukendt'],            // ukendt slags: springes over
];

$html = ASC_Market_Quotes::stock_chart('TEST.CO', $bars, 'DKK', '6m', $markers);
if (in_array('--print', $argv ?? [], true)) { echo $html, PHP_EOL; }

check(str_contains($html, '<svg') && str_contains($html, '</svg>'), 'SVG mangler');
check(str_contains($html, 'data-line="sma50"') && str_contains($html, 'data-line="sma200"'), 'SMA-linjer mangler');
check(str_contains($html, 'SMA50') && str_contains($html, 'SMA200'), 'forklaring mangler');
check(substr_count($html, 'class="asc-marker"') === 3, 'forventede tre markører, fik ' . substr_count($html, 'class="asc-marker"'));
check(str_contains($html, 'data-kind="sim_sell"') && str_contains($html, 'data-kind="buy"'), 'markørtyper mangler');
check(!str_contains($html, '<script') && substr_count($html, 'http') === 1, 'ekstern kode eller adresse i grafen');
check(str_contains($html, 'handelsdag'), '6m skal være daglige candles');

$weekly = ASC_Market_Quotes::stock_chart('TEST.CO', $bars, 'DKK', '5y', []);
check(str_contains($weekly, 'Hver kerte er en uge'), '5y skal samles til uger');
check(!str_contains($weekly, 'class="asc-marker"'), 'ingen markører uden datoer');

$month = ASC_Market_Quotes::stock_chart('TEST.CO', $bars, 'DKK', '1m', []);
check(str_contains($month, 'data-line="sma200"'), 'SMA200 skal også findes i en kort periode');

$short = ASC_Market_Quotes::stock_chart('TEST.CO', array_slice($bars, 0, 60), 'DKK', '6m', []);
check(!str_contains($short, 'data-line="sma200"') && str_contains($short, 'for lidt historik'), 'SMA200 må ikke gættes uden 200 dage');

check(str_contains(ASC_Market_Quotes::stock_chart('TEST.CO', [], 'DKK', '6m', []), 'Ingen valide'), 'tom historik');

fwrite(STDOUT, "OK: aktiesidens graf" . PHP_EOL);
