<?php
declare(strict_types=1);
// Røgtest af spredningsadvarslen (sektor), rensning af sektor og papirporteføljens stilling uden WordPress.
// Kør: php tests/wp_sector_spread.php
define('ABSPATH', __DIR__);
function esc_html($text): string { return htmlspecialchars((string)$text, ENT_QUOTES, 'UTF-8'); }
function esc_attr($text): string { return esc_html($text); }
function esc_url($text): string { return esc_html($text); }
function sanitize_text_field($text): string { return trim(strip_tags((string)$text)); }
function wp_date($format, $timestamp = null) { return gmdate((string)$format, $timestamp === null ? time() : (int)$timestamp); }

require_once __DIR__ . '/../wordpress/hangar18-ai-stock-scanner/includes/class-asc-playbook.php';

function check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, 'FEJL: ' . $message . PHP_EOL);
        exit(1);
    }
}

function priv(string $method, ...$args) {
    $reflection = new ReflectionMethod(ASC_Playbook::class, $method);
    $reflection->setAccessible(true);
    return $reflection->invoke(null, ...$args);
}

// ---- Sektornavn og fallback
check(ASC_Playbook::sector_label(null) === 'ukendt' && ASC_Playbook::sector_label('  ') === 'ukendt', 'manglende sektor er ukendt');
check(ASC_Playbook::sector_label(' Teknologi ') === 'Teknologi', 'sektor trimmes');
check(ASC_Playbook::sector_of(['sector' => 'Sundhed'], ['sector' => 'Energi']) === 'Sundhed', 'aktiens egen sektor vinder');
check(ASC_Playbook::sector_of(['sector' => null], ['sector' => 'Energi']) === 'Energi', 'universet er fallback');
check(ASC_Playbook::sector_of(null, []) === 'ukendt', 'ingen data er ukendt');
check(ASC_Playbook::sector_of([], ['region' => 'USA']) === 'ukendt', 'snapshot uden feltet tåles');

// ---- Optælling
$info = ASC_Playbook::sector_counts(['Teknologi', 'Sundhed', 'Teknologi', null, 'ukendt', 'Energi', 'Sundhed']);
check(array_keys($info['counts']) === ['Sundhed', 'Teknologi', 'Energi'], 'største først, ens antal alfabetisk: ' . implode(',', array_keys($info['counts'])));
check($info['counts']['Teknologi'] === 2 && $info['unknown'] === 2 && $info['total'] === 7, 'tal: ' . json_encode($info));
check(ASC_Playbook::sector_count_line(['Teknologi', 'Sundhed', 'Teknologi', null]) === 'Teknologi 2 · Sundhed 1 · ukendt 1', 'optællingslinje');
check(ASC_Playbook::sector_count_line([]) === '', 'ingen aktier, ingen linje');
check(ASC_Playbook::sector_count_line(['A & B']) === 'A &amp; B 1', 'sektornavn escapes');

// ---- Aktier med entry: flere end 3 eller over 40 %
$seven = array_merge(array_fill(0, 7, 'Teknologi'), ['Sundhed', 'Energi']);
$warning = ASC_Playbook::concentration_warning($seven, 4, 3);
check($warning === ['sector' => 'Teknologi', 'count' => 7, 'total' => 9], '7 af 9: ' . json_encode($warning));
check(ASC_Playbook::concentration_text($warning, 'aktier med entry')
    === 'Bemærk: 7 af 9 aktier med entry ligger i Teknologi. Falder sektoren, falder de samlet.', 'advarslens ordlyd');
$html = ASC_Playbook::entry_concentration_html($seven);
check(str_contains($html, 'Bemærk: 7 af 9 aktier med entry ligger i Teknologi'), 'HTML-advarsel: ' . $html);
check(str_contains($html, 'role="status"'), 'advarslen er en statusbesked');
check(ASC_Playbook::entry_concentration_html(['Teknologi', 'Sundhed']) === '', 'ingen advarsel uden koncentration');
check(ASC_Playbook::entry_concentration_html([]) === '', 'ingen aktier, ingen advarsel');
$others = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'];
check(ASC_Playbook::concentration_warning(array_merge(['X', 'X', 'X'], array_slice($others, 0, 7)), 4, 3) === null,
    '3 af 10 (30 %) giver ingen advarsel');
check(ASC_Playbook::concentration_warning(array_merge(['X', 'X', 'X', 'X'], $others), 4, 3) !== null,
    'mere end 3 giver advarsel, selv under 40 %');
check(ASC_Playbook::concentration_warning(['X', 'X', 'X'], 4, 3) === null, '3 af 3 er hverken over 3 eller nok til procentreglen (under 4 i alt)');
check(ASC_Playbook::concentration_warning(['X', 'X', 'Y', 'Z', 'W'], 4, 3) === null, '2 af 5 er præcis 40 %, ikke over');
check(ASC_Playbook::concentration_warning(['X', 'X', 'Y', 'Z'], 4, 3) !== null, '2 af 4 er 50 %');
check(ASC_Playbook::concentration_warning(['ukendt', 'ukendt', 'ukendt', 'ukendt', null, 'Y'], 4, 3) === null,
    'ukendt giver aldrig en advarsel');
check(ASC_Playbook::concentration_warning(['X', 'X', 'ukendt', 'ukendt', 'ukendt'], 4, 3) === null,
    'ukendte tæller i nævneren: 2 af 5 er ikke over 40 %');

// ---- Egne positioner (portefølje og simulator): kun over 40 % og mindst 4, ingen "flere end 3"-regel
check(ASC_Playbook::concentration_warning(['X', 'X', 'X'], 4, null) === null, '3 positioner er for få');
check(ASC_Playbook::concentration_warning(['X', 'X', 'Y', 'Z'], 4, null) !== null, '2 af 4 positioner er 50 %');
check(ASC_Playbook::concentration_warning(['X', 'X', 'Y', 'Z', 'W'], 4, null) === null, '2 af 5 positioner er 40 %');
check(ASC_Playbook::concentration_warning(array_merge(array_fill(0, 5, 'X'), $others, $others), 4, null) === null,
    '5 af 37 uden "flere end 3"-regel giver ingen advarsel');
check(ASC_Playbook::concentration_text(['sector' => 'Energi', 'count' => 3, 'total' => 5], 'positioner i din portefølje')
    === 'Bemærk: 3 af 5 positioner i din portefølje ligger i Energi. Falder sektoren, falder de samlet.', 'ordlyd for positioner');

// ---- Rensning: sektor i aktier og univers; snapshot uden feltet tåles
$stock = priv('clean_stock', ['sector' => ' Teknologi ', 'action' => 'hold øje']);
check($stock['sector'] === 'Teknologi', 'sektor i aktie: ' . var_export($stock['sector'], true));
check(priv('clean_stock', ['action' => 'hold øje'])['sector'] === null, 'aktie uden sektor giver null');
check(priv('clean_stock', ['sector' => ['x']])['sector'] === null, 'ugyldig sektor giver null');
$columns = ['ticker', 'region', 'size', 'sector'];
$universe = priv('clean_universe', ['columns' => $columns, 'rows' => [['AAPL', 'USA', 'Mega', 'Teknologi'], ['MSFT', 'USA', 'Mega']]]);
check(end($universe['columns']) === 'sector', 'sektor er sidste universkolonne');
$named = [];
foreach ($universe['rows'] as $row) {
    check(count($row) === count($universe['columns']), 'rækkens længde følger kolonnerne');
    $named[$row[0]] = array_combine($universe['columns'], $row);
}
check($named['AAPL']['sector'] === 'Teknologi', 'sektor i univers');
check($named['MSFT']['sector'] === null, 'række uden sektor giver null');
$old = priv('clean_universe', ['columns' => ['ticker', 'region'], 'rows' => [['AAPL', 'USA']]]);
check($old['rows'][0][array_search('sector', $old['columns'], true)] === null, 'gammelt snapshot uden kolonnen tåles');

// ---- Papirporteføljens stilling
check(priv('clean_paper_score', null) === null && priv('clean_paper_score', 'tekst') === null, 'ugyldig stilling giver null');
check(priv('clean_paper_score', ['sammenlignet' => 1]) === null, 'uden antal intet felt');
$score = priv('clean_paper_score', [
    'antal' => 4, 'sammenlignet' => 3, 'udeladt' => 1, 'dage' => 41, 'afkast_pct' => 5.5, 'rsp_pct' => 2.2,
    'forskel_pp' => 3.3, 'vinderandel_pct' => 66.67, 'slaar_rsp_pct' => 33.33, 'start' => '2026-09-21',
    'for_tidligt' => true, 'ekstra' => 'skal væk',
]);
check($score['antal'] === 4 && $score['sammenlignet'] === 3 && $score['udeladt'] === 1 && $score['dage'] === 41, 'heltal renses');
check($score['afkast_pct'] === 5.5 && $score['start'] === '2026-09-21' && $score['for_tidligt'] === true, 'tal og dato renses');
check(!isset($score['ekstra']), 'ukendte felter fjernes');
$bad = priv('clean_paper_score', ['antal' => 2, 'afkast_pct' => NAN, 'rsp_pct' => 'x', 'start' => '21-09-2026', 'for_tidligt' => false]);
check($bad['afkast_pct'] === null && $bad['rsp_pct'] === null && $bad['start'] === null && $bad['for_tidligt'] === false,
    'ugyldige tal bliver null');

$page = ASC_Playbook::paper_score_html($score);
check(str_contains($page, 'Under 3 måneder siger tallene ikke noget.'), 'noten om 3 måneder vises: ' . $page);
check(str_contains($page, 'aktiens egen valuta'), 'valutanoten vises');
check(str_contains($page, '+5,5 %') && str_contains($page, '+2,2 %'), 'gennemsnit vises: ' . $page);
check(str_contains($page, '+3,3 %-point'), 'forskel i procentpoint vises: ' . $page);
check(str_contains($page, '2026-09-21') && str_contains($page, 'Vinderandel'), 'startdato og vinderandel vises');
check(str_contains($page, '3 af 4 handler er med i sammenligningen; 1 er udeladt'), 'udeladte handler tælles: ' . $page);
$late = $score;
$late['for_tidligt'] = false;
$late['udeladt'] = 0;
$late['sammenlignet'] = 4;
check(!str_contains(ASC_Playbook::paper_score_html($late), 'Under 3 måneder'), 'noten forsvinder efter 3 måneder');
check(str_contains(ASC_Playbook::paper_score_html($late), '4 af 4 handler er med i sammenligningen.'), 'ingen udeladte');
check(ASC_Playbook::paper_score_html(null) === '' && ASC_Playbook::paper_score_html(['antal' => 0]) === '', 'ingen handler, ingen stilling');
$none = ['antal' => 2, 'sammenlignet' => 0, 'udeladt' => 2, 'afkast_pct' => null, 'rsp_pct' => null, 'forskel_pp' => null,
    'vinderandel_pct' => null, 'start' => null, 'for_tidligt' => true];
check(str_contains(ASC_Playbook::paper_score_html($none), '–'), 'manglende tal vises som –');
check(!str_contains(ASC_Playbook::paper_score_html($none), '+0') && !str_contains(ASC_Playbook::paper_score_html($none), '>0 %'),
    'ingen gættede nuller');

$brief = ASC_Playbook::paper_brief_html($score, 'https://x.dk/?asc_view=playbook&asc_tab=papir');
check(str_contains($brief, '4 papirhandler') && str_contains($brief, 'Under 3 måneder siger tallene ikke noget.'), 'kort stilling: ' . $brief);
check(str_contains($brief, 'href="https://x.dk/?asc_view=playbook&amp;asc_tab=papir"'), 'kort stilling har link: ' . $brief);
check(str_contains(ASC_Playbook::paper_brief_html($none, '/x'), 'ingen kan sammenlignes med RSP endnu'), 'ingen sammenlignelige handler');
check(ASC_Playbook::paper_brief_html(null, '/x') === '', 'ingen stilling, intet kort');

echo 'OK' . PHP_EOL;
