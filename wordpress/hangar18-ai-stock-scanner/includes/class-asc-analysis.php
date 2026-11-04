<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Overblik over seneste scannerkørsel, automatiske Bear/Base/Bull-scenarier pr. aktie og en manuel beregner.
 * Scenarierne er regnestykket EPS × P/E; siden laver ingen prognoser og ingen handelsråd.
 */
final class ASC_Analysis {
    public static function register(): void {
        add_shortcode('ai_stock_analysis', [self::class, 'render']);
    }

    private static function input(string $key, float $default, float $max): float {
        $raw = $_GET[$key] ?? '';
        if (!is_string($raw)) { return $default; }
        $raw = trim(str_replace(',', '.', wp_unslash($raw)));
        if (preg_match('/^(?:[0-9]+)(?:\.[0-9]{1,4})?$/D', $raw) !== 1) {
            return $default;
        }
        $num = (float)$raw;
        return is_finite($num) && $num > 0 && $num <= $max ? $num : $default;
    }

    /** Det valgte aktiesymbol fra asc_analysis_ticker, kun hvis det er gyldigt. */
    private static function picked_ticker(): string {
        $raw = $_GET['asc_analysis_ticker'] ?? '';
        if (!is_string($raw)) { return ''; }
        $ticker = strtoupper(trim(sanitize_text_field(wp_unslash($raw))));
        return preg_match('/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D', $ticker) === 1 ? $ticker : '';
    }

    /** Et tal fra scenarierne, der kan bruges som startværdi i beregneren (positivt og inden for grænsen). */
    private static function seed($value, float $max): ?float {
        return (is_int($value) || is_float($value)) && is_finite((float)$value) && $value > 0 && $value <= $max
            ? round((float)$value, 4) : null;
    }

    public static function render(): string {
        if (!is_user_logged_in()) { return '<p>Log ind for at se analyser.</p>'; }
        wp_enqueue_style('hangar18-asc');
        $snapshot = get_option(ASC_OPTION_SNAPSHOT, []);
        $rows = is_array($snapshot) && is_array($snapshot['rows'] ?? null)
            ? $snapshot['rows'] : [];
        $scores = [];
        $signals = ['Købskandidat' => 0, 'Hold øje' => 0, 'Salgssignal' => 0, 'Afvent' => 0];
        foreach ($rows as $row) {
            if (!is_array($row)) { continue; }
            $score = $row['score'] ?? null;
            if (is_int($score) && $score >= 0 && $score <= 100) {
                $scores[] = $score;
            }
            $signal = ($row['signal'] ?? '') === 'Interessant' ? 'Købskandidat' : ($row['signal'] ?? '');
            if (isset($signals[$signal])) { $signals[$signal]++; }
        }
        $sample = count($scores);
        $mean = $sample > 0 ? round(array_sum($scores) / $sample, 1) : null;
        $picked = self::picked_ticker();
        $auto = $picked !== '' && class_exists('ASC_Playbook') ? ASC_Playbook::scenarios_for($picked) : null;
        $auto_pe = is_array($auto) && is_array($auto['pe'] ?? null) ? $auto['pe'] : [];
        // En valgt aktie udfylder EPS og de tre P/E; tal brugeren selv har rettet (i adressen) vinder.
        $eps = self::input('asc_eps', self::seed($auto['eps_horizon'] ?? null, 100000.0) ?? 20.0, 100000.0);
        $bear = self::input('asc_pe_bear', self::seed($auto_pe['bear'] ?? null, 10000.0) ?? 10.0, 10000.0);
        $base = self::input('asc_pe_base', self::seed($auto_pe['base'] ?? null, 10000.0) ?? 15.0, 10000.0);
        $bull = self::input('asc_pe_bull', self::seed($auto_pe['bull'] ?? null, 10000.0) ?? 20.0, 10000.0);

        ob_start();
        echo '<section class="asc-analysis" aria-label="Aktieanalyse">';
        echo '<h2>Analyser og scenarier</h2>';
        echo '<p>Siden viser et overblik over scannerens seneste kørsel (antal papirer, gennemsnitlig MSS-score og '
            . 'signalfordeling), automatiske Bear/Base/Bull-scenarier for de aktier, scanneren har regnet på, og en manuel '
            . 'beregner. Scenarierne er regnestykket EPS × P/E ud fra historiske P/E og analytikernes estimater, ikke en prognose.</p>';
        echo '<div class="asc-analysis-grid">';
        echo '<div class="asc-analysis-card"><h3>Analyserede papirer</h3><strong>'
            . esc_html((string)$sample) . '</strong></div>';
        echo '<div class="asc-analysis-card"><h3>Gennemsnitlig MSS-score</h3><strong>'
            . ($mean !== null ? esc_html(number_format($mean, 1, ',', '.')) . '/100' : '—')
            . '</strong></div>';
        echo '<div class="asc-analysis-card"><h3>Signalfordeling</h3>';
        foreach ($signals as $signal => $count) {
            echo '<p>' . esc_html($signal) . ': <strong>'
                . esc_html((string)$count) . '</strong></p>';
        }
        echo '</div></div>';
        if (is_array($snapshot) && ($snapshot['mode'] ?? '') === 'demo') {
            echo '<p class="asc-warning">DEMODATA – signalfordelingen er ikke markedsanalyse.</p>';
        }
        if (is_array($snapshot) && !empty($snapshot['generated_at'])) {
            echo '<p class="asc-updated">Snapshot (UTC): '
                . esc_html((string)$snapshot['generated_at']) . '</p>';
        }
        $view = isset($_GET['asc_view']) && is_string($_GET['asc_view'])
            ? sanitize_key(wp_unslash($_GET['asc_view'])) : '';
        echo '<h3>Automatisk Bear / Base / Bull</h3>';
        echo '<p>Vælg en aktie, som scanneren har regnet på. Kursmålet er forventet EPS ved horisonten (normalt to år frem) gange P/E i hvert '
            . 'scenarie (laveste, midterste og højeste historiske P/E). Det er et regnestykke, ikke en forudsigelse af kursen.</p>';
        $options = class_exists('ASC_Playbook') ? ASC_Playbook::scenario_tickers() : [];
        if ($picked !== '' && !in_array($picked, $options, true)) { $options[] = $picked; }
        echo '<form class="asc-filter-form" method="get" action="">';
        if ($view === 'analysis') {
            echo '<input type="hidden" name="asc_view" value="analysis">';
        }
        echo '<label>Aktie<select name="asc_analysis_ticker"><option value="">Vælg aktie</option>';
        foreach ($options as $option) {
            echo '<option value="' . esc_attr($option) . '"' . selected($picked, $option, false) . '>'
                . esc_html($option) . '</option>';
        }
        echo '</select></label><button type="submit">Vis scenarier</button></form>';
        if ($picked === '') {
            echo '<p class="asc-subtle">' . ($options ? 'Vælg en aktie for at se Bear, Base og Bull.'
                : 'Ingen aktier har scenarier endnu. Følg en aktie, så kommer den med ved næste kørsel.') . '</p>';
        } elseif (!is_array($auto)) {
            echo '<h4>' . esc_html($picked) . '</h4><p class="asc-empty">Ikke beregnet endnu. Følg aktien, '
                . 'så kommer den med ved næste kørsel.</p>';
        } else {
            echo '<h4>' . esc_html($picked) . '</h4>' . ASC_Playbook::scenario_cards_html($auto);
        }

        echo '<h3>Manuel bull / base / bear-beregner</h3>';
        echo '<p>' . ($picked !== '' && is_array($auto)
            ? 'EPS og P/E er udfyldt fra ' . esc_html($picked) . ' ovenfor – ret tallene, hvis du vil regne selv. '
            : 'Angiv selv forventet indtjening pr. andel (EPS) og P/E-multipler. ')
            . 'Beregningen er kun EPS × P/E, ingen AI-prognose og ingen vurdering af sandsynlighed.</p>';
        echo '<form class="asc-filter-form" method="get" action="">';
        if ($view === 'analysis') {
            echo '<input type="hidden" name="asc_view" value="analysis">';
        }
        if ($picked !== '') {
            echo '<input type="hidden" name="asc_analysis_ticker" value="' . esc_attr($picked) . '">';
        }
        $fields = [
            'asc_eps' => [is_array($auto) ? 'Forventet EPS (ved horisonten)' : 'Forventet EPS', $eps],
            'asc_pe_bear' => ['Bear P/E', $bear],
            'asc_pe_base' => ['Base P/E', $base],
            'asc_pe_bull' => ['Bull P/E', $bull],
        ];
        foreach ($fields as $name => $config) {
            echo '<label>' . esc_html($config[0])
                . '<input name="' . esc_attr($name)
                . '" type="number" min="0.0001" step="any" value="'
                . esc_attr((string)$config[1]) . '" required></label>';
        }
        echo '<button type="submit">Beregn scenarier</button></form>';
        echo '<div class="asc-analysis-grid">';
        foreach (['Bear' => $bear, 'Base' => $base, 'Bull' => $bull] as $scenario => $multiple) {
            echo '<div class="asc-analysis-card"><h3>' . esc_html($scenario) . '</h3>'
                . '<strong>' . esc_html(number_format($eps * $multiple, 2, ',', '.'))
                . '</strong><p>Pris i samme valuta som EPS</p>'
                . '<small>EPS ' . esc_html((string)$eps) . ' × P/E '
                . esc_html((string)$multiple) . '</small></div>';
        }
        echo '</div>';
        echo '<p class="asc-disclaimer">Scenarier er regneeksempler (EPS × P/E) ud fra historiske P/E og analytikernes '
            . 'estimater, ikke prognoser og ikke købs- eller salgsanbefalinger. De automatiske tal kommer fra scannerens '
            . 'seneste kørsel; i den manuelle beregner er det dine egne tal. MSS-scoren og signalfordelingen øverst '
            . 'kommer fra mandagslisten (kvalitet, værdikanal og moat).</p>';
        echo '</section>';
        return (string)ob_get_clean();
    }
}
