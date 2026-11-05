<?php
declare(strict_types=1);

if (!defined('ABSPATH')) { exit; }

/**
 * Entry-tjeklisten på aktiesiden: alle krav, plus- og minustegn og en plan med stop, kursmål og tab.
 * Kravene gentager weekly_list.classify og må kun ændres sammen med den. Plus- og minustegn ændrer
 * aldrig Entry; de er til Allans egen vurdering. Systemet køber ikke noget selv.
 */
final class ASC_Entry_Check {
    // Samme tal som stockscanner/weekly_list.py og sizing.DEFAULTS; en test holder dem ens.
    public const MIN_QUALITY = 60.0;
    public const MIN_VALUE_SCORE = 50.0;
    public const MAX_PEG = 2.0;
    public const MIN_ASYMMETRY = 3.0;
    public const ATR_MULTIPLE = 3.0;
    public const WEAK_MARKET = 50.0;    // Højst så mange % over 50-dages gennemsnit = svagt marked.
    private const DEFAULT_AMOUNT = 10000.0;
    private const MIN_AMOUNT = 100.0;
    private const MAX_AMOUNT = 100000000.0;
    private const OWNED_ACTIONS = ['SÆLG (ejet)', 'BEHOLD (ejet)'];

    /** Svagt marked ud fra snapshot-feltet breadth; ukendt tæller ikke som svagt. */
    public static function market_weak(array $breadth): bool {
        $share = $breadth['50'] ?? null;
        return is_numeric($share) && (float)$share <= self::WEAK_MARKET;
    }

    /**
     * Købskravene i samme rækkefølge som weekly_list.classify.
     * @return array<int, array{0: string, 1: string, 2: string}> Tilstand (ok, no, unknown), krav og detalje.
     */
    public static function requirements(array $stock): array {
        $list = [];
        $signal = (string)($stock['stockmap'] ?? '');
        $list[] = [strpos($signal, 'køb') === 0 ? 'ok' : 'no', 'StockMap-køb', $signal !== '' ? $signal : 'intet signal'];
        $list[] = self::at_least('Kvalitet mindst 60', $stock['quality'] ?? null, self::MIN_QUALITY, false);
        $list[] = self::at_least('Kanal mindst 50', $stock['channel_score'] ?? null, self::MIN_VALUE_SCORE, false);
        $peg = $stock['peg'] ?? null;
        $list[] = is_numeric($peg)
            ? [(float)$peg < self::MAX_PEG ? 'ok' : 'no', 'PEG under 2', number_format((float)$peg, 2, ',', '.')]
            : ['unknown', 'PEG under 2', 'mangler, spærrer ikke'];
        $list[] = !empty($stock['asymmetry_inf'])
            ? ['ok', 'Asymmetri mindst 3', 'kursen er under Bear']
            : self::at_least('Asymmetri mindst 3', $stock['asymmetry'] ?? null, self::MIN_ASYMMETRY, true);
        $list[] = self::earnings_requirement($stock);
        $list[] = ($stock['liquidity'] ?? null) === 'Lav'
            ? ['no', 'Nok handel i aktien', 'for lidt handel'] : ['ok', 'Nok handel i aktien', (string)($stock['liquidity'] ?? 'ikke målt')];
        $trap = (string)($stock['eps_trend'] ?? '');
        $list[] = [$trap === '' ? 'ok' : 'no', 'Ingen faldende estimater', $trap === '' ? 'ingen fald' : $trap];
        $alarm = strpos((string)($stock['reasons'] ?? ''), 'STOR NEGATIV NYHED') !== false
            || strpos((string)($stock['news_summary'] ?? ''), 'STOR NEGATIV NYHED') !== false;
        $list[] = [$alarm ? 'no' : 'ok', 'Ingen stor negativ nyhed', $alarm ? 'se nyhederne' : 'ingen'];
        return $list;
    }

    /** @return array{0: string, 1: string, 2: string} */
    private static function at_least(string $label, $value, float $limit, bool $optional): array {
        if (!is_numeric($value)) { return [$optional ? 'unknown' : 'no', $label, $optional ? 'mangler, spærrer ikke' : 'mangler']; }
        return [(float)$value >= $limit ? 'ok' : 'no', $label, number_format((float)$value, $optional ? 1 : 0, ',', '.')];
    }

    /** @return array{0: string, 1: string, 2: string} */
    private static function earnings_requirement(array $stock): array {
        $days = ASC_Playbook::earnings_days($stock['earnings'] ?? null);
        if ($days !== null && $days >= 0) {
            return [ASC_Playbook::earnings_soon($days) ? 'no' : 'ok', 'Intet regnskab inden for 7 dage',
                'om ' . $days . ' dage'];
        }
        $guess = ASC_Playbook::earnings_days($stock['earnings_estimate'] ?? null);
        return $guess !== null && $guess >= 0
            ? ['unknown', 'Intet regnskab inden for 7 dage', 'anslået om ' . $guess . ' dage, spærrer ikke']
            : ['unknown', 'Intet regnskab inden for 7 dage', 'dato ukendt, tjek selv'];
    }

    /**
     * Tegn der hverken giver eller fjerner Entry.
     * @return array<int, array{0: string, 1: string, 2: string}> Tegn (plus, minus, neutral), emne og detalje.
     */
    public static function signals(array $stock, array $breadth): array {
        $list = [];
        $share = $breadth['50'] ?? null;
        if (is_numeric($share)) {
            $list[] = [self::market_weak($breadth) ? 'minus' : 'plus', 'Marked',
                number_format((float)$share, 0, ',', '.') . ' % af aktierne er over 50-dages gennemsnit'];
        }
        $mti = (string)($stock['mti'] ?? '');
        if ($mti !== '') { $list[] = [$mti === 'dobbelt grøn' ? 'plus' : ($mti === 'rød' ? 'minus' : 'neutral'), 'MTI', $mti]; }
        $tpi = (string)($stock['tpi'] ?? '');
        if ($tpi !== '') { $list[] = ['neutral', 'TPI', $tpi]; }
        $rising = (string)($stock['eps_rising'] ?? '');
        if ($rising !== '') { $list[] = ['plus', 'Estimater', $rising]; }
        $list[] = self::insider_signal(is_array($stock['insiders'] ?? null) ? $stock['insiders'] : null);
        $guess = ASC_Playbook::earnings_days($stock['earnings_estimate'] ?? null);
        if (ASC_Playbook::earnings_soon($guess)) {
            $list[] = ['minus', 'Regnskab', 'Anslået om ' . $guess . ' dage. Datoen er regnet ud fra tidligere regnskaber'];
        }
        $risk = is_array($stock['earnings_risk'] ?? null) ? (string)($stock['earnings_risk']['level'] ?? '') : '';
        if ($risk === 'Høj') { $list[] = ['minus', 'Regnskabsrisiko', 'Høj']; }
        return $list;
    }

    /** @return array{0: string, 1: string, 2: string} */
    private static function insider_signal(?array $facts): array {
        if ($facts === null) { return ['neutral', 'Insiderkøb', 'ingen data, findes kun for USA']; }
        $buyers = (int)($facts['buyers'] ?? 0);
        $days = (int)($facts['days'] ?? 90);
        if ($buyers < 1) { return ['neutral', 'Insiderkøb', 'ingen køb på markedet de seneste ' . $days . ' dage']; }
        return ['plus', 'Insiderkøb', $buyers . ' i ledelsen har købt for ca. '
            . number_format((float)($facts['value_usd'] ?? 0), 0, ',', '.') . ' USD på ' . $days . ' dage'];
    }

    /**
     * Plan ud fra seneste kørsel. Null uden kurs og ATR, eller når stoppet ikke giver mening.
     * @return array<string, float|null>|null
     */
    public static function plan(array $stock, ?array $scenarios, float $amount): ?array {
        $price = $stock['price'] ?? null;
        $atr = $stock['atr14'] ?? null;
        if (!is_numeric($price) || !is_numeric($atr) || (float)$price <= 0 || (float)$atr <= 0) { return null; }
        $price = (float)$price;
        $stop = $price - self::ATR_MULTIPLE * (float)$atr;
        if ($stop <= 0) { return null; }
        $risk_pct = ($price - $stop) / $price * 100;
        $prices = is_array($scenarios) && is_array($scenarios['prices'] ?? null) ? $scenarios['prices'] : [];
        $base = is_numeric($prices['base'] ?? null) ? (float)$prices['base'] : null;
        $bull = is_numeric($prices['bull'] ?? null) ? (float)$prices['bull'] : null;
        return [
            'price' => $price, 'stop' => $stop, 'risk_pct' => $risk_pct, 'loss' => $amount * $risk_pct / 100,
            'base' => $base, 'bull' => $bull,
            'reward_risk' => $base === null ? null : ($base - $price) / ($price - $stop),
        ];
    }

    /** Beløbet fra adresselinjen inden for rimelige grænser; ellers standardbeløbet. */
    private static function amount(): float {
        $raw = isset($_GET['asc_amount']) && is_string($_GET['asc_amount']) ? sanitize_text_field(wp_unslash($_GET['asc_amount'])) : '';
        $value = str_replace(['.', ' ', ','], ['', '', '.'], $raw);
        if (!is_numeric($value)) { return self::DEFAULT_AMOUNT; }
        return max(self::MIN_AMOUNT, min(self::MAX_AMOUNT, (float)$value));
    }

    private static function fmt(?float $value, int $decimals = 2): string {
        return $value === null ? '–' : number_format($value, $decimals, ',', '.');
    }

    /** Hele panelet som escaped HTML. Tom streng uden fuld analyse. */
    public static function render(string $ticker, ?array $stock, ?array $scenarios, array $breadth): string {
        if ($stock === null) { return ''; }
        $requirements = self::requirements($stock);
        $missing = count(array_filter($requirements, static fn(array $r): bool => $r[0] === 'no'));
        $owned = in_array($stock['action'] ?? null, self::OWNED_ACTIONS, true);
        $marks = ['ok' => '✓', 'no' => '✗', 'unknown' => '?', 'plus' => '▲', 'minus' => '▼', 'neutral' => '•'];
        $html = '<div class="asc-sim-analysis asc-entry-check"><h4>Entry-tjekliste</h4>';
        $html .= '<p><strong>' . esc_html($missing === 0 ? 'Alle krav er opfyldt' : $missing . ' krav er ikke opfyldt') . '</strong>'
            . ($owned ? ' <span class="asc-subtle">Du ejer aktien, så salgsreglerne gælder først.</span>' : '') . '</p>';
        if (self::market_weak($breadth) && $missing === 0) {
            $html .= '<p class="asc-warning" role="alert">Markedet er svagt. Entry gælder stadig, men overvej en mindre position.</p>';
        }
        $html .= '<ul class="asc-check-list">';
        foreach ($requirements as [$state, $label, $detail]) {
            $html .= '<li class="asc-check-' . esc_attr($state) . '"><span aria-hidden="true">' . $marks[$state] . '</span> '
                . esc_html($label) . ' <span class="asc-subtle">' . esc_html($detail) . '</span></li>';
        }
        $html .= '</ul><h5>Plus og minus</h5><p class="asc-subtle">Ændrer ikke Entry. Det er tegn, du selv vejer.</p><ul class="asc-check-list">';
        foreach (self::signals($stock, $breadth) as [$sign, $label, $detail]) {
            $html .= '<li class="asc-check-' . esc_attr($sign) . '"><span aria-hidden="true">' . $marks[$sign] . '</span> '
                . esc_html($label) . ' <span class="asc-subtle">' . esc_html($detail) . '</span></li>';
        }
        $html .= '</ul>' . self::why_cheap_html(is_array($stock['why_cheap'] ?? null) ? $stock['why_cheap'] : null);
        return $html . self::plan_html($ticker, $stock, $scenarios) . '</div>';
    }

    private static function why_cheap_html(?array $why): string {
        if ($why === null) { return ''; }
        $labels = ['lav' => 'Lav', 'middel' => 'Middel', 'hoej' => 'Høj', 'ukendt' => 'Ukendt'];
        $html = '<h5>Hvorfor er den billig?</h5><p>' . esc_html((string)($why['hvorfor_billig'] ?? '')) . '</p>';
        $risks = is_array($why['risici'] ?? null) ? $why['risici'] : [];
        if ($risks) {
            $html .= '<ul>';
            foreach ($risks as $risk) { $html .= '<li>' . esc_html((string)$risk) . '</li>'; }
            $html .= '</ul>';
        }
        return $html . '<p class="asc-subtle">Risiko for værdifælde: '
            . esc_html($labels[(string)($why['vaerdifaelde'] ?? 'ukendt')] ?? 'Ukendt') . '. Skrevet af lokal AI '
            . esc_html((string)($why['dato'] ?? '')) . ' ud fra regnskabstal og nyheder. Kan tage fejl, så tjek selv.</p>';
    }

    private static function plan_html(string $ticker, array $stock, ?array $scenarios): string {
        $amount = self::amount();
        $plan = self::plan($stock, $scenarios, $amount);
        if ($plan === null) { return ''; }
        $currency = (string)($stock['currency'] ?? '');
        $html = '<h5>Plan, hvis du køber</h5><ul>';
        $html .= '<li>Kurs ved seneste kørsel: <strong>' . esc_html(self::fmt($plan['price']) . ' ' . $currency) . '</strong></li>';
        $html .= '<li>Stop (kurs minus 3 × ATR): <strong>' . esc_html(self::fmt($plan['stop']) . ' ' . $currency) . '</strong>, '
            . esc_html(self::fmt($plan['risk_pct'], 1)) . ' % under kursen</li>';
        if ($plan['base'] !== null) {
            $html .= '<li>Kursmål: Base ' . esc_html(self::fmt($plan['base'])) . ' og Bull ' . esc_html(self::fmt($plan['bull']))
                . ' ' . esc_html($currency) . ' <span class="asc-subtle">(regnestykke, ikke en prognose)</span></li>';
            $html .= '<li>Gevinst mod risiko til Base: <strong>' . esc_html(self::fmt($plan['reward_risk'], 1)) . ' gange</strong></li>';
        }
        $html .= '<li>Køber du for ' . esc_html(self::fmt($amount, 0)) . ', taber du ca. <strong>'
            . esc_html(self::fmt($plan['loss'], 0)) . '</strong>, hvis stoppet rammes. Kursgab kan gøre tabet større.</li></ul>';
        $html .= '<form class="asc-filter-form" method="get" action="' . esc_url(ASC_Stock_Page::url($ticker)) . '#asc-entry-plan">';
        parse_str((string)wp_parse_url(ASC_Stock_Page::url($ticker), PHP_URL_QUERY), $query);
        foreach ($query as $key => $value) {
            if (is_string($value)) {
                $html .= '<input type="hidden" name="' . esc_attr((string)$key) . '" value="' . esc_attr($value) . '">';
            }
        }
        return $html . '<label id="asc-entry-plan">Beløb<input type="number" name="asc_amount" min="100" step="100" value="'
            . esc_attr((string)round($amount)) . '"></label><button type="submit">Beregn</button></form>';
    }
}
