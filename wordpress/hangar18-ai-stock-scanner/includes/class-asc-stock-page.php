<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Samlet aktieside: søg en aktie frem (symbol eller navn), også en man ikke følger, eller klik på et symbol i en
 * hvilken som helst tabel. Viser kurs, candlegraf med volumen og SMA50/SMA200, brugerens egne køb og salg,
 * playbook-analysen og knapper til Følg, Køb i simulator og Registrér køb.
 *
 * Kun for indloggede. Kurser hentes serverside fra ASC_Market_Quotes og gættes eller opfindes aldrig.
 * Kun visning: siden ændrer intet selv (knapperne bruger de eksisterende handlinger).
 */
final class ASC_Stock_Page {
    private const TICKER_RE = '/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D';
    private const DEFAULT_PERIOD = '6m';
    private const MAX_HITS = 12;
    private const STALE_AFTER = 432000;  // En kurs ældre end 5 dage markeres "gammel".
    private const LIQUID_DAYS = 21;      // Dage i gennemsnittet for en dags handel.
    private const WATCH_MESSAGES = [
        'added' => 'Aktien er tilføjet din overvågningsliste.',
        'removed' => 'Aktien er fjernet fra listen.',
        'exists' => 'Aktien er allerede på listen.',
        'invalid' => 'Ugyldigt aktiesymbol.',
        'limit' => 'Du kan overvåge højst 50 aktier.',
    ];

    public static function register(): void {
        add_shortcode('ai_stock_page', [self::class, 'render']);
        add_action('template_redirect', [self::class, 'private_page_no_cache'], 0);
    }

    /** Siden viser private data (egne køb): ingen delt sidecache. */
    public static function private_page_no_cache(): void {
        if (!is_user_logged_in() || !is_singular()) { return; }
        $content = (string)get_post_field('post_content', get_queried_object_id());
        if (has_shortcode($content, 'ai_stock_page')) {
            if (!defined('DONOTCACHEPAGE')) { define('DONOTCACHEPAGE', true); }
            nocache_headers();
        }
    }

    // ------------------------------------------------------------------ Links

    private static function base_url(): string {
        static $base = null;  // Tabellerne kalder url() én gang pr. række.
        if ($base === null) {
            $base = get_permalink(get_queried_object_id());
            $home_id = (int)get_option('asc_home_page_id', 0);
            // Uden asc_view (en side uden menu) går linket til startsiden, hvor menuen har aktiesiden.
            if (!isset($_GET['asc_view']) && $home_id > 0 && get_post_type($home_id) === 'page') {
                $base = get_permalink($home_id);
            }
            $base = is_string($base) && $base !== '' ? $base : home_url('/');
        }
        return $base;
    }

    /** Adressen på aktiesiden for én aktie (bygget som ASC_Simulator::lookup_url). */
    public static function url(string $ticker): string {
        return add_query_arg(['asc_view' => 'stock', 'asc_ticker' => $ticker], self::base_url()) . '#asc-stock';
    }

    /** Escaped &lt;a&gt; til aktiesiden med symbolet som tekst; et ugyldigt symbol vises som ren tekst. */
    public static function link(string $ticker, ?string $text = null): string {
        $ticker = trim($ticker);
        $label = esc_html($text ?? $ticker);
        if (preg_match(self::TICKER_RE, $ticker) !== 1) { return $label; }
        return '<a class="asc-stock-link" href="' . esc_url(self::url($ticker)) . '">' . $label . '</a>';
    }

    /** Den aktuelle side uden aktiesidens egne parametre (til perioder, søgeresultater og knapper). */
    private static function self_url(): string {
        return remove_query_arg(
            ['asc_stock_q', 'asc_ticker', 'asc_period', 'asc_watch_status'],
            add_query_arg([])
        );
    }

    // ------------------------------------------------------------- Small helpers

    private static function query_text(string $key): string {
        return isset($_GET[$key]) && is_string($_GET[$key])
            ? trim(sanitize_text_field(wp_unslash($_GET[$key]))) : '';
    }

    private static function fmt(float $value, int $decimals = 2): string {
        return number_format($value, $decimals, ',', '.');
    }

    private static function when(int $stamp): string {
        $text = $stamp > 0 ? wp_date('d-m-Y H:i', $stamp) : false;
        return is_string($text) ? $text : '–';
    }

    private static function date_text(string $iso): string {
        return preg_match('/^\d{4}-\d\d-\d\d$/D', $iso) === 1
            ? substr($iso, 8, 2) . '-' . substr($iso, 5, 2) . '-' . substr($iso, 0, 4) : $iso;
    }

    // ------------------------------------------------------------------- Search

    /**
     * Finder aktien bag en søgning: et kendt symbol, et enkelt navnehit eller flere hits. Navne søges i det danske
     * katalog; symboler også i aktierne i playbook-snapshottet. Et gyldigt symbol, der ingen steder er kendt, slås
     * stadig op direkte (kurskilden afgør, om det findes).
     * @return array{ticker: string, hits: array<string, string>, direct: string, message: string}
     */
    private static function resolve(string $query): array {
        $symbol = strtoupper((string)preg_replace('/\s+/', '', $query));
        $valid = preg_match(self::TICKER_RE, $symbol) === 1;
        $known = array_flip(ASC_Playbook::known_tickers());
        $hits = [];
        foreach (ASC_Danish_Catalog::search($query, self::MAX_HITS) as $ticker => $name) {
            $hits[(string)$ticker] = $name;
        }
        if ($valid) {
            foreach (array_keys($known) as $candidate) {
                if (count($hits) >= self::MAX_HITS) { break; }
                $candidate = (string)$candidate;
                if (str_contains($candidate, $symbol) && !isset($hits[$candidate])) { $hits[$candidate] = ''; }
            }
        }
        $result = ['ticker' => '', 'hits' => [], 'direct' => '', 'message' => ''];
        if ($valid && (isset($known[$symbol]) || isset($hits[$symbol]))) {
            $result['ticker'] = $symbol;
        } elseif (count($hits) === 1) {
            $result['ticker'] = (string)array_key_first($hits);
        } elseif (count($hits) > 1) {
            $result['hits'] = $hits;
            $result['direct'] = $valid ? $symbol : '';
        } elseif ($valid) {
            $result['ticker'] = $symbol;
        } else {
            $result['message'] = 'Ingen aktie fundet. Skriv et gyldigt symbol, fx NOVO-B.CO, SAP.DE eller MSFT '
                . '(uden mellemrum), eller en del af et dansk selskabsnavn.';
        }
        return $result;
    }

    private static function render_search(string $value, string $view): void {
        echo '<form class="asc-filter-form asc-stock-search" method="get" action="">';
        if ($view !== '') { echo '<input type="hidden" name="asc_view" value="' . esc_attr($view) . '">'; }
        echo '<label>Symbol eller navn<input type="search" name="asc_stock_q" maxlength="60" '
            . 'placeholder="fx MSFT, NOVO-B.CO eller Harboe" value="' . esc_attr($value) . '"></label>';
        echo '<button type="submit">Find aktie</button></form>';
    }

    /** @param array<string, string> $hits ticker => navn */
    private static function render_hits(array $hits, string $direct): void {
        $self = self::self_url();
        echo '<div class="asc-stock-hits"><p>Flere aktier passer. Vælg en:</p><ul>';
        foreach ($hits as $ticker => $name) {
            $ticker = (string)$ticker;
            echo '<li><a class="asc-stock-link" href="' . esc_url(add_query_arg('asc_ticker', $ticker, $self)) . '">'
                . esc_html($ticker) . '</a>' . ($name !== '' ? ' <span class="asc-subtle">' . esc_html($name) . '</span>' : '') . '</li>';
        }
        echo '</ul>';
        if ($direct !== '') {
            echo '<p class="asc-subtle">Eller <a href="' . esc_url(add_query_arg('asc_ticker', $direct, $self)) . '">slå symbolet '
                . esc_html($direct) . ' op direkte</a>.</p>';
        }
        echo '</div>';
    }

    // ------------------------------------------------------------------ Rendering

    public static function render(): string {
        if (!is_user_logged_in()) {
            $url = wp_login_url(get_permalink());
            return '<p>Log ind for at se aktiesiden. <a href="' . esc_url($url) . '">Log ind</a></p>';
        }
        wp_enqueue_style('hangar18-asc');
        $query = self::query_text('asc_stock_q');
        $query = function_exists('mb_substr') ? mb_substr($query, 0, 60) : substr($query, 0, 60);
        $ticker = strtoupper(self::query_text('asc_ticker'));
        $hits = [];
        $direct = '';
        $message = '';
        if ($query !== '') {
            $found = self::resolve($query);
            $ticker = $found['ticker'];
            $hits = $found['hits'];
            $direct = $found['direct'];
            $message = $found['message'];
        }
        $view = sanitize_key(self::query_text('asc_view'));
        ob_start();
        echo '<section class="asc-dashboard"><div class="asc-portfolio asc-stock" id="asc-stock">';
        echo '<div class="asc-section-title"><h2>Aktie</h2>'
            . '<p>Søg en aktie frem – også en du ikke følger – og se kurs, graf og analyse.</p></div>';
        self::render_search($query !== '' ? $query : $ticker, $view);
        if ($message !== '') {
            echo '<p class="asc-notice-error" role="alert">' . esc_html($message) . '</p>';
        }
        if ($hits) { self::render_hits($hits, $direct); }
        if ($ticker !== '') {
            if (preg_match(self::TICKER_RE, $ticker) !== 1) {
                echo '<p class="asc-notice-error" role="alert">Aktiesymbolet er ugyldigt. '
                    . 'Brug fx NOVO-B.CO, SAP.DE eller MSFT (uden mellemrum).</p>';
            } else {
                self::render_stock(get_current_user_id(), $ticker);
            }
        } elseif ($query === '') {
            echo '<p class="asc-empty">Skriv et symbol eller et navn ovenfor, eller klik på et symbol i en tabel.</p>';
        }
        echo '<p class="asc-disclaimer">Forsinkede kurser. Ikke investeringsrådgivning.</p>';
        echo '</div></section>';
        return (string)ob_get_clean();
    }

    /** Forrige afsluttede dags lukkekurs: er den seneste bar dagens (endnu ikke lukket), bruges barren før. */
    private static function previous_close(array $bars, int $market_time): ?array {
        $count = count($bars);
        if ($count === 0 || $market_time <= 0) { return null; }
        $bar = $bars[$count - 1];
        if (gmdate('Y-m-d', (int)$bar['time']) >= gmdate('Y-m-d', $market_time)) {
            if ($count < 2) { return null; }
            $bar = $bars[$count - 2];
        }
        $close = (float)$bar['close'];
        return $close > 0 ? ['close' => $close, 'date' => gmdate('Y-m-d', (int)$bar['time'])] : null;
    }

    /** Gennemsnit af lukkekurs × volumen over de seneste dage (i aktiens valuta); null uden volumen. */
    private static function daily_turnover(array $bars): ?float {
        $sum = 0.0;
        $days = 0;
        foreach (array_slice($bars, -self::LIQUID_DAYS) as $bar) {
            if (!is_array($bar) || !is_numeric($bar['close'] ?? null) || !is_numeric($bar['volume'] ?? null)) { continue; }
            $sum += (float)$bar['close'] * (float)$bar['volume'];
            $days++;
        }
        $value = $days > 0 ? $sum / $days : null;
        return $value !== null && is_finite($value) && $value > 0 ? $value : null;
    }

    private static function render_stock(int $user_id, string $ticker): void {
        $period = sanitize_key(self::query_text('asc_period'));
        $period_explicit = array_key_exists($period, ASC_Market_Quotes::PERIOD_DAYS);
        if (!$period_explicit) { $period = self::DEFAULT_PERIOD; }
        $self = self::self_url();
        $enabled = ASC_Market_Quotes::enabled();
        $quote = ASC_Market_Quotes::get($ticker);
        $long = ASC_Market_Quotes::history($ticker);
        $lots = ASC_Portfolio::lots_for($user_id, $ticker);
        $sim = ASC_Simulator::trades_for($user_id, $ticker);
        $followed = ASC_Watchlist::is_followed($ticker);

        // Historik: fem år hvis den kunne hentes, ellers de seks måneder fra kursopslaget (og det siges).
        $bars = [];
        $fallback = false;
        $currency = '';
        if ($long !== null) {
            $bars = $long['bars'];
            $currency = $long['currency'];
        } elseif (is_array($quote) && is_array($quote['history'] ?? null) && $quote['history']) {
            $bars = $quote['history'];
            $fallback = true;
        }
        if (is_array($quote)) { $currency = strtoupper((string)($quote['currency'] ?? $currency)); }

        $name = ASC_Danish_Catalog::name_for($ticker);
        if ($name === null && $lots && is_string($lots[0]['label'] ?? null) && $lots[0]['label'] !== '') {
            $name = (string)$lots[0]['label'];
        }

        // ---- Overskrift, kurs og dagens ændring
        echo '<h3 class="asc-stock-title">' . esc_html($ticker) . ($name !== null ? ' – ' . esc_html($name) : '') . '</h3>';
        if (is_array($quote)) {
            $price = (float)$quote['price'];
            $time = (int)($quote['market_time'] ?? 0);
            $stale = !empty($quote['stale']) || $time < time() - self::STALE_AFTER;
            echo '<div class="asc-stock-quote"><strong class="asc-stock-price">' . esc_html(self::fmt($price)) . ' '
                . esc_html($currency) . '</strong> <span class="asc-subtle">kurstidspunkt ' . esc_html(self::when($time))
                . ($stale ? ' – gammel kurs' : '') . '</span>';
            $previous = self::previous_close($bars !== [] ? $bars : (is_array($quote['history'] ?? null) ? $quote['history'] : []), $time);
            if ($previous !== null) {
                $change = $price - $previous['close'];
                $percent = $change / $previous['close'] * 100;
                echo '<div class="' . esc_attr($change >= 0 ? 'asc-positive' : 'asc-negative') . '">'
                    . esc_html(($change > 0 ? '+' : '') . self::fmt($change) . ' ' . $currency . ' ('
                        . ($percent > 0 ? '+' : '') . self::fmt($percent) . ' %)')
                    . ' <span class="asc-subtle">siden forrige lukkekurs ' . esc_html(self::date_text($previous['date']))
                    . '</span></div>';
            }
            echo '</div>';
        } elseif (!$enabled) {
            echo '<p class="asc-warning" role="alert">Kurser mangler: Yahoo-kurser skal aktiveres af administratoren '
                . '(AI Stock Scanner → Forbindelse). Playbook-analysen nedenfor vises stadig, hvis den findes.</p>';
        } else {
            echo '<p class="asc-warning" role="alert">Ingen kurs tilgængelig for ' . esc_html($ticker)
                . ' (symbolet findes ikke, eller kurskilden svarer ikke lige nu). Der vises aldrig gættede kurser.</p>';
        }
        $facts = ASC_Playbook::size_liquidity_html($ticker);
        if ($facts !== '') { echo '<p class="asc-stock-facts">' . $facts . '</p>'; }
        $turnover = self::daily_turnover($bars);
        if ($turnover !== null) {
            echo '<p>En dags handel &asymp; <strong>' . esc_html(self::fmt($turnover, 0) . ' ' . $currency) . '</strong> '
                . '<span class="asc-subtle">(gennemsnit af lukkekurs &times; volumen, seneste '
                . esc_html((string)self::LIQUID_DAYS) . ' dage)</span></p>';
        }
        if ($lots || $sim['open']) {
            echo '<p class="asc-subtle">Du ejer aktien: ' . esc_html((string)count($lots)) . ' køb i porteføljen og '
                . esc_html((string)count($sim['open'])) . ' åben position i simulatoren.</p>';
        }

        // ---- Graf med perioder og markører
        // Periodevalget med links og SVG-grafen er den serverrenderede udgave: den vises uden JavaScript og når
        // biblioteket til den interaktive graf ikke kan indlæses (ASC_Stock_Chart lægger den i <noscript>).
        $tabs = '<nav class="asc-pb-tabs" aria-label="Periode">';
        foreach (ASC_Market_Quotes::PERIOD_LABELS as $key => $label) {
            $tabs .= '<a class="asc-pb-tab' . ($period === $key ? ' is-active' : '') . '" href="'
                . esc_url(add_query_arg(['asc_ticker' => $ticker, 'asc_period' => $key], $self) . '#asc-stock-chart') . '"'
                . ($period === $key ? ' aria-current="page"' : '') . '>' . esc_html($label) . '</a>';
        }
        $tabs .= '</nav>';
        $limited_text = '<p class="asc-warning">Den lange historik (5 år) kunne ikke hentes lige nu. Grafen bruger de seneste '
            . 'ca. 6 måneder fra kursopslaget; SMA200 kræver mindst 200 handelsdage og kan mangle.</p>';
        echo '<div id="asc-stock-chart">';
        if (!$bars) { echo $tabs; }
        if ($bars) {
            if ($fallback) { echo $limited_text; }
            $markers = [];
            foreach ($lots as $lot) {
                $markers[] = ['date' => (string)($lot['buy_date'] ?? ''), 'kind' => 'buy'];
            }
            foreach ($sim['open'] as $position) {
                $markers[] = ['date' => (string)($position['buy_date'] ?? ''), 'kind' => 'sim_buy'];
            }
            foreach ($sim['closed'] as $trade) {
                $markers[] = ['date' => (string)($trade['buy_date'] ?? ''), 'kind' => 'sim_buy'];
                $markers[] = ['date' => (string)($trade['sell_date'] ?? ''), 'kind' => 'sim_sell'];
            }
            $svg_html = $tabs . ASC_Market_Quotes::stock_chart($ticker, $bars, $currency, $period, $markers);
            echo ASC_Stock_Chart::render($ticker, $bars, $currency, $period, $period_explicit, $markers, $fallback,
                $svg_html, ASC_Playbook::key_figures($ticker));
        } elseif ($enabled) {
            echo '<p class="asc-warning">Ingen kurshistorik tilgængelig for ' . esc_html($ticker) . ' lige nu.</p>';
        } else {
            echo '<p class="asc-subtle">Grafen kræver aktiverede Yahoo-kurser.</p>';
        }
        echo '</div>';

        // ---- Playbook-analyse, regnskab, salgsregel og nyheder
        $owned = [];
        foreach ($lots as $lot) {
            $owned[] = ['source' => 'Portefølje', 'buy_date' => (string)($lot['buy_date'] ?? '')];
        }
        foreach ($sim['open'] as $position) {
            $owned[] = ['source' => 'Simulator', 'buy_date' => (string)($position['buy_date'] ?? '')];
        }
        echo ASC_Playbook::stock_page_analysis($ticker, $owned);

        // ---- Knapper: Følg, Køb i simulator, Registrér køb
        $status = sanitize_key(self::query_text('asc_watch_status'));
        echo '<div class="asc-stock-actions" id="asc-watchlist">';
        if (isset(self::WATCH_MESSAGES[$status])) {
            echo '<p role="status" class="asc-notice">' . esc_html(self::WATCH_MESSAGES[$status]) . '</p>';
        }
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="' . ($followed ? 'asc_watch_remove' : 'asc_watch_add') . '">';
        echo '<input type="hidden" name="asc_watch_ticker" value="' . esc_attr($ticker) . '">';
        wp_nonce_field($followed ? 'asc_watch_remove' : 'asc_watch_add');
        echo $followed
            ? '<span class="asc-subtle">Du følger aktien.</span> <button type="submit" class="asc-delete">Fjern fra overvågningslisten</button>'
            : '<button type="submit">Følg</button>';
        echo '</form>';
        echo '<a class="asc-stock-btn" href="' . esc_url(ASC_Simulator::lookup_url($ticker)) . '">Køb i simulator</a>';
        $args = ['asc_view' => 'portfolio', 'asc_ticker' => $ticker];
        if ($name !== null) {
            $args['asc_name'] = function_exists('mb_substr') ? mb_substr($name, 0, 80) : substr($name, 0, 80);
        }
        if (preg_match('/^(DKK|SEK|NOK|EUR|USD)$/D', $currency) === 1) { $args['asc_currency'] = $currency; }
        echo '<a class="asc-stock-btn" href="' . esc_url(add_query_arg($args, self::base_url()) . '#asc-add-position')
            . '">Registrér køb</a>';
        echo '</div>';
    }
}
