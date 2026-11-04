<?php
declare(strict_types=1);
// Røgtest af flerbruger-reglerne i playbook uden WordPress: synlige aktier, ejet-status, "Ændringer siden sidst",
// rensning og visning af Bear/Base/Bull. Kør: php tests/wp_playbook_visibility.php
define('ABSPATH', __DIR__);
function esc_html($text): string { return htmlspecialchars((string)$text, ENT_QUOTES, 'UTF-8'); }
function esc_attr($text): string { return esc_html($text); }
function sanitize_text_field($text): string { return trim(strip_tags((string)$text)); }
function wp_date($format, $timestamp = null) { return gmdate((string)$format, $timestamp === null ? time() : (int)$timestamp); }

require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-playbook.php';

function check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, 'FEJL: ' . $message . PHP_EOL);
        exit(1);
    }
}

// ---- Hvilke aktier ser en bruger?
$data = ['research' => ['MSFT', 'ugyldigt symbol'], 'candidates' => ['NVDA'], 'stocks' => []];
$visible = ASC_Playbook::visible_tickers($data, ['AAPL', 'SAP.DE'], ['NOVO-B.CO'], ['TSLA']);
$list = array_map('strval', array_keys($visible));
sort($list);
check($list === ['AAPL', 'MSFT', 'NOVO-B.CO', 'NVDA', 'SAP.DE', 'TSLA'], 'synlige aktier: ' . implode(',', $list));
check(!isset($visible['ANDEN-BRUGER']), 'en anden brugers aktie må ikke være synlig');
check(ASC_Playbook::visible_tickers([], [], [], []) === [], 'uden data er intet synligt');

// ---- Ejet-status: kun for brugerens egne aktier
$stock = [
    'action' => 'BEHOLD (ejet)', 'reasons' => '+12.3 % siden køb; ingen salgsregel ramt; faldende estimater',
    'price' => 120.0, 'currency' => 'USD',
    'exit' => ['supertrend_down' => false, 'supertrend_flips' => [], 'stockmap_sell' => false, 'sma50_breaks' => []],
];
$other = ASC_Playbook::personal_stock($stock, []);
check($other['action'] === 'hold øje', 'ikke-ejer får hold øje');
check(!str_contains((string)$other['reasons'], 'siden køb'), 'procent siden køb må ikke vises: ' . $other['reasons']);
check(!str_contains((string)$other['reasons'], 'ejet'), 'ingen ejet-tekst til ikke-ejer');
check(str_contains((string)$other['reasons'], 'faldende estimater'), 'offentlige begrundelser bevares');
$sell = $stock;
$sell['action'] = 'SÆLG (ejet)';
$sell['reasons'] = '+5.0 % siden køb; Supertrend ×3 vendt ned (2026-10-20); StockMap-salg denne uge';
check(ASC_Playbook::personal_stock($sell, [])['action'] === 'hold øje', 'SÆLG (ejet) skjules for ikke-ejer');
check(!str_contains((string)ASC_Playbook::personal_stock($sell, [])['reasons'], 'Supertrend'), 'salgsgrunde skjules for ikke-ejer');
$hold = ['action' => 'hold øje', 'reasons' => 'intet StockMap-køb'];
check(ASC_Playbook::personal_stock($hold, []) === $hold, 'almindelige aktier røres ikke');

$lots = [['ticker' => 'X', 'quantity' => 10, 'buy_price' => 100.0, 'currency' => 'USD', 'buy_date' => '2026-09-01']];
$mine = ASC_Playbook::personal_stock($stock, $lots);
check($mine['action'] === 'BEHOLD (ejet)', 'ejer ser BEHOLD (ejet)');
check(str_contains((string)$mine['reasons'], '+20,0 % siden køb'), 'gevinst regnes af brugerens egen købskurs: ' . $mine['reasons']);
$flipped = $stock;
$flipped['exit'] = ['supertrend_down' => true, 'supertrend_flips' => ['2026-10-20'], 'stockmap_sell' => false, 'sma50_breaks' => []];
check(ASC_Playbook::personal_stock($flipped, $lots)['action'] === 'SÆLG (ejet)', 'brud efter købsdatoen giver SÆLG (ejet)');
$late = [['ticker' => 'X', 'quantity' => 1, 'buy_price' => 100.0, 'currency' => 'USD', 'buy_date' => '2026-10-25']];
check(ASC_Playbook::personal_stock($flipped, $late)['action'] === 'BEHOLD (ejet)', 'brud før købsdatoen tæller ikke');
$kr = [['ticker' => 'X', 'quantity' => 1, 'buy_price' => 100.0, 'currency' => 'DKK', 'buy_date' => '2026-09-01']];
check(!str_contains((string)ASC_Playbook::personal_stock($stock, $kr)['reasons'], 'siden køb'), 'ingen procent ved blandede valutaer');

// ---- Ændringer siden sidst
$visible = ['MSFT' => true, 'NVDA' => true];
$changes = [
    'MSFT: handling: hold øje → KØB-KANDIDAT; StockMap: ingen → køb 2026-11-02',
    'ANDEN: handling: hold øje → KØB-KANDIDAT',
    'NVDA: handling: hold øje → BEHOLD (ejet)',
    'NVDA: handling: BEHOLD (ejet) → SÆLG (ejet); TPI: grøn → rød',
    'PAPIR KØB MSFT 520.17',
    42,
];
$seen = ASC_Playbook::visible_changes($changes, $visible);
check(count($seen) === 3, 'tre synlige ændringslinjer, fik ' . count($seen) . ': ' . implode(' | ', $seen));
check($seen[0] === $changes[0], 'MSFT-linjen vises uændret');
check($seen[1] === 'NVDA: TPI: grøn → rød', 'ejet-delen fjernes, resten bliver: ' . $seen[1]);
check($seen[2] === 'PAPIR KØB MSFT 520.17', 'papirporteføljen er fælles');

// ---- Rensning af scenarier (privat metode)
$clean = new ReflectionMethod(ASC_Playbook::class, 'clean_scenarios');
$clean->setAccessible(true);
check($clean->invoke(null, null) === null && $clean->invoke(null, 'tekst') === null, 'ugyldigt felt giver null');
check($clean->invoke(null, ['prices' => ['bear' => null, 'base' => null, 'bull' => null]]) === null, 'uden kursmål intet felt');
$raw = [
    'currency' => 'usd', 'horizon_years' => 2.0, 'price' => 60.0, 'eps_today' => 4.0, 'eps_horizon' => 5.0,
    'pe' => ['bear' => 10.0, 'base' => 15.0, 'bull' => 20.0, 'extra' => 1],
    'prices' => ['bear' => 50.0, 'base' => 75.0, 'bull' => 1.0e13],
    'upside_pct' => ['bear' => -16.7, 'base' => 25.0, 'bull' => 'tekst'], 'cagr_pct' => ['bear' => -200.0],
    'asymmetry' => null, 'asymmetry_inf' => true, 'peg' => 1.2,
    'notes' => ['Under 3 års P/E-historik', str_repeat('x', 500), 'a', 'b', 'c', 'd', 'e'],
];
$c = $clean->invoke(null, $raw);
check(is_array($c) && $c['currency'] === 'USD', 'valuta renses');
check($c['prices']['base'] === 75.0 && $c['prices']['bull'] === null, 'for stort kursmål afvises');
check($c['upside_pct']['bull'] === null && $c['cagr_pct']['bear'] === null, 'ikke-tal og tal uden for grænsen afvises');
check(!isset($c['pe']['extra']) && $c['pe']['base'] === 15.0, 'kun bear/base/bull beholdes');
check($c['asymmetry_inf'] === true && $c['asymmetry'] === null, 'uendelig asymmetri markeres');
check(count($c['notes']) === 6 && strlen($c['notes'][1]) === 160, 'højst seks noter på 160 tegn');

// ---- Visning
$html = ASC_Playbook::scenario_cards_html($c);
foreach (['Bear', 'Base', 'Bull', 'Kurs nu', 'EPS 5,00 × P/E 15,0', '75,00', '+25,0 %', 'ikke en prognose'] as $needle) {
    check(str_contains($html, $needle), 'scenariekort mangler: ' . $needle);
}
check(str_contains($html, '∞'), 'uendelig asymmetri vises som ∞');
$empty = ASC_Playbook::scenario_cards_html(['prices' => [], 'notes' => ['<script>x</script>']]);
check(!str_contains($empty, '<script>'), 'noter escapes');
check(str_contains($empty, 'ikke en prognose'), 'forklaringen er altid med');

echo 'ok' . PHP_EOL;
