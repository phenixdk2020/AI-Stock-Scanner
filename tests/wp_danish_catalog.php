<?php
declare(strict_types=1);
define('ABSPATH', __DIR__ . '/');
require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-danish-catalog.php';

$path = __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/assets/danish-stocks-snapshot.csv';
$csv = (string)file_get_contents($path);
$rows = ASC_Danish_Catalog::parse_csv($csv);
if (count($rows) !== 141) {
    throw new RuntimeException('Expected 141 real reference rows, got ' . count($rows));
}
$by_ticker = [];
foreach ($rows as $row) {
    $by_ticker[$row['ticker']] = $row;
}
foreach (['NOVO-B.CO', 'HARB-B.CO', 'DSV.CO', 'DANSKE.CO', 'VWS.CO'] as $ticker) {
    if (!isset($by_ticker[$ticker])) {
        throw new RuntimeException('Missing known Copenhagen symbol ' . $ticker);
    }
}
if (strpos($by_ticker['HARB-B.CO']['name'], 'Harboes') === false ||
    $by_ticker['HARB-B.CO']['currency'] !== 'DKK' ||
    $by_ticker['HARB-B.CO']['type'] !== 'Aktie') {
    throw new RuntimeException('Harboe stock metadata incorrect');
}
$custom = "name,ticker,isin,sector\n" .
    "Test Aktie,TEST-B.CO,DK0010274414,Industri\n" .
    "Evil <script>alert(1)</script>,BAD.CO,NOPE,Tech\n" .
    "Test Aktie,TEST-B.CO,DK0010274414,Duplicate\n" .
    "No symbol,../evil,DK0010274414,Bad\n";
$parsed = ASC_Danish_Catalog::parse_csv($custom);
if (count($parsed) !== 2 || $parsed[0]['ticker'] !== 'BAD.CO' ||
    $parsed[1]['ticker'] !== 'TEST-B.CO' ||
    $parsed[1]['isin'] !== 'DK0010274414' ||
    strpos($parsed[0]['name'], '<') !== false ||
    $parsed[0]['isin'] !== '') {
    throw new RuntimeException('CSV import validation, ISIN or XSS protection failed');
}
if (ASC_Danish_Catalog::parse_csv("ticker,sector\nTEST.CO,Finance\n") !== []) {
    throw new RuntimeException('CSV import without name header should fail');
}
if (ASC_Danish_Catalog::parse_csv(str_repeat('x', 100001)) !== []) {
    throw new RuntimeException('Oversized CSV must be rejected');
}
$old_rows = [
    ['ticker' => 'OLD.CO', 'name' => 'Tidligere notering', 'isin' => 'DK1234567890', 'sector' => 'Finans'],
    ['ticker' => 'HARB-B.CO', 'name' => 'Harboe', 'isin' => ''],
];
$new_rows = [
    ['ticker' => 'NEW.CO', 'name' => 'Nyt navn', 'isin' => 'DK1234567890', 'sector' => 'Finans'],
];
$partial = ASC_Danish_Catalog::reconcile($old_rows, $new_rows, false);
if (count($partial['rows']) !== 2 || $partial['added'] !== 0 ||
    $partial['matched'] !== 1 || $partial['not_found'] !== 0 ||
    in_array('not_found', array_column($partial['rows'], 'listing_status'), true)) {
    throw new RuntimeException('Partial import must not mark absent holdings as delisted');
}
$complete = ASC_Danish_Catalog::reconcile($old_rows, $new_rows, true);
if (count($complete['rows']) !== 2 || $complete['matched'] !== 1 ||
    $complete['added'] !== 0 || $complete['not_found'] !== 1) {
    throw new RuntimeException('Complete list must flag one unmatched security');
}
$by_ticker = array_column($complete['rows'], null, 'ticker');
if (!isset($by_ticker['NEW.CO'], $by_ticker['HARB-B.CO']) ||
    $by_ticker['NEW.CO']['listing_status'] !== 'found' ||
    $by_ticker['HARB-B.CO']['listing_status'] !== 'not_found' ||
    $by_ticker['NEW.CO']['isin'] !== 'DK1234567890') {
    throw new RuntimeException('Changed ticker ISIN match or non-destructive flag failed');
}
$add = ASC_Danish_Catalog::reconcile($old_rows, [
    ['ticker' => 'HARB-B.CO', 'name' => 'Harboe', 'isin' => ''],
    ['ticker' => 'EXTRA.CO', 'name' => 'Ekstra', 'isin' => ''],
], true);
if ($add['not_found'] !== 1 || $add['added'] !== 1 || count($add['rows']) !== 3) {
    throw new RuntimeException('New and unmatched security reconciliation failed');
}
echo "PASS: 141 bundled Danish securities, search metadata, ticker conversion, CSV/ISIN validation.\n";
