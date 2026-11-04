/* Aktiesidens interaktive graf (TradingView Lightweight Charts, Apache-2.0, ligger i pluginet under assets/vendor).
   Læser kurserne fra <script type="application/json" id="asc-chart-data"> og bygger periodevalg, linje/candles, volumen,
   SMA50/SMA200, markører (K, V, S), trådkors-tekst og intradag (1 D og 1 U fra REST-ruten). Mislykkes biblioteket,
   vises den serverrenderede SVG-graf fra <noscript data-asc-chart-fallback>. Intet gættes: mangler data, siges det. */
(function () {
    'use strict';
    var root = document.querySelector('[data-asc-chart]');
    if (!root) { return; }

    var PERIODS = [['1d', '1 D'], ['5d', '1 U'], ['1m', '1 M'], ['3m', '3 M'], ['6m', '6 M'], ['ytd', 'ÅTD'], ['1y', '1 Å'], ['5y', '5 Å']];
    var INTRADAY = { '1d': true, '5d': true };
    var STORAGE_KEY = 'asc_stock_period';
    var DEFAULT_PERIOD = '6m';
    var UP = '#167b59', DOWN = '#c8394c', SMA50 = '#d97706', SMA200 = '#7c3aed', MARK = '#0ea5e9';
    var LETTER = { buy: 'K', sim_buy: 'V', sim_sell: 'S' };

    var fallbackShown = false;
    function useFallback() {
        if (fallbackShown) { return; }
        fallbackShown = true;
        root.hidden = true;
        var credit = document.querySelector('.asc-chart-credit');
        if (credit) { credit.hidden = true; }
        var holder = document.querySelector('noscript[data-asc-chart-fallback]');
        if (!holder) { return; }
        // Med JavaScript slået til er indholdet af <noscript> ren tekst: serverens escaped markup.
        var box = document.createElement('div');
        box.className = 'asc-chart-fallback';
        var note = document.createElement('p');
        note.className = 'asc-subtle';
        note.textContent = 'Den interaktive graf kunne ikke indlæses. Her er den enkle graf.';
        var inner = document.createElement('div');
        inner.innerHTML = holder.textContent || '';
        box.appendChild(note);
        box.appendChild(inner);
        holder.parentNode.insertBefore(box, holder);
    }

    var cfg = null;
    try {
        var dataNode = document.getElementById('asc-chart-data');
        cfg = dataNode ? JSON.parse(dataNode.textContent || '') : null;
    } catch (e) { cfg = null; }
    var LW = window.LightweightCharts;
    if (!cfg || !Array.isArray(cfg.bars) || cfg.bars.length < 2 || !LW || typeof LW.createChart !== 'function'
        || !LW.AreaSeries || !LW.CandlestickSeries || !LW.HistogramSeries || !LW.LineSeries) {
        useFallback();
        return;
    }

    // ---------------------------------------------------------------- Hjælpere

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) { node.className = cls; }
        if (text !== undefined) { node.textContent = text; }
        return node;
    }
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    function dayOf(ts) { return new Date(ts * 1000).toISOString().slice(0, 10); }
    function dayText(day) { return day.slice(8, 10) + '-' + day.slice(5, 7) + '-' + day.slice(0, 4); }
    function stampText(ts) {   // ts er allerede forskudt til børsens lokale tid og vises som UTC
        var d = new Date(ts * 1000);
        return pad(d.getUTCDate()) + '-' + pad(d.getUTCMonth() + 1) + '-' + d.getUTCFullYear() + ' '
            + pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes());
    }
    var priceFmt = new Intl.NumberFormat('da-DK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    var pctFmt = new Intl.NumberFormat('da-DK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    var volFmt = new Intl.NumberFormat('da-DK', { maximumFractionDigits: 0 });
    var compactFmt = new Intl.NumberFormat('da-DK', { notation: 'compact', maximumFractionDigits: 1 });
    function signed(value, fmt) { return (value > 0 ? '+' : '') + fmt.format(value); }
    function rgba(color, alpha) {
        var m = /rgba?\(\s*(\d+)\D+(\d+)\D+(\d+)/.exec(color || '');
        return m ? 'rgba(' + m[1] + ',' + m[2] + ',' + m[3] + ',' + alpha + ')' : 'rgba(71,85,105,' + alpha + ')';
    }
    function validPeriod(key) {
        for (var i = 0; i < PERIODS.length; i++) { if (PERIODS[i][0] === key) { return true; } }
        return false;
    }
    function timeKey(t) {
        if (t && typeof t === 'object') { return t.year + '-' + pad(t.month) + '-' + pad(t.day); }
        return String(t);
    }

    // Daglige bars: én pr. dag (UTC-datoen, som serveren), stigende, med SMA50 og SMA200 på al historik.
    function prepareDaily(rows) {
        var out = [];
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i];
            var bar = { time: dayOf(r[0]), o: r[1], h: r[2], l: r[3], c: r[4], v: r[5] };
            if (out.length && out[out.length - 1].time === bar.time) { out[out.length - 1] = bar; } else { out.push(bar); }
        }
        var sums = { 50: 0, 200: 0 };
        for (var j = 0; j < out.length; j++) {
            [50, 200].forEach(function (n) {
                sums[n] += out[j].c;
                if (j >= n) { sums[n] -= out[j - n].c; }
                out[j]['sma' + n] = j >= n - 1 ? sums[n] / n : null;
            });
        }
        return out;
    }

    // ------------------------------------------------------------------- Graf

    function start() {
        var daily = prepareDaily(cfg.bars);
        var currency = cfg.currency || '';
        var state = { type: 'line', sma50: true, sma200: true, period: DEFAULT_PERIOD };
        var cur = null;            // den viste serie: { mode, bars, index, base, baseNote }
        var token = 0;             // ignorerer svar fra et forældet periodevalg
        var intradayCache = {};
        var chart = null;

        root.hidden = false;
        var head = el('div', 'asc-chart-head');
        head.setAttribute('role', 'status');
        var whenNode = el('div', 'asc-chart-when');
        var valueLine = el('div', 'asc-chart-valueline');
        var valueNode = el('strong', 'asc-chart-value');
        var changeNode = el('span', 'asc-chart-change');
        valueLine.appendChild(valueNode);
        valueLine.appendChild(document.createTextNode(' '));
        valueLine.appendChild(changeNode);
        var detailNode = el('div', 'asc-chart-detail asc-subtle');
        head.appendChild(whenNode);
        head.appendChild(valueLine);
        head.appendChild(detailNode);

        var toolbar = el('div', 'asc-chart-toolbar');
        var periodBar = el('div', 'asc-chart-periods');
        periodBar.setAttribute('role', 'group');
        periodBar.setAttribute('aria-label', 'Periode');
        var periodButtons = {};
        PERIODS.forEach(function (p) {
            var b = el('button', 'asc-chart-btn', p[1]);
            b.type = 'button';
            b.setAttribute('data-period', p[0]);
            b.addEventListener('click', function () { setPeriod(p[0]); });
            periodButtons[p[0]] = b;
            periodBar.appendChild(b);
        });
        var optionBar = el('div', 'asc-chart-options');
        optionBar.setAttribute('role', 'group');
        optionBar.setAttribute('aria-label', 'Visning');
        var typeButtons = {};
        [['line', 'Linje'], ['candle', 'Candles']].forEach(function (t) {
            var b = el('button', 'asc-chart-btn', t[1]);
            b.type = 'button';
            b.setAttribute('data-type', t[0]);
            b.addEventListener('click', function () { setType(t[0]); });
            typeButtons[t[0]] = b;
            optionBar.appendChild(b);
        });
        var smaButtons = {};
        [['sma50', 'SMA50', SMA50], ['sma200', 'SMA200', SMA200]].forEach(function (s) {
            var b = el('button', 'asc-chart-btn asc-chart-sma', s[1]);
            b.type = 'button';
            b.setAttribute('data-sma', s[0]);
            b.style.setProperty('--asc-sma', s[2]);
            b.title = 'Glidende gennemsnit (kun daglige perioder)';
            b.addEventListener('click', function () { state[s[0]] = !state[s[0]]; applySma(); refreshButtons(); });
            smaButtons[s[0]] = b;
            optionBar.appendChild(b);
        });
        toolbar.appendChild(periodBar);
        toolbar.appendChild(optionBar);

        var canvas = el('div', 'asc-chart-canvas');
        var messageNode = el('p', 'asc-chart-message');
        messageNode.setAttribute('role', 'status');
        messageNode.hidden = true;
        var legendNode = el('p', 'asc-subtle asc-chart-legend-line');
        var notes = [];
        if (cfg.limited) { notes.push('Kun ca. 6 måneders historik kunne hentes; SMA200 kan mangle.'); }
        if (cfg.markers && cfg.markers.length) { notes.push('K = køb (portefølje), V = køb (simulator), S = salg (simulator).'); }
        legendNode.textContent = notes.join(' ');
        legendNode.hidden = notes.length === 0;

        root.appendChild(head);
        root.appendChild(toolbar);
        root.appendChild(messageNode);
        root.appendChild(canvas);
        root.appendChild(legendNode);

        // Farver følger sidens: tekstfarven arves fra siden, baggrunden er gennemsigtig.
        function themeOptions() {
            var color = window.getComputedStyle(canvas).color;
            return {
                layout: { textColor: color, background: { type: LW.ColorType.Solid, color: 'transparent' }, attributionLogo: true },
                grid: { vertLines: { color: rgba(color, 0.08) }, horzLines: { color: rgba(color, 0.08) } },
                crosshair: { vertLine: { color: rgba(color, 0.5) }, horzLine: { color: rgba(color, 0.5) } }
            };
        }
        var theme = themeOptions();
        chart = LW.createChart(canvas, {
            autoSize: true,
            layout: theme.layout,
            grid: theme.grid,
            crosshair: { mode: LW.CrosshairMode.Normal, vertLine: theme.crosshair.vertLine, horzLine: theme.crosshair.horzLine },
            rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.08, bottom: 0.26 } },
            timeScale: { borderVisible: false, timeVisible: false, secondsVisible: false, rightOffset: 2, fixLeftEdge: true, fixRightEdge: true },
            localization: { locale: 'da-DK', priceFormatter: function (p) { return priceFmt.format(p); }, dateFormat: 'dd-MM-yyyy' },
            handleScroll: { vertTouchDrag: false },   // en lodret fingerbevægelse ruller siden, ikke grafen
            handleScale: { axisPressedMouseMove: true }
        });
        if (window.matchMedia) {
            var query = window.matchMedia('(prefers-color-scheme: dark)');
            var onTheme = function () {
                var t = themeOptions();
                chart.applyOptions({ layout: t.layout, grid: t.grid, crosshair: t.crosshair });
            };
            if (query.addEventListener) { query.addEventListener('change', onTheme); }
        }

        var area = chart.addSeries(LW.AreaSeries, {
            lineWidth: 2, lineColor: UP, topColor: rgba('rgb(22,123,89)', 0.28), bottomColor: rgba('rgb(22,123,89)', 0),
            priceLineVisible: true, lastValueVisible: true, crosshairMarkerVisible: true
        });
        var candles = chart.addSeries(LW.CandlestickSeries, {
            upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN, visible: false
        });
        var volume = chart.addSeries(LW.HistogramSeries, {
            priceScaleId: '', lastValueVisible: false, priceLineVisible: false,
            priceFormat: { type: 'custom', formatter: function (v) { return compactFmt.format(v); }, minMove: 1 }
        });
        volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        var sma50 = chart.addSeries(LW.LineSeries, { color: SMA50, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        var sma200 = chart.addSeries(LW.LineSeries, { color: SMA200, lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        var markerApis = [];
        if (typeof LW.createSeriesMarkers === 'function') {
            markerApis = [LW.createSeriesMarkers(area, []), LW.createSeriesMarkers(candles, [])];
        }

        // ---- Visning af tal over grafen
        function showPoint(i, hover) {
            var b = cur.bars[i];
            whenNode.textContent = (hover ? '' : 'Seneste: ') + (cur.mode === 'daily' ? dayText(b.time) : stampText(b.time));
            var diff = b.c - cur.base;
            var pct = cur.base > 0 ? diff / cur.base * 100 : null;
            changeNode.textContent = signed(diff, priceFmt) + ' ' + currency + (pct === null ? '' : ' (' + signed(pct, pctFmt) + ' %)')
                + ' ' + cur.baseNote;
            changeNode.className = 'asc-chart-change ' + (diff >= 0 ? 'asc-positive' : 'asc-negative');
            var vol = b.v > 0 ? 'Volumen ' + volFmt.format(b.v) : 'Volumen –';
            if (state.type === 'candle') {
                valueNode.textContent = priceFmt.format(b.c) + ' ' + currency;
                detailNode.textContent = 'Åbn ' + priceFmt.format(b.o) + ' · Høj ' + priceFmt.format(b.h) + ' · Lav '
                    + priceFmt.format(b.l) + ' · Luk ' + priceFmt.format(b.c) + ' · ' + vol;
            } else {
                valueNode.textContent = priceFmt.format(b.c) + ' ' + currency;
                detailNode.textContent = vol;
            }
        }
        function showLatest() { showPoint(cur.bars.length - 1, false); }
        chart.subscribeCrosshairMove(function (param) {
            if (!cur) { return; }
            if (!param || param.time === undefined || !param.point) { showLatest(); return; }
            var i = cur.index[timeKey(param.time)];
            if (i === undefined) { showLatest(); } else { showPoint(i, true); }
        });

        function refreshButtons() {
            Object.keys(periodButtons).forEach(function (k) {
                var on = k === state.period;
                periodButtons[k].setAttribute('aria-pressed', on ? 'true' : 'false');
                periodButtons[k].classList.toggle('is-active', on);
            });
            Object.keys(typeButtons).forEach(function (k) {
                var on = k === state.type;
                typeButtons[k].setAttribute('aria-pressed', on ? 'true' : 'false');
                typeButtons[k].classList.toggle('is-active', on);
            });
            var intraday = cur && cur.mode === 'intraday';
            ['sma50', 'sma200'].forEach(function (k) {
                var on = state[k] && !intraday;
                smaButtons[k].setAttribute('aria-pressed', on ? 'true' : 'false');
                smaButtons[k].classList.toggle('is-active', on);
                smaButtons[k].disabled = !!intraday;
            });
        }
        function say(text, offer) {
            messageNode.textContent = '';
            if (!text) { messageNode.hidden = true; return; }
            messageNode.hidden = false;
            messageNode.appendChild(document.createTextNode(text));
            if (offer) {
                var b = el('button', 'asc-chart-btn', 'Vis 1 M');
                b.type = 'button';
                b.setAttribute('data-offer', '1m');
                b.addEventListener('click', function () { setPeriod('1m'); });
                messageNode.appendChild(document.createTextNode(' '));
                messageNode.appendChild(b);
            }
        }

        function colorLine(diff) {
            var color = diff >= 0 ? UP : DOWN;
            var rgb = diff >= 0 ? 'rgb(22,123,89)' : 'rgb(200,57,76)';
            area.applyOptions({ lineColor: color, topColor: rgba(rgb, 0.28), bottomColor: rgba(rgb, 0) });
        }
        function volumeData(bars) {
            return bars.map(function (b) {
                return { time: b.time, value: b.v, color: b.c >= b.o ? rgba('rgb(22,123,89)', 0.45) : rgba('rgb(200,57,76)', 0.45) };
            });
        }
        function setSeries(bars, withSma) {
            area.setData(bars.map(function (b) { return { time: b.time, value: b.c }; }));
            candles.setData(bars.map(function (b) { return { time: b.time, open: b.o, high: b.h, low: b.l, close: b.c }; }));
            volume.setData(volumeData(bars));
            ['50', '200'].forEach(function (n) {
                var series = n === '50' ? sma50 : sma200;
                series.setData(withSma ? bars.filter(function (b) { return b['sma' + n] !== null; })
                    .map(function (b) { return { time: b.time, value: b['sma' + n] }; }) : []);
            });
        }
        function indexOf(bars) {
            var map = {};
            bars.forEach(function (b, i) { map[String(b.time)] = i; });
            return map;
        }
        function applySma() {
            var intraday = cur && cur.mode === 'intraday';
            sma50.applyOptions({ visible: state.sma50 && !intraday });
            sma200.applyOptions({ visible: state.sma200 && !intraday });
        }
        function placeMarkers() {
            var list = [];
            var days = daily.map(function (b) { return b.time; });
            (cfg.markers || []).forEach(function (m) {
                if (!LETTER[m.kind] || m.date < days[0] || m.date > days[days.length - 1]) { return; }
                var at = null;   // en dato uden handel (weekend) hører til barren før
                for (var i = 0; i < days.length; i++) { if (days[i] <= m.date) { at = days[i]; } else { break; } }
                if (at === null) { return; }
                var sell = m.kind === 'sim_sell';
                list.push({ time: at, position: sell ? 'aboveBar' : 'belowBar', shape: sell ? 'arrowDown' : 'arrowUp', color: MARK, text: LETTER[m.kind] });
            });
            list.sort(function (a, b) { return a.time < b.time ? -1 : (a.time > b.time ? 1 : 0); });
            markerApis.forEach(function (api) { api.setMarkers(list); });
        }
        function clearMarkers() { markerApis.forEach(function (api) { api.setMarkers([]); }); }

        // ---- Perioder
        function startDay(key, lastDay) {
            if (key === '5y') { return null; }
            if (key === 'ytd') { return lastDay.slice(0, 4) + '-01-01'; }
            var d = new Date(lastDay + 'T00:00:00Z');
            if (key === '1m') { d.setUTCMonth(d.getUTCMonth() - 1); }
            else if (key === '3m') { d.setUTCMonth(d.getUTCMonth() - 3); }
            else if (key === '6m') { d.setUTCMonth(d.getUTCMonth() - 6); }
            else { d.setUTCFullYear(d.getUTCFullYear() - 1); }
            return d.toISOString().slice(0, 10);
        }
        function applyDaily(key) {
            var changedMode = !cur || cur.mode !== 'daily';
            var n = daily.length;
            var from = 0;
            var begin = startDay(key, daily[n - 1].time);
            if (begin !== null) { while (from < n - 2 && daily[from].time < begin) { from++; } }
            var base = from > 0 ? daily[from - 1].c : daily[from].o;
            cur = { mode: 'daily', bars: daily, index: indexOf(daily), base: base, baseNote: 'siden periodens start' };
            if (changedMode) {
                setSeries(daily, true);
                chart.timeScale().applyOptions({ timeVisible: false });
                placeMarkers();
            }
            state.period = key;
            applySma();
            colorLine(daily[n - 1].c - base);
            chart.timeScale().setVisibleRange({ from: daily[from].time, to: daily[n - 1].time });
            refreshButtons();
            showLatest();
        }
        function applyIntraday(key, data) {
            var offset = data.gmtoffset || 0;
            var bars = [];
            data.bars.forEach(function (r) {
                var bar = { time: r[0] + offset, o: r[1], h: r[2], l: r[3], c: r[4], v: r[5] };
                if (bars.length && bars[bars.length - 1].time >= bar.time) { return; }
                bars.push(bar);
            });
            var useClose = key === '1d' && data.previous_close > 0;
            var base = useClose ? data.previous_close : bars[0].o;
            cur = { mode: 'intraday', bars: bars, index: indexOf(bars), base: base,
                baseNote: useClose ? 'siden forrige lukkekurs' : 'siden periodens start' };
            setSeries(bars, false);
            clearMarkers();
            chart.timeScale().applyOptions({ timeVisible: true, secondsVisible: false });
            state.period = key;
            applySma();
            colorLine(bars[bars.length - 1].c - base);
            chart.timeScale().fitContent();
            refreshButtons();
            showLatest();
        }
        function validIntraday(data) {
            if (!data || !Array.isArray(data.bars) || data.bars.length < 2) { return false; }
            return data.bars.every(function (r) {
                return Array.isArray(r) && r.length >= 6 && r.slice(0, 6).every(function (x) { return typeof x === 'number' && isFinite(x); })
                    && r[4] > 0;
            });
        }
        function fetchIntraday(key) {
            var info = cfg.intraday || {};
            if (!info.url) { return Promise.resolve(null); }
            var url = info.url + (info.url.indexOf('?') >= 0 ? '&' : '?') + 'ticker=' + encodeURIComponent(cfg.ticker) + '&range=' + key;
            return fetch(url, { credentials: 'same-origin', headers: { 'X-WP-Nonce': info.nonce || '', 'Accept': 'application/json' } })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) { return validIntraday(data) ? data : null; })
                .catch(function () { return null; });
        }
        function remember(key) {
            try { window.sessionStorage.setItem(STORAGE_KEY, key); } catch (e) { /* privat tilstand: perioden huskes ikke */ }
        }
        function setPeriod(key) {
            if (!validPeriod(key)) { return; }
            var mine = ++token;
            if (!INTRADAY[key]) {
                say('');
                applyDaily(key);
                remember(key);
                return;
            }
            if (intradayCache[key]) { say(''); applyIntraday(key, intradayCache[key]); remember(key); return; }
            say('Henter intradagskurser …');
            fetchIntraday(key).then(function (data) {
                if (mine !== token) { return; }
                if (!data) {
                    say('Intradagskurser kan ikke hentes lige nu (markedet kan være lukket, eller kilden svarer ikke). Der vises ingen gættede kurser.', true);
                    return;
                }
                intradayCache[key] = data;
                say('');
                applyIntraday(key, data);
                remember(key);
            });
        }
        function setType(type) {
            state.type = type;
            area.applyOptions({ visible: type === 'line' });
            candles.applyOptions({ visible: type === 'candle' });
            refreshButtons();
            showLatest();
        }

        // Start altid med daglige data; en husket intradagsperiode hentes bagefter.
        var initial = validPeriod(cfg.period) ? cfg.period : DEFAULT_PERIOD;
        if (!cfg.explicit) {
            try {
                var saved = window.sessionStorage.getItem(STORAGE_KEY);
                if (saved && validPeriod(saved)) { initial = saved; }
            } catch (e) { /* ingen sessionStorage */ }
        }
        applyDaily(INTRADAY[initial] ? DEFAULT_PERIOD : initial);
        if (INTRADAY[initial]) { setPeriod(initial); }
    }

    // Startes sidst, så alle hjælpere og formatterere ovenfor er sat.
    try { start(); } catch (e) { useFallback(); }
})();
