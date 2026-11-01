<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Research overview of the latest scanner snapshot and transparent scenario calculator.
 * Does not generate unlicensed fundamental scores, forecasts, or trade advice.
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

    public static function render(): string {
        if (!is_user_logged_in()) { return '<p>Log ind for at se analyser.</p>'; }
        wp_enqueue_style('hangar18-asc');
        $snapshot = get_option(ASC_OPTION_SNAPSHOT, []);
        $rows = is_array($snapshot) && is_array($snapshot['rows'] ?? null)
            ? $snapshot['rows'] : [];
        $scores = [];
        $signals = ['Interessant' => 0, 'Hold øje' => 0, 'Afvent' => 0];
        foreach ($rows as $row) {
            if (!is_array($row)) { continue; }
            $score = $row['score'] ?? null;
            if (is_int($score) && $score >= 0 && $score <= 100) {
                $scores[] = $score;
            }
            $signal = $row['signal'] ?? '';
            if (isset($signals[$signal])) { $signals[$signal]++; }
        }
        $sample = count($scores);
        $mean = $sample > 0 ? round(array_sum($scores) / $sample, 1) : null;
        $eps = self::input('asc_eps', 20.0, 100000.0);
        $bear = self::input('asc_pe_bear', 10.0, 10000.0);
        $base = self::input('asc_pe_base', 15.0, 10000.0);
        $bull = self::input('asc_pe_bull', 20.0, 10000.0);

        ob_start();
        echo '<section class="asc-analysis" aria-label="Aktieanalyse">';
        echo '<h2>Analyser og scenarier</h2>';
        echo '<p>Teknisk screening og manuel værdiansættelse holdes adskilt. '
            . 'Vi viser ikke opdigtede kvalitet-, moat- eller fundamentale scorer.</p>';
        echo '<div class="asc-analysis-grid">';
        echo '<div class="asc-analysis-card"><h3>Analyserede papirer</h3><strong>'
            . esc_html((string)$sample) . '</strong></div>';
        echo '<div class="asc-analysis-card"><h3>Gennemsnitlig teknisk score</h3><strong>'
            . ($mean !== null ? esc_html(number_format($mean, 1, ',', '.')) . '/100' : '—')
            . '</strong></div>';
        echo '<div class="asc-analysis-card"><h3>Teknisk signalfordeling</h3>';
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
        echo '<h3>Manuel bull / base / bear-beregner</h3>';
        echo '<p>Angiv selv forventet indtjening pr. andel (EPS) og P/E-multipler. '
            . 'Beregningen er kun EPS × P/E, ingen AI-prognose og ingen vurdering af sandsynlighed.</p>';
        echo '<form class="asc-filter-form" method="get" action="">';
        $view = isset($_GET['asc_view']) && is_string($_GET['asc_view'])
            ? sanitize_key(wp_unslash($_GET['asc_view'])) : '';
        if ($view === 'analysis') {
            echo '<input type="hidden" name="asc_view" value="analysis">';
        }
        $fields = [
            'asc_eps' => ['Forventet EPS', $eps],
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
        echo '<p class="asc-disclaimer">Scenarier er brugerindtastede regneeksempler og '
            . 'er ikke automatisk baseret på finansielle regnskaber. '
            . 'Scorens seks tekniske kriterier er SMA50, SMA200, RSI14, MACD, '
            . '21-dages udvikling og relativ volumen. '
            . 'Der er endnu ingen beregnet fundamental kvalitet eller moat.</p>';
        echo '</section>';
        return (string)ob_get_clean();
    }
}
