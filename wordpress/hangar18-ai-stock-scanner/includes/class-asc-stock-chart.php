<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Aktiesidens interaktive graf (TradingView Lightweight Charts, Apache-2.0): trådkors, zoom, perioder, linje/candles,
 * volumen, SMA50/SMA200, markører for brugerens handler og nøgletal under grafen.
 *
 * Biblioteket ligger i pluginet (assets/vendor/lightweight-charts), og intet indlæses udefra. Kurserne lægges i siden
 * som JSON i et <script type="application/json">, aldrig som kode. Intradagsdata (1 D og 1 U) hentes af assets/stock-chart.js
 * fra den loginkrævende REST-rute ai-stock-scanner/v1/quotes/intraday. Mislykkes indlæsningen af biblioteket, viser
 * scriptet den serverrenderede SVG-graf, som ligger i <noscript> ($svg_html) og også vises uden JavaScript.
 * Kun visning: klassen ændrer intet og gætter aldrig en kurs.
 */
final class ASC_Stock_Chart {
    /** Den pinnede version af biblioteket (npm lightweight-charts); se assets/vendor/lightweight-charts/README.md. */
    public const LIBRARY_VERSION = '5.2.1';
    private const MARKER_KINDS = ['buy', 'sim_buy', 'sim_sell'];
    private const YEAR = 31536000;  // 365 dage i sekunder: 52 uger.

    private static function fmt(float $value, int $decimals = 2): string {
        return number_format($value, $decimals, ',', '.');
    }

    private static function plugin_file(): string {
        return dirname(__DIR__) . '/hangar18-ai-stock-scanner.php';
    }

    /** Biblioteket og scriptet indlæses kun, når aktiesiden tegner en graf (ikke på andre sider). */
    private static function enqueue(): void {
        wp_enqueue_script(
            'hangar18-asc-lwc',
            plugins_url('assets/vendor/lightweight-charts/lightweight-charts.standalone.production.js', self::plugin_file()),
            [],
            self::LIBRARY_VERSION,
            true
        );
        wp_enqueue_script(
            'hangar18-asc-stock-chart',
            plugins_url('assets/stock-chart.js', self::plugin_file()),
            ['hangar18-asc-lwc'],
            defined('ASC_PLUGIN_VERSION') ? ASC_PLUGIN_VERSION : self::LIBRARY_VERSION,
            true
        );
    }

    /**
     * Nøgletal af de daglige bars: seneste dags åbning, høj, lav og volumen, 52 ugers høj/lav (kun med mindst et års
     * historik) samt P/E og markedsværdi fra playbook-data. Mangler et tal, vises "–".
     * @param array<int, array<string, mixed>> $bars Stigende i tid.
     * @param array{pe: ?float, mcap_usd_bn: ?float} $playbook
     */
    public static function figures_html(array $bars, string $currency, array $playbook): string {
        $bars = array_values(array_filter($bars, static fn($bar): bool => is_array($bar)
            && is_numeric($bar['time'] ?? null) && is_numeric($bar['open'] ?? null) && is_numeric($bar['high'] ?? null)
            && is_numeric($bar['low'] ?? null) && is_numeric($bar['close'] ?? null)));
        $count = count($bars);
        if ($count === 0) { return ''; }
        $last = $bars[$count - 1];
        $last_time = (int)$last['time'];
        $since = $last_time - self::YEAR;
        $high = null;
        $low = null;
        foreach ($bars as $bar) {
            if ((int)$bar['time'] < $since) { continue; }
            $high = $high === null ? (float)$bar['high'] : max($high, (float)$bar['high']);
            $low = $low === null ? (float)$bar['low'] : min($low, (float)$bar['low']);
        }
        // 52 uger kræver, at historikken når cirka et år tilbage (en uges slæk for weekender og helligdage).
        $full_year = (int)$bars[0]['time'] <= $since + 7 * 86400;
        $unit = $currency !== '' ? ' ' . $currency : '';
        $money = static fn(?float $value): string => $value === null ? '–' : self::fmt($value) . $unit;
        $volume = is_numeric($last['volume'] ?? null) && (float)$last['volume'] > 0
            ? self::fmt((float)$last['volume'], 0) : '–';
        $pe = isset($playbook['pe']) && is_float($playbook['pe']) ? self::fmt($playbook['pe'], 1) : '–';
        $cap = isset($playbook['mcap_usd_bn']) && is_float($playbook['mcap_usd_bn'])
            ? self::fmt($playbook['mcap_usd_bn'], 1) . ' mia. USD' : '–';
        $items = [
            ['Åbning', $money((float)$last['open']), 'Kursen ved handelsdagens start (seneste dag i kurshistorikken).'],
            ['Høj', $money((float)$last['high']), 'Dagens højeste kurs.'],
            ['Lav', $money((float)$last['low']), 'Dagens laveste kurs.'],
            ['Volumen', $volume, 'Antal aktier handlet på seneste handelsdag.'],
            ['52 ugers høj', $money($full_year ? $high : null), 'Højeste kurs det seneste år, beregnet ud fra kurshistorikken. Vises kun med mindst et års historik.'],
            ['52 ugers lav', $money($full_year ? $low : null), 'Laveste kurs det seneste år, beregnet ud fra kurshistorikken. Vises kun med mindst et års historik.'],
            ['P/E', $pe, 'Kurs delt med forventet indtjening pr. aktie i dag (EPS) fra Playbook-analysen. Findes kun for analyserede aktier med positiv EPS.'],
            ['Markedsværdi', $cap, 'Selskabets samlede værdi på børsen i milliarder USD, fra Playbook-universet. Findes ikke for alle aktier.'],
        ];
        $html = '<dl class="asc-chart-figures" aria-label="Nøgletal">';
        foreach ($items as [$label, $value, $help]) {
            $html .= '<div title="' . esc_attr($help) . '"><dt>' . esc_html($label) . '</dt><dd>' . esc_html($value) . '</dd></div>';
        }
        $html .= '</dl><p class="asc-subtle">Åbning, høj, lav og volumen er fra seneste handelsdag i historikken ('
            . esc_html(gmdate('d-m-Y', $last_time)) . ').</p>';
        return $html;
    }

    /**
     * Grafen som markup: tom beholder (scriptet bygger knapper og graf), JSON med kurserne, den serverrenderede
     * SVG-graf i <noscript> og nøgletallene. $svg_html er allerede escaped HTML (perioder + ASC_Market_Quotes::stock_chart).
     * @param array<int, array<string, mixed>> $bars Daglige bars, stigende i tid (time, open, high, low, close, volume).
     * @param array<int, array<string, mixed>> $markers [['date' => 'Y-m-d', 'kind' => 'buy'|'sim_buy'|'sim_sell'], ...]
     * @param array{pe: ?float, mcap_usd_bn: ?float} $playbook
     */
    public static function render(string $ticker, array $bars, string $currency, string $period, bool $explicit,
                                  array $markers, bool $limited, string $svg_html, array $playbook): string {
        $rows = [];
        foreach ($bars as $bar) {
            if (!is_array($bar)) { continue; }
            foreach (['time', 'open', 'high', 'low', 'close'] as $key) {
                if (!is_numeric($bar[$key] ?? null)) { continue 2; }
            }
            $rows[] = [(int)$bar['time'], (float)$bar['open'], (float)$bar['high'], (float)$bar['low'],
                (float)$bar['close'], is_numeric($bar['volume'] ?? null) ? (float)$bar['volume'] : 0.0];
        }
        if (count($rows) < 2) { return $svg_html; }
        self::enqueue();

        $clean = [];
        $seen = [];
        foreach ($markers as $marker) {
            $date = is_array($marker) && is_string($marker['date'] ?? null) ? $marker['date'] : '';
            $kind = is_array($marker) && is_string($marker['kind'] ?? null) ? $marker['kind'] : '';
            if (!in_array($kind, self::MARKER_KINDS, true) || preg_match('/^\d{4}-\d\d-\d\d$/D', $date) !== 1) { continue; }
            if (isset($seen[$date . '|' . $kind])) { continue; }
            $seen[$date . '|' . $kind] = true;
            $clean[] = ['date' => $date, 'kind' => $kind];
        }
        $payload = [
            'ticker' => $ticker,
            'currency' => $currency,
            'bars' => $rows,
            'markers' => $clean,
            'period' => $period,
            'explicit' => $explicit,
            'limited' => $limited,
            'intraday' => [
                'url' => esc_url_raw(rest_url('ai-stock-scanner/v1/quotes/intraday')),
                'nonce' => wp_create_nonce('wp_rest'),
            ],
        ];
        $json = wp_json_encode($payload, JSON_HEX_TAG | JSON_HEX_AMP);
        if (!is_string($json)) { return $svg_html; }

        $html = '<div class="asc-chart-app" data-asc-chart hidden></div>';
        $html .= '<script type="application/json" id="asc-chart-data">' . $json . '</script>';
        // Uden JavaScript, og når biblioteket ikke kan indlæses, bruges den enkle SVG-graf. Scriptet henter den herfra.
        $html .= '<noscript data-asc-chart-fallback>' . $svg_html . '</noscript>';
        $html .= '<p class="asc-subtle asc-chart-credit">Interaktiv graf: <a href="https://www.tradingview.com/" '
            . 'target="_blank" rel="noopener noreferrer">TradingView Lightweight Charts&trade;</a>.</p>';
        $html .= self::figures_html($bars, $currency, $playbook);
        return $html;
    }
}
