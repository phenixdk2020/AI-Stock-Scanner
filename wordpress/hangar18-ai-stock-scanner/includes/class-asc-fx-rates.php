<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/**
 * ECB daily reference rates for indicative portfolio values in DKK.
 *
 * EUR-based reference rates, not an FX trading feed. They are only used to
 * convert already calculated native-currency P/L at the reference rate of
 * the SAME day; historical FX gains/losses are not inferred.
 */
final class ASC_FX_Rates {
    private const ENDPOINT = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml';
    private const CACHE_KEY = 'asc_ecb_daily_fx_v1';
    private const LAST_KEY = 'asc_ecb_last_good_fx_v1';
    private const COOLDOWN_KEY = 'asc_ecb_fx_failed_v1';
    private const CACHE_SECONDS = 21600; // 6h; ECB itself publishes once per working day.
    private const COOLDOWN_SECONDS = 900;
    private const MAX_RESPONSE = 65536;
    private static bool $loaded = false;
    private static ?array $snapshot = null;

    /**
     * Parse an ECB XML payload using DOM, with XXE disabled. Returns null
     * unless it has a trustworthy date and a positive DKK reference rate.
     * Exposed for deterministic, network-free regression testing.
     */
    public static function parse_ecb_xml(string $body): ?array {
        if ($body === '' || strlen($body) > self::MAX_RESPONSE ||
            stripos($body, '<!DOCTYPE') !== false || stripos($body, '<!ENTITY') !== false ||
            !class_exists('DOMDocument')) {
            return null;
        }
        $previous = libxml_use_internal_errors(true);
        try {
            $doc = new DOMDocument();
            $doc->resolveExternals = false;
            $doc->substituteEntities = false;
            if (!$doc->loadXML($body, LIBXML_NONET)) { return null; }
            $xpath = new DOMXPath($doc);
            $days = $xpath->query('//*[local-name()="Cube" and @time]');
            if ($days === false || $days->length !== 1) { return null; }
            $day = $days->item(0);
            if (!($day instanceof DOMElement)) { return null; }
            $date = $day->getAttribute('time');
            $parsed_date = DateTimeImmutable::createFromFormat('!Y-m-d', $date);
            if (!$parsed_date || $parsed_date->format('Y-m-d') !== $date) { return null; }
            // Allow weekends/ECB holidays but reject unexpectedly old/future data.
            $stamp = $parsed_date->getTimestamp();
            if ($stamp > time() + 86400 || $stamp < time() - 8 * DAY_IN_SECONDS) {
                return null;
            }
            $rates = ['EUR' => 1.0];
            $nodes = $xpath->query('./*[local-name()="Cube" and @currency and @rate]', $day);
            if ($nodes === false) { return null; }
            foreach ($nodes as $node) {
                if (!($node instanceof DOMElement)) { continue; }
                $code = $node->getAttribute('currency');
                $raw = $node->getAttribute('rate');
                if (!in_array($code, ['DKK', 'SEK', 'NOK', 'USD'], true)
                    || preg_match('/^[0-9]+(?:\.[0-9]+)?$/D', $raw) !== 1) {
                    continue;
                }
                $rate = (float)$raw;
                if (is_finite($rate) && $rate > 0 && $rate < 1000000) {
                    $rates[$code] = $rate;
                }
            }
            if (!isset($rates['DKK']) || count($rates) < 3) { return null; }
            return [
                'source_date' => $date,
                'received_at' => time(),
                'eur_rates' => $rates,
            ];
        } catch (Throwable $e) {
            return null;
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($previous);
        }
    }

    /** Safe currency conversion: 1 EUR = X DKK and 1 EUR = Y foreign. */
    public static function rate_from_snapshot(array $snapshot, string $currency): ?float {
        if ($currency === 'DKK') { return 1.0; }
        $rates = $snapshot['eur_rates'] ?? null;
        if (!is_array($rates) || !isset($rates['DKK'], $rates[$currency])
            || !is_numeric($rates['DKK']) || !is_numeric($rates[$currency])) {
            return null;
        }
        $dkk = (float)$rates['DKK'];
        $base = (float)$rates[$currency];
        if (!is_finite($dkk) || !is_finite($base) || $base <= 0 || $dkk <= 0) {
            return null;
        }
        $rate = $dkk / $base;
        return is_finite($rate) && $rate > 0 ? $rate : null;
    }

    private static function acceptable(?array $value): bool {
        if (!is_array($value) || !is_string($value['source_date'] ?? null)
            || !is_numeric($value['received_at'] ?? null)
            || !is_array($value['eur_rates'] ?? null)) {
            return false;
        }
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $value['source_date']);
        return $date instanceof DateTimeImmutable
            && $date->format('Y-m-d') === $value['source_date']
            && $date->getTimestamp() <= time() + DAY_IN_SECONDS
            && $date->getTimestamp() >= time() - 8 * DAY_IN_SECONDS
            && (int)$value['received_at'] <= time() + 300
            && (int)$value['received_at'] >= time() - 7 * DAY_IN_SECONDS
            && self::rate_from_snapshot($value, 'EUR') !== null;
    }

    private static function latest(): ?array {
        if (self::$loaded) { return self::$snapshot; }
        self::$loaded = true;
        $cached = get_transient(self::CACHE_KEY);
        if (is_array($cached) && self::acceptable($cached)) {
            return self::$snapshot = $cached;
        }
        $last = get_option(self::LAST_KEY, null);
        $fallback = is_array($last) && self::acceptable($last)
            ? array_merge($last, ['stale' => true]) : null;
        if (get_transient(self::COOLDOWN_KEY) !== false) {
            return self::$snapshot = $fallback;
        }

        // Rate limiting applies to unsuccessful attempts too, even if unavailable.
        set_transient(self::COOLDOWN_KEY, 1, self::COOLDOWN_SECONDS);
        $response = wp_safe_remote_get(self::ENDPOINT, [
            'timeout' => 3,
            'redirection' => 0,
            'limit_response_size' => self::MAX_RESPONSE,
            'headers' => ['Accept' => 'application/xml'],
        ]);
        if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
            return self::$snapshot = $fallback;
        }
        $parsed = self::parse_ecb_xml((string)wp_remote_retrieve_body($response));
        if ($parsed === null) { return self::$snapshot = $fallback; }
        set_transient(self::CACHE_KEY, $parsed, self::CACHE_SECONDS);
        update_option(self::LAST_KEY, $parsed, false);
        return self::$snapshot = $parsed;
    }

    /**
     * DKK per one unit of the supplied ISO currency. No guessed fallback rate.
     * Source and date must always be shown when presenting conversion.
     */
    public static function to_dkk(string $currency): ?array {
        if ($currency === 'DKK') {
            return ['rate' => 1.0, 'source_date' => '', 'stale' => false];
        }
        if (!in_array($currency, ['EUR', 'USD', 'SEK', 'NOK'], true)) { return null; }
        $data = self::latest();
        if ($data === null) { return null; }
        $rate = self::rate_from_snapshot($data, $currency);
        if ($rate === null) { return null; }
        return [
            'rate' => $rate,
            'source_date' => (string)$data['source_date'],
            'stale' => !empty($data['stale']),
        ];
    }
}
