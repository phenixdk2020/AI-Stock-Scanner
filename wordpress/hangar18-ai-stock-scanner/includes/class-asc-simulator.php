<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * Per-user virtual trading simulator ("børs og portefølje"): the user looks up
 * stocks, reads the Playbook analysis, buys them virtually, follows prices for
 * a round of 30 days and sees the result against the RSP benchmark.
 *
 * Prices are ALWAYS taken server-side from ASC_Market_Quotes (never from a form)
 * and are never invented. Virtual trades only; not investment advice.
 */
final class ASC_Simulator {
    public const META = 'asc_simulator_v1';
    private const TICKER_RE = '/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D';
    private const DATE_RE = '/^\d{4}-\d\d-\d\d$/D';
    private const START_CASH = 1000000.0;
    private const MIN_CASH = 10000.0;
    private const MAX_CASH = 1000000000.0;
    private const ROUND_DAYS = 30;
    private const TARGET_POSITIONS = 10;
    private const MAX_POSITIONS = 20;
    private const MAX_HISTORY = 50;
    private const MAX_CLOSED = 200;
    private const FEE_RATE = 0.001;      // 0,1 % of the amount on every buy and sell.
    private const BENCHMARK = 'RSP';
    private const STALE_AFTER = 432000;  // A quote older than 5 days is marked "gammel".
    private const LIQUID_DAYS = 21;      // Dage i gennemsnittet for en dags handel.
    private const THIN_TRADE_DKK = 14000000.0; // Under ca. 2 mio. USD om dagen advares der (køb blokeres ikke).
    /** @var array<string, array|null> */
    private static array $quote_cache = [];

    public static function register(): void {
        add_shortcode('ai_stock_simulator', [self::class, 'render']);
        add_action('template_redirect', [self::class, 'private_page_no_cache'], 0);
        add_action('admin_post_asc_sim_start', [self::class, 'start_round']);
        add_action('admin_post_asc_sim_buy', [self::class, 'buy']);
        add_action('admin_post_asc_sim_sell', [self::class, 'sell']);
        add_action('admin_post_asc_sim_end', [self::class, 'end_round']);
    }

    /** Prevent shared page caches from showing a user's virtual portfolio to others. */
    public static function private_page_no_cache(): void {
        if (!is_user_logged_in() || !is_singular()) { return; }
        $content = (string)get_post_field('post_content', get_queried_object_id());
        if (has_shortcode($content, 'ai_stock_simulator')) {
            if (!defined('DONOTCACHEPAGE')) { define('DONOTCACHEPAGE', true); }
            nocache_headers();
        }
    }

    // ------------------------------------------------------------------ Links

    /** URL of the simulator's lookup for one ticker (used by the Playbook rows). */
    public static function lookup_url(string $ticker): string {
        static $base = null;  // The Playbook calls this once per row.
        if ($base === null) {
            $base = get_permalink(get_queried_object_id());
            $home_id = (int)get_option('asc_home_page_id', 0);
            // Outside the home page (no asc_view) go to the home page, where the menu has the simulator.
            if (!isset($_GET['asc_view']) && $home_id > 0 && get_post_type($home_id) === 'page') {
                $base = get_permalink($home_id);
            }
            $base = is_string($base) && $base !== '' ? $base : home_url('/');
        }
        return add_query_arg(['asc_view' => 'simulator', 'asc_sim_ticker' => $ticker], $base) . '#asc-simulator';
    }

    // ------------------------------------------------------------- Small helpers

    private static function field(string $key): string {
        $value = $_POST[$key] ?? '';
        return is_string($value) ? trim(sanitize_text_field(wp_unslash($value))) : '';
    }

    private static function query_text(string $key): string {
        return isset($_GET[$key]) && is_string($_GET[$key])
            ? trim(sanitize_text_field(wp_unslash($_GET[$key]))) : '';
    }

    /** Accepts 1000000, 1.000.000 and 1.000.000,50; rejects everything else. */
    private static function decimal(string $raw): ?float {
        $raw = str_replace([' ', "\u{00A0}"], '', trim($raw));
        if ($raw === '') { return null; }
        if (str_contains($raw, ',')) { $raw = str_replace(',', '.', str_replace('.', '', $raw)); }
        elseif (preg_match('/^\d{1,3}(?:\.\d{3})+$/D', $raw) === 1) { $raw = str_replace('.', '', $raw); }
        if (preg_match('/^[0-9]+(?:\.[0-9]+)?$/D', $raw) !== 1) { return null; }
        $value = (float)$raw;
        return is_finite($value) ? $value : null;
    }

    /** Escaped-by-caller number in Danish format. */
    private static function fmt(float $value, int $decimals = 2): string {
        return number_format($value, $decimals, ',', '.');
    }

    private static function signed(float $value, int $decimals = 2): string {
        return ($value > 0 ? '+' : '') . self::fmt($value, $decimals);
    }

    private static function fmt_quantity(float $value): string {
        if ($value === floor($value)) { return number_format($value, 0, ',', '.'); }
        return rtrim(rtrim(number_format($value, 6, ',', '.'), '0'), ',');
    }

    private static function when(int $stamp): string {
        $text = $stamp > 0 ? wp_date('d-m-Y H:i', $stamp) : false;
        return is_string($text) ? $text : '–';
    }

    private static function today(): string {
        $today = wp_date('Y-m-d');
        return is_string($today) ? $today : gmdate('Y-m-d');
    }

    private static function elapsed_days(string $started): int {
        $from = DateTimeImmutable::createFromFormat('!Y-m-d', $started);
        $to = DateTimeImmutable::createFromFormat('!Y-m-d', self::today());
        if (!($from instanceof DateTimeImmutable) || !($to instanceof DateTimeImmutable)) { return 0; }
        return max(0, (int)$from->diff($to)->format('%r%a'));
    }

    // ------------------------------------------------------------------- Storage

    /** @return array{round: ?array, history: array} */
    private static function load(int $user_id): array {
        $raw = get_user_meta($user_id, self::META, true);
        $raw = is_array($raw) ? $raw : [];
        $history = is_array($raw['history'] ?? null) ? array_values(array_filter($raw['history'], 'is_array')) : [];
        return [
            'round' => is_array($raw['round'] ?? null) ? self::clean_round($raw['round']) : null,
            'history' => $history,
        ];
    }

    private static function clean_round(array $raw): ?array {
        $started = $raw['started'] ?? null;
        if (!is_string($started) || preg_match(self::DATE_RE, $started) !== 1) { return null; }
        $start_cash = is_numeric($raw['start_cash_dkk'] ?? null) && (float)$raw['start_cash_dkk'] > 0
            ? (float)$raw['start_cash_dkk'] : self::START_CASH;
        $cash = is_numeric($raw['cash_dkk'] ?? null) ? (float)$raw['cash_dkk'] : $start_cash;
        $bench = is_numeric($raw['benchmark_start'] ?? null) && (float)$raw['benchmark_start'] > 0
            ? (float)$raw['benchmark_start'] : null;
        return [
            'started' => $started,
            'start_cash_dkk' => $start_cash,
            'cash_dkk' => $cash,
            'benchmark_start' => $bench,
            'positions' => is_array($raw['positions'] ?? null)
                ? array_values(array_filter($raw['positions'], 'is_array')) : [],
            'closed' => is_array($raw['closed'] ?? null)
                ? array_values(array_filter($raw['closed'], 'is_array')) : [],
        ];
    }

    private static function save(int $user_id, array $state): void {
        update_user_meta($user_id, self::META, [
            'round' => $state['round'],
            'history' => array_slice(array_values($state['history']), 0, self::MAX_HISTORY),
        ]);
    }

    // ------------------------------------------------------------- Prices and FX

    /**
     * Latest quote for a ticker, taken server-side. Null when there is none.
     * @return array{price: float, currency: string, time: int, stale: bool, history: array}|null
     */
    private static function price_for(string $ticker): ?array {
        if (array_key_exists($ticker, self::$quote_cache)) { return self::$quote_cache[$ticker]; }
        $result = null;
        $quote = ASC_Market_Quotes::get($ticker);
        if (is_array($quote) && is_numeric($quote['price'] ?? null) && (float)$quote['price'] > 0) {
            $currency = strtoupper((string)($quote['currency'] ?? ''));
            if (preg_match('/^[A-Z]{3}$/D', $currency) === 1) {
                $time = (int)($quote['market_time'] ?? 0);
                $result = [
                    'price' => (float)$quote['price'],
                    'currency' => $currency,
                    'time' => $time,
                    'stale' => !empty($quote['stale']) || $time < time() - self::STALE_AFTER,
                    'history' => is_array($quote['history'] ?? null) ? $quote['history'] : [],
                ];
            }
        }
        self::$quote_cache[$ticker] = $result;
        return $result;
    }

    /** Gennemsnit af lukkekurs × volumen i kr. over de seneste dage; null uden volumen i kurshistorikken. */
    private static function daily_turnover_dkk(array $history, float $fx): ?float {
        $sum = 0.0;
        $days = 0;
        foreach (array_slice($history, -self::LIQUID_DAYS) as $bar) {
            if (!is_array($bar) || !is_numeric($bar['close'] ?? null) || !is_numeric($bar['volume'] ?? null)) { continue; }
            $sum += (float)$bar['close'] * (float)$bar['volume'];
            $days++;
        }
        $value = $days > 0 ? $sum / $days * $fx : null;
        return $value !== null && is_finite($value) ? $value : null;
    }

    /** DKK per unit of the currency (ECB), or null when unavailable. */
    private static function fx(string $currency): ?float {
        $rate = ASC_FX_Rates::to_dkk($currency);
        if ($rate === null) { return null; }
        $value = (float)$rate['rate'];
        return is_finite($value) && $value > 0 ? $value : null;
    }

    // --------------------------------------------------------------- Calculations

    /**
     * Value of the current round at the latest quotes. Positions without a usable
     * quote are shown at their purchase value and counted in "unpriced".
     * @return array{rows: array, positions_value: float, total: float, gain: float, pct: float, unpriced: int}
     */
    private static function valuation(array $round): array {
        $rows = [];
        $positions_value = 0.0;
        $unpriced = 0;
        foreach ($round['positions'] as $position) {
            $ticker = (string)($position['ticker'] ?? '');
            $quantity = (float)($position['quantity'] ?? 0);
            $buy_price = (float)($position['buy_price'] ?? 0);
            $currency = (string)($position['currency'] ?? '');
            $buy_fx = (float)($position['fx_to_dkk'] ?? 0);
            $fee = (float)($position['fee_dkk'] ?? 0);
            if ($ticker === '' || $quantity <= 0 || $buy_price <= 0 || $buy_fx <= 0) { continue; }
            $cost = $quantity * $buy_price * $buy_fx + $fee;
            $quote = self::price_for($ticker);
            $priced = $quote !== null && $quote['currency'] === $currency;
            $fx_now = $currency === 'DKK' ? 1.0 : (self::fx($currency) ?? $buy_fx);
            $value = $priced ? $quantity * (float)$quote['price'] * $fx_now : $quantity * $buy_price * $buy_fx;
            if (!$priced) { $unpriced++; }
            $gain = $value - $cost;
            $positions_value += $value;
            $rows[] = [
                'id' => (string)($position['id'] ?? ''),
                'ticker' => $ticker,
                'quantity' => $quantity,
                'buy_price' => $buy_price,
                'buy_date' => (string)($position['buy_date'] ?? ''),
                'currency' => $currency,
                'price' => $priced ? (float)$quote['price'] : null,
                'time' => $priced ? (int)$quote['time'] : 0,
                'stale' => $priced && $quote['stale'],
                'value' => $value,
                'gain' => $gain,
                'pct' => $cost > 0 ? $gain / $cost * 100 : 0.0,
            ];
        }
        $total = (float)$round['cash_dkk'] + $positions_value;
        $start = (float)$round['start_cash_dkk'];
        return [
            'rows' => $rows,
            'positions_value' => $positions_value,
            'total' => $total,
            'gain' => $total - $start,
            'pct' => $start > 0 ? ($total / $start - 1) * 100 : 0.0,
            'unpriced' => $unpriced,
        ];
    }

    /**
     * RSP return since the round started. The start price is the quote stored at
     * the start; if it was missing, the close of the last trading day on or before
     * the start date is used. Null when it cannot be computed.
     * @return array{return: ?float, from_history: bool}
     */
    private static function benchmark(array $round): array {
        $quote = self::price_for(self::BENCHMARK);
        $start = is_numeric($round['benchmark_start'] ?? null) && (float)$round['benchmark_start'] > 0
            ? (float)$round['benchmark_start'] : null;
        $from_history = false;
        if ($start === null && $quote !== null) {
            foreach ($quote['history'] as $bar) {
                if (!is_array($bar) || !is_numeric($bar['time'] ?? null) || !is_numeric($bar['close'] ?? null)) { continue; }
                if (gmdate('Y-m-d', (int)$bar['time']) <= (string)$round['started'] && (float)$bar['close'] > 0) {
                    $start = (float)$bar['close'];
                    $from_history = true;
                }
            }
        }
        if ($start === null || $quote === null) { return ['return' => null, 'from_history' => false]; }
        return ['return' => ($quote['price'] / $start - 1) * 100, 'from_history' => $from_history];
    }

    // ------------------------------------------------------------------- Actions

    private static function guard(string $nonce_action): int {
        if (!is_user_logged_in()) { auth_redirect(); exit; }
        check_admin_referer($nonce_action);
        return get_current_user_id();
    }

    /** One-time per-user status shown (and removed) on the next page view. */
    private static function flash_key(): string {
        return 'asc_sim_flash_' . get_current_user_id();
    }

    private static function redirect(string $status, string $ticker = ''): void {
        set_transient(self::flash_key(), $status, 180);
        $referer = wp_get_referer();
        $url = is_string($referer) && $referer !== ''
            ? wp_validate_redirect($referer, home_url('/')) : home_url('/');
        $url = remove_query_arg('asc_sim_ticker', $url);
        if ($ticker !== '') { $url = add_query_arg('asc_sim_ticker', $ticker, $url); }
        wp_safe_redirect($url . '#asc-simulator');
        exit;
    }

    public static function start_round(): void {
        $user_id = self::guard('asc_sim_start');
        $state = self::load($user_id);
        if ($state['round'] !== null) { self::redirect('round_exists'); }
        $cash = self::decimal(self::field('asc_sim_cash'));
        if ($cash === null || $cash < self::MIN_CASH || $cash > self::MAX_CASH) { self::redirect('invalid_amount'); }
        $cash = round((float)$cash, 2);
        $benchmark = self::price_for(self::BENCHMARK);
        $state['round'] = [
            'started' => self::today(),
            'start_cash_dkk' => $cash,
            'cash_dkk' => $cash,
            'benchmark_start' => $benchmark !== null ? $benchmark['price'] : null,
            'positions' => [],
            'closed' => [],
        ];
        self::save($user_id, $state);
        self::redirect('started');
    }

    public static function buy(): void {
        $user_id = self::guard('asc_sim_buy');
        $ticker = strtoupper(self::field('asc_sim_ticker'));
        if (preg_match(self::TICKER_RE, $ticker) !== 1) { self::redirect('invalid_ticker'); }
        $amount = self::decimal(self::field('asc_sim_amount'));
        if ($amount === null || $amount <= 0 || $amount > self::MAX_CASH) { self::redirect('invalid_buy_amount', $ticker); }
        $state = self::load($user_id);
        $round = $state['round'];
        if ($round === null) { self::redirect('no_round'); }
        if (self::elapsed_days((string)$round['started']) >= self::ROUND_DAYS) { self::redirect('round_over'); }
        if (count($round['positions']) >= self::MAX_POSITIONS) { self::redirect('max_positions', $ticker); }
        foreach ($round['positions'] as $position) {
            if (($position['ticker'] ?? '') === $ticker) { self::redirect('already_held', $ticker); }
        }
        $quote = self::price_for($ticker);
        if ($quote === null) { self::redirect('no_quote', $ticker); }
        $fx = self::fx($quote['currency']);
        if ($fx === null) { self::redirect('no_fx', $ticker); }
        $unit_dkk = $quote['price'] * (float)$fx;
        if (!is_finite($unit_dkk) || $unit_dkk <= 0) { self::redirect('no_quote', $ticker); }
        $quantity = floor((float)$amount / $unit_dkk);
        if (!is_finite($quantity) || $quantity < 1) { self::redirect('qty_zero', $ticker); }
        $cost = $quantity * $unit_dkk;
        $fee = $cost * self::FEE_RATE;
        if ($cost + $fee > (float)$round['cash_dkk'] + 0.005) { self::redirect('no_cash', $ticker); }
        $round['positions'][] = [
            'id' => wp_generate_uuid4(),
            'ticker' => $ticker,
            'quantity' => $quantity,
            'buy_price' => $quote['price'],
            'currency' => $quote['currency'],
            'buy_date' => self::today(),
            'fx_to_dkk' => (float)$fx,
            'fee_dkk' => $fee,
        ];
        $round['cash_dkk'] = round((float)$round['cash_dkk'] - $cost - $fee, 2);
        $state['round'] = $round;
        self::save($user_id, $state);
        self::redirect('bought');
    }

    public static function sell(): void {
        $user_id = self::guard('asc_sim_sell');
        $id = self::field('asc_sim_position_id');
        $state = self::load($user_id);
        $round = $state['round'];
        if ($round === null) { self::redirect('no_round'); }
        if (self::elapsed_days((string)$round['started']) >= self::ROUND_DAYS) { self::redirect('round_over'); }
        $index = null;
        foreach ($round['positions'] as $i => $position) {
            if ($id !== '' && (string)($position['id'] ?? '') === $id) { $index = $i; break; }
        }
        if ($index === null) { self::redirect('notfound'); }
        $position = $round['positions'][$index];
        $ticker = (string)($position['ticker'] ?? '');
        $currency = (string)($position['currency'] ?? '');
        $quantity = (float)($position['quantity'] ?? 0);
        $buy_price = (float)($position['buy_price'] ?? 0);
        $buy_fx = (float)($position['fx_to_dkk'] ?? 0);
        $buy_fee = (float)($position['fee_dkk'] ?? 0);
        if ($ticker === '' || $quantity <= 0 || $buy_price <= 0 || $buy_fx <= 0) { self::redirect('notfound'); }
        $quote = self::price_for($ticker);
        if ($quote === null || $quote['currency'] !== $currency) { self::redirect('no_quote'); }
        $sell_fx = self::fx($currency);
        if ($sell_fx === null) { self::redirect('no_fx'); }
        $proceeds = $quantity * $quote['price'] * (float)$sell_fx;
        $sell_fee = $proceeds * self::FEE_RATE;
        $pnl = ($proceeds - $sell_fee) - ($quantity * $buy_price * $buy_fx + $buy_fee);
        $round['closed'][] = [
            'ticker' => $ticker,
            'quantity' => $quantity,
            'buy_price' => $buy_price,
            'sell_price' => $quote['price'],
            'currency' => $currency,
            'buy_date' => (string)($position['buy_date'] ?? ''),
            'sell_date' => self::today(),
            'buy_fx' => $buy_fx,
            'sell_fx' => (float)$sell_fx,
            'buy_fee_dkk' => $buy_fee,
            'sell_fee_dkk' => $sell_fee,
            'pnl_dkk' => $pnl,
        ];
        $round['closed'] = array_slice($round['closed'], -self::MAX_CLOSED);
        unset($round['positions'][$index]);
        $round['positions'] = array_values($round['positions']);
        $round['cash_dkk'] = round((float)$round['cash_dkk'] + $proceeds - $sell_fee, 2);
        $state['round'] = $round;
        self::save($user_id, $state);
        self::redirect('sold');
    }

    /** Finish the round after day 30: store the summary in history, then a new round can start. */
    public static function end_round(): void {
        $user_id = self::guard('asc_sim_end');
        $state = self::load($user_id);
        $round = $state['round'];
        if ($round === null) { self::redirect('no_round'); }
        if (self::elapsed_days((string)$round['started']) < self::ROUND_DAYS) { self::redirect('round_not_over'); }
        $valuation = self::valuation($round);
        $benchmark = self::benchmark($round);
        array_unshift($state['history'], [
            'started' => (string)$round['started'],
            'ended' => self::today(),
            'start_value' => (float)$round['start_cash_dkk'],
            'end_value' => $valuation['total'],
            'return_pct' => $valuation['pct'],
            'rsp_return_pct' => $benchmark['return'],
            'trades' => count($round['closed']) * 2 + count($round['positions']),
            'unpriced' => $valuation['unpriced'],
        ]);
        $state['round'] = null;
        self::save($user_id, $state);
        self::redirect('ended');
    }

    // ------------------------------------------------------------------ Rendering

    public static function render(): string {
        if (!is_user_logged_in()) {
            $url = wp_login_url(get_permalink());
            return '<p>Log ind for at bruge simulatoren. <a href="' . esc_url($url) . '">Log ind</a></p>';
        }
        wp_enqueue_style('hangar18-asc');
        $user_id = get_current_user_id();
        $state = self::load($user_id);
        $round = $state['round'];
        ob_start();
        echo '<section class="asc-dashboard"><div class="asc-portfolio asc-simulator" id="asc-simulator">';
        echo '<div class="asc-section-title"><h2>Simulator</h2>'
            . '<p>Find aktier, læs Playbook-analysen, køb dem virtuelt og følg kurserne i 30 dage.</p></div>';
        self::render_flash();
        if (!ASC_Market_Quotes::enabled()) {
            echo '<div class="asc-warning" role="alert">Kurser mangler: Yahoo-kurser skal aktiveres af administratoren '
                . '(AI Stock Scanner → Forbindelse), før der kan handles i simulatoren.</div>';
        }
        if ($round === null) {
            self::render_start_form();
        } else {
            $valuation = self::valuation($round);
            $benchmark = self::benchmark($round);
            $day = self::elapsed_days((string)$round['started']);
            $finished = $day >= self::ROUND_DAYS;
            self::render_overview($round, $valuation, $benchmark, $day);
            if ($finished) {
                self::render_end_block($valuation, $benchmark);
            } else {
                self::render_lookup($round);
            }
            self::render_positions($valuation, $finished);
            self::render_closed($round);
        }
        self::render_history($state['history']);
        echo '<p class="asc-disclaimer">Virtuelle handler med forsinkede kurser. Ikke investeringsrådgivning.</p>';
        echo ASC_Market_Quotes::auto_refresh_markup();
        echo '</div></section>';
        return (string)ob_get_clean();
    }

    private static function render_flash(): void {
        $status = get_transient(self::flash_key());
        delete_transient(self::flash_key());
        $status = is_string($status) ? sanitize_key($status) : '';
        $messages = [
            'started' => 'Ny runde er startet.',
            'bought' => 'Aktien er købt virtuelt til seneste kurs.',
            'sold' => 'Aktien er solgt virtuelt til seneste kurs.',
            'ended' => 'Runden er afsluttet og gemt i historikken. Du kan starte en ny runde.',
            'invalid_amount' => 'Startbeløbet skal være mellem 10.000 og 1.000.000.000 kr.',
            'round_exists' => 'Der kører allerede en runde.',
            'no_round' => 'Der er ingen aktiv runde. Start en runde først.',
            'round_over' => 'Runden er slut. Afslut den, og start en ny for at handle videre.',
            'round_not_over' => 'Runden er ikke slut endnu.',
            'invalid_ticker' => 'Aktiesymbolet er ugyldigt. Brug fx NOVO-B.CO, SAP.DE eller MSFT (uden mellemrum).',
            'invalid_buy_amount' => 'Beløbet skal være et positivt tal i kr., fx 100.000.',
            'max_positions' => 'Du har nået det højeste antal positioner (20). Sælg en aktie først.',
            'already_held' => 'Du ejer allerede denne aktie i runden.',
            'no_quote' => 'Der findes ingen kurs på aktien lige nu (eller kursen er i en anden valuta end købet). Der handles aldrig uden kurs.',
            'no_fx' => 'Der findes ingen valutakurs til DKK for aktiens valuta (understøtter DKK, EUR, USD, SEK og NOK).',
            'qty_zero' => 'Beløbet rækker ikke til en hel aktie.',
            'no_cash' => 'Der er ikke kontanter nok (husk handelsomkostningen på 0,1 %).',
            'notfound' => 'Kunne ikke finde positionen.',
        ];
        if (!isset($messages[$status])) { return; }
        $ok = in_array($status, ['started', 'bought', 'sold', 'ended'], true);
        echo '<div class="asc-notice ' . ($ok ? 'asc-notice-ok' : 'asc-notice-error')
            . '" role="' . ($ok ? 'status' : 'alert') . '"><strong>'
            . ($ok ? 'OK: ' : 'Fejl: ') . esc_html($messages[$status]) . '</strong></div>';
    }

    private static function render_start_form(): void {
        echo '<div class="asc-add-position asc-sim-start"><h3>Start en runde</h3>';
        echo '<p class="asc-subtle">En runde varer ' . esc_html((string)self::ROUND_DAYS) . ' dage. Mål: '
            . esc_html((string)self::TARGET_POSITIONS) . ' aktier (højst ' . esc_html((string)self::MAX_POSITIONS)
            . '). Handelsomkostning: ' . esc_html(self::fmt(self::FEE_RATE * 100, 1))
            . ' % af beløbet ved hvert køb og salg. Afkastet sammenlignes med RSP (S&amp;P 500 equal weight).</p>';
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_sim_start">';
        wp_nonce_field('asc_sim_start');
        echo '<label>Startbeløb (kr.)<input type="text" name="asc_sim_cash" inputmode="decimal" placeholder="fx '
            . esc_attr(self::fmt(self::START_CASH, 0)) . '" required></label>';
        echo '<p class="asc-subtle">Du vælger selv beløbet: mellem ' . esc_html(self::fmt(self::MIN_CASH, 0))
            . ' og ' . esc_html(self::fmt(self::MAX_CASH, 0)) . ' kr.</p>';
        echo '<button type="submit">Start runde</button></form></div>';
    }

    private static function render_overview(array $round, array $valuation, array $benchmark, int $day): void {
        $gain = (float)$valuation['gain'];
        $pct = (float)$valuation['pct'];
        $rsp = $benchmark['return'];
        $class = $gain >= 0 ? 'asc-positive' : 'asc-negative';
        $count = count($valuation['rows']);
        echo '<div class="asc-sim-metrics">';
        echo '<div><span>Kontanter</span><strong>' . esc_html(self::fmt((float)$round['cash_dkk'])) . ' kr.</strong></div>';
        echo '<div><span>Værdi af positioner</span><strong>' . esc_html(self::fmt((float)$valuation['positions_value'])) . ' kr.</strong></div>';
        echo '<div><span>Samlet værdi</span><strong>' . esc_html(self::fmt((float)$valuation['total'])) . ' kr.</strong>'
            . '<small>Start: ' . esc_html(self::fmt((float)$round['start_cash_dkk'])) . ' kr.</small></div>';
        echo '<div><span>Gevinst / tab</span><strong class="' . esc_attr($class) . '">'
            . esc_html(self::signed($gain) . ' kr.') . '</strong><small class="' . esc_attr($class) . '">'
            . esc_html(self::signed($pct) . ' %') . '</small></div>';
        echo '<div><span>RSP siden start</span><strong>'
            . ($rsp === null ? '–' : esc_html(self::signed((float)$rsp) . ' %')) . '</strong>'
            . ($rsp !== null && !empty($benchmark['from_history']) ? '<small>startkurs = slutkurs på startdagen</small>' : '')
            . '</div>';
        echo '<div><span>Forskel mod RSP</span><strong>'
            . ($rsp === null ? '–' : esc_html(self::signed($pct - (float)$rsp) . ' %-point')) . '</strong></div>';
        echo '<div><span>Dag</span><strong>' . esc_html((string)min($day, self::ROUND_DAYS)) . ' af '
            . esc_html((string)self::ROUND_DAYS) . '</strong><small>Startet ' . esc_html((string)$round['started']) . '</small></div>';
        echo '<div><span>Positioner</span><strong>' . esc_html((string)$count) . ' af '
            . esc_html((string)self::TARGET_POSITIONS) . '</strong><small>Højst '
            . esc_html((string)self::MAX_POSITIONS) . '</small></div>';
        echo '</div>';
        if ((int)$valuation['unpriced'] > 0) {
            echo '<p class="asc-warning">' . esc_html((string)$valuation['unpriced'])
                . ' position(er) mangler en kurs og vises til købsværdien, indtil kursen kommer.</p>';
        }
        echo '<p class="asc-subtle">Handelsomkostning ' . esc_html(self::fmt(self::FEE_RATE * 100, 1))
            . ' % ved køb og salg. Åbne positioner er værdisat uden salgsomkostning. Valuta omregnes med ECB-kurser.</p>';
    }

    private static function render_end_block(array $valuation, array $benchmark): void {
        $rsp = $benchmark['return'];
        $class = (float)$valuation['gain'] >= 0 ? 'asc-positive' : 'asc-negative';
        echo '<div class="asc-notice asc-sim-over" role="status"><h3>Runden er slut</h3>';
        echo '<p>Slutværdi <strong>' . esc_html(self::fmt((float)$valuation['total'])) . ' kr.</strong> – <strong class="'
            . esc_attr($class) . '">' . esc_html(self::signed((float)$valuation['gain']) . ' kr. ('
            . self::signed((float)$valuation['pct']) . ' %)') . '</strong>. RSP i samme periode: '
            . ($rsp === null ? '–' : esc_html(self::signed((float)$rsp) . ' %')) . '.</p>';
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="asc_sim_end">';
        wp_nonce_field('asc_sim_end');
        echo '<button type="submit">Afslut og start ny runde</button></form></div>';
    }

    private static function render_lookup(array $round): void {
        $ticker = strtoupper(self::query_text('asc_sim_ticker'));
        $view = sanitize_key(self::query_text('asc_view'));
        echo '<div class="asc-add-position asc-sim-lookup"><h3>Find en aktie</h3>';
        echo '<form class="asc-filter-form" method="get">';
        if ($view !== '') { echo '<input type="hidden" name="asc_view" value="' . esc_attr($view) . '">'; }
        echo '<label>Ticker (Yahoo-symbol)<input type="text" name="asc_sim_ticker" maxlength="20" '
            . 'placeholder="fx MSFT, NOVO-B.CO eller SAP.DE" value="' . esc_attr($ticker) . '"></label>';
        echo '<button type="submit">Slå op</button></form>';
        if ($ticker !== '') {
            if (preg_match(self::TICKER_RE, $ticker) !== 1) {
                echo '<p class="asc-notice-error" role="alert">Aktiesymbolet er ugyldigt.</p>';
            } else {
                self::render_lookup_result($round, $ticker);
            }
        }
        echo '</div>';
    }

    private static function render_lookup_result(array $round, string $ticker): void {
        $quote = self::price_for($ticker);
        echo '<h4>' . esc_html($ticker) . '</h4>';
        if ($quote === null) {
            echo '<p class="asc-warning">Ingen kurs tilgængelig for ' . esc_html($ticker)
                . ' (symbolet findes ikke, eller kurskilden svarer ikke). Der kan ikke købes uden kurs.</p>';
        } else {
            echo '<p><strong>' . esc_html(self::fmt($quote['price'])) . ' ' . esc_html($quote['currency'])
                . '</strong> <span class="asc-subtle">kurstidspunkt ' . esc_html(self::when($quote['time']))
                . ($quote['stale'] ? ' – gammel kurs' : '') . '</span></p>';
        }
        echo ASC_Playbook::analysis_panel($ticker);
        if ($quote === null) { return; }
        $fx = self::fx($quote['currency']);
        if ($fx === null) {
            echo '<p class="asc-warning">Ingen valutakurs til DKK for ' . esc_html($quote['currency'])
                . ' – aktien kan ikke købes i simulatoren.</p>';
            return;
        }
        $turnover = self::daily_turnover_dkk($quote['history'], (float)$fx);
        if ($turnover !== null) {
            echo '<p>En dags handel &asymp; <strong>' . esc_html(self::fmt($turnover, 0)) . ' kr.</strong> '
                . '<span class="asc-subtle">(gennemsnit af lukkekurs &times; volumen, seneste '
                . esc_html((string)self::LIQUID_DAYS) . ' dage)</span></p>';
            if ($turnover < self::THIN_TRADE_DKK) {
                echo '<p class="asc-warning">Tyndt handlet: under ca. ' . esc_html(self::fmt(self::THIN_TRADE_DKK / 1000000, 0))
                    . ' mio. kr. om dagen. Det kan være svært at købe og sælge uden at flytte kursen. '
                    . 'Playbook-listen gør ikke sådanne aktier til købskandidater.</p>';
            }
        }
        $held = false;
        foreach ($round['positions'] as $position) {
            if (($position['ticker'] ?? '') === $ticker) { $held = true; }
        }
        if ($held) {
            echo '<p class="asc-subtle">Du ejer allerede denne aktie i runden.</p>';
            return;
        }
        $default = (float)$round['start_cash_dkk'] / self::TARGET_POSITIONS;
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" class="asc-sim-buy">';
        echo '<input type="hidden" name="action" value="asc_sim_buy">';
        wp_nonce_field('asc_sim_buy');
        echo '<input type="hidden" name="asc_sim_ticker" value="' . esc_attr($ticker) . '">';
        echo '<label>Beløb i kr.<input type="text" name="asc_sim_amount" inputmode="decimal" placeholder="fx '
            . esc_attr(self::fmt(floor($default), 0)) . '" required></label>';
        echo '<button type="submit">Køb virtuelt</button></form>';
        echo '<p class="asc-subtle">Kurserne er forsinkede; købet sker til serverens seneste kurs (1 aktie ≈ '
            . esc_html(self::fmt($quote['price'] * (float)$fx)) . ' kr.), antal = hele aktier, plus '
            . esc_html(self::fmt(self::FEE_RATE * 100, 1)) . ' % i omkostning.</p>';
    }

    private static function render_positions(array $valuation, bool $finished): void {
        echo '<h3>Mine positioner</h3>';
        if (!$valuation['rows']) {
            echo '<p class="asc-empty">Ingen positioner endnu. Slå en aktie op ovenfor, og køb den.</p>';
            return;
        }
        echo '<div class="asc-table-wrap asc-sim-table"><table><thead><tr>';
        foreach (['Aktie', 'Antal', 'Købskurs', 'Seneste kurs', 'Værdi (kr.)', 'Gevinst (kr.)', ''] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach ($valuation['rows'] as $row) {
            $class = $row['gain'] >= 0 ? 'asc-positive' : 'asc-negative';
            echo '<tr><th scope="row">' . esc_html($row['ticker'])
                . '<div class="asc-subtle">' . esc_html($row['buy_date']) . '</div></th>';
            echo '<td>' . esc_html(self::fmt_quantity($row['quantity'])) . '</td>';
            echo '<td>' . esc_html(self::fmt($row['buy_price']) . ' ' . $row['currency']) . '</td>';
            if ($row['price'] !== null) {
                echo '<td>' . esc_html(self::fmt($row['price']) . ' ' . $row['currency'])
                    . '<div class="asc-subtle">' . esc_html(self::when($row['time']))
                    . ($row['stale'] ? ' – gammel kurs' : '') . '</div></td>';
            } else {
                echo '<td>–<div class="asc-subtle">kurs mangler</div></td>';
            }
            echo '<td>' . esc_html(self::fmt($row['value'])) . '</td>';
            echo '<td class="' . esc_attr($class) . '">' . esc_html(self::signed($row['gain']))
                . '<div>' . esc_html(self::signed($row['pct']) . ' %') . '</div></td>';
            echo '<td>';
            if (!$finished && $row['price'] !== null) {
                echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
                echo '<input type="hidden" name="action" value="asc_sim_sell">';
                echo '<input type="hidden" name="asc_sim_position_id" value="' . esc_attr($row['id']) . '">';
                wp_nonce_field('asc_sim_sell', '_wpnonce', false);
                echo '<button type="submit" class="asc-delete">Sælg alle</button></form>';
            }
            echo '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function render_closed(array $round): void {
        $closed = $round['closed'];
        if (!$closed) { return; }
        echo '<h3>Lukkede handler</h3>';
        echo '<div class="asc-table-wrap asc-sim-table"><table><thead><tr>';
        foreach (['Aktie', 'Antal', 'Købt', 'Solgt', 'Resultat (kr.)'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach (array_reverse($closed) as $trade) {
            $pnl = (float)($trade['pnl_dkk'] ?? 0);
            $currency = (string)($trade['currency'] ?? '');
            echo '<tr><th scope="row">' . esc_html((string)($trade['ticker'] ?? '')) . '</th>';
            echo '<td>' . esc_html(self::fmt_quantity((float)($trade['quantity'] ?? 0))) . '</td>';
            echo '<td>' . esc_html(self::fmt((float)($trade['buy_price'] ?? 0)) . ' ' . $currency)
                . '<div class="asc-subtle">' . esc_html((string)($trade['buy_date'] ?? '')) . '</div></td>';
            echo '<td>' . esc_html(self::fmt((float)($trade['sell_price'] ?? 0)) . ' ' . $currency)
                . '<div class="asc-subtle">' . esc_html((string)($trade['sell_date'] ?? '')) . '</div></td>';
            echo '<td class="' . esc_attr($pnl >= 0 ? 'asc-positive' : 'asc-negative') . '">'
                . esc_html(self::signed($pnl)) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function render_history(array $history): void {
        if (!$history) { return; }
        echo '<h3>Tidligere runder</h3>';
        echo '<div class="asc-table-wrap asc-sim-table"><table><thead><tr>';
        foreach (['Periode', 'Start (kr.)', 'Slut (kr.)', 'Afkast', 'RSP', 'Handler'] as $head) {
            echo '<th scope="col">' . esc_html($head) . '</th>';
        }
        echo '</tr></thead><tbody>';
        foreach ($history as $item) {
            $return = is_numeric($item['return_pct'] ?? null) ? (float)$item['return_pct'] : null;
            $rsp = is_numeric($item['rsp_return_pct'] ?? null) ? (float)$item['rsp_return_pct'] : null;
            echo '<tr><th scope="row">' . esc_html((string)($item['started'] ?? '')) . ' – '
                . esc_html((string)($item['ended'] ?? '')) . '</th>';
            echo '<td>' . esc_html(self::fmt((float)($item['start_value'] ?? 0))) . '</td>';
            echo '<td>' . esc_html(self::fmt((float)($item['end_value'] ?? 0))) . '</td>';
            echo '<td class="' . esc_attr($return !== null && $return < 0 ? 'asc-negative' : 'asc-positive') . '">'
                . ($return === null ? '–' : esc_html(self::signed($return) . ' %')) . '</td>';
            echo '<td>' . ($rsp === null ? '–' : esc_html(self::signed($rsp) . ' %')) . '</td>';
            echo '<td>' . esc_html((string)(int)($item['trades'] ?? 0)) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }
}
