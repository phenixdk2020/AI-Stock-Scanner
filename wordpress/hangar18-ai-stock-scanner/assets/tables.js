/* Sortering og søgning på alle tabeller (.asc-table-wrap). Virker uden ændringer i de enkelte sider:
   klik på en kolonneoverskrift for at sortere, og skriv i søgefeltet over tabellen for at filtrere.
   Sorteringen huskes i fanen, så den overlever genindlæsningen hvert 15. minut. */
(function () {
    'use strict';
    var SEARCH_FROM = 4;   // Søgefelt fra så mange rækker.
    // Forklaring af kolonnerne, samlet ét sted. Vises ved mus-over og i fold-ud-boksen under tabellen.
    var HELP = {
        'aktie': 'Aktiens symbol. Klik for at åbne aktiesiden.',
        'værdipapir': 'Aktiens symbol. Klik for at åbne aktiesiden.',
        'type': 'Aktie eller ETF (indeksfond).',
        'marked': 'Det land, aktien handles i.',
        'region': 'USA, Norden eller Europa.',
        'handelsdato': 'Dagen for seneste kurs, som scanningen bygger på.',
        'handling': 'Scannerens samlede vurdering: KØB-KANDIDAT (alle regler opfyldt), hold øje, pil ned (salgssignal denne uge), BEHOLD eller SÆLG (ejede aktier). En regelbaseret screening, ikke en anbefaling.',
        'signal': 'Samme vurdering som Handling på mandagslisten. Købskandidat: alle regler opfyldt. Hold øje: mindst ét krav mangler. Salgssignal: StockMap gav salg denne uge. Afvent: alt andet.',
        'stockmap': 'Seneste køb- eller salgssignal ud fra aktiens styrke mod markedet (RSP) med dato. Køb inden for 2 uger er et krav for købskandidater.',
        'tpi': 'Turning Point Indicator, vendepunkter. Vores forenklede udgave: den lange trend (grøn eller rød) og ugens tilstand (oversolgt, neutral eller overkøbt).',
        'mti': 'Momentum Trend Indicator. Kortere trendsignal for aktien: rød, uge grøn, dag grøn eller dobbelt grøn (både uge og dag).',
        'kvalitet': 'Percentil 0-100 mod universet for selskabets rentabilitet, gæld og pengestrøm. Højere er bedre. Mindst 60 kræves for køb.',
        'moat': 'Percentil 0-100 for hvor varig selskabets indtjening ser ud. Højere er bedre.',
        'mss-score': 'MyStockScanner-score: gennemsnit af Kvalitet, Kanal (0-100) og Moat. Siger, hvor godt og fornuftigt prissat selskabet ser ud, ikke om tidspunktet er rigtigt. En høj score er derfor ikke et køb i sig selv.',
        'værdi': 'Percentil 0-100 for hvor billig aktien er på nøgletal mod universet. Højere er billigere.',
        'momentum': 'Percentil 0-100 for kursudviklingen de seneste 1-12 måneder. Højere er stærkere.',
        'kanal': 'Kursens placering i værdikanalen. 50 er midten, og over 50 er den nederste, billige halvdel. Over 100 ligger kursen under kanalen. Mindst 50 kræves for køb.',
        'peg': 'Price/Earnings to Growth: P/E delt med indtjeningsvæksten. Lavere er billigere i forhold til væksten. Under 2 kræves for køb.',
        'asymmetri': 'Forventet gevinst i basisscenariet delt med tabet i det dårlige scenarie. Mindst 3 kræves for køb. ∞ betyder intet beregnet tab.',
        'regnskab': 'Dato og nedtælling til næste regnskab. Inden for 7 dage spærres for køb.',
        'størrelsesklasse': 'Selskabets markedsværdi: Mega (over 200 mia. USD), Large (10-200), Mid (2-10), Small (0,3-2), Micro (under 0,3).',
        'likviditet': 'Hvor meget aktien handles for pr. dag (21 dages gennemsnit). Høj: fra 20 mio. USD. Lav: under 2 mio. USD eller flere end 2 dage uden handel. Lav blokerer køb.',
        'størrelse': 'Foreslået antal aktier ud fra din risiko, som du sætter i boksen Positionsstørrelse.',
        'nyheder': 'Antal positive og negative overskrifter de seneste 7 dage, vurderet af den lokale AI. Kun et hint.',
        'begrundelse': 'De regler, der afgjorde aktiens Handling.',
        'upside %': 'Analytikernes gennemsnitlige kursmål i forhold til kursen nu.',
        'mkt.værdi (mia. usd)': 'Selskabets samlede markedsværdi i milliarder USD.',
        'antal': 'Antal aktier.',
        'købskurs': 'Kursen, aktien blev købt til.',
        'seneste kurs': 'Nyeste kurs fra Yahoo. Forsinket, og den ændrer sig kun, når børsen er åben.',
        'investeret': 'Det samlede købsbeløb.',
        'værdi (kr.)': 'Positionens værdi nu i kroner.',
        'gevinst/tab': 'Værdi minus købsbeløb.',
        'gevinst (kr.)': 'Værdi minus købsbeløb og omkostning i kroner.',
        'resultat (kr.)': 'Salg minus køb, efter omkostninger, i kroner.',
        'afkast': 'Gevinst eller tab i procent.',
        'rsp': 'Afkastet på RSP (S&P 500 med lige vægt) i samme periode, til sammenligning.',
        'handler': 'Antal køb og salg i runden.',
        'salgsgrund': 'Den salgsregel, der lukkede handlen.',
        'isin': 'Aktiens internationale identifikationsnummer.',
        'entry': 'Entry: alle købskrav er opfyldt. Vent: god og billig mod sin egen værdi, men intet købssignal. Nej: grunden står ved siden af. "Dyr mod andre aktier" betyder Værdi under 20. En regelbaseret screening, ikke en anbefaling.',
        'bear %': 'Kursmål i Bear-scenariet om 2 år i forhold til kursen. Bruger lavt P/E, men analytikernes estimat, så det er ikke et værste scenarie.',
        'base %': 'Kursmål i Base-scenariet om 2 år i forhold til kursen.',
        'samlet': 'Samlet score 0-100: gennemsnit af Kvalitet, Moat, Værdi og Kanal. Jo højere, jo bedre og billigere ser selskabet ud. Siger ikke noget om tidspunktet; det gør Entry.',
        'selskab': 'Selskabets navn.',
        'ticker': 'Aktiens symbol hos Yahoo, fx NOVO-B.CO.',
        'sektor': 'Den sektor, selskabet hører til (fra Yahoo, vist på dansk). Ukendt betyder, at scanneren ikke kender den. Bruges til spredning: ligger mange aktier med entry i samme sektor, vises en advarsel.',
        'status': 'Om aktien er aktiv på børsen ifølge kataloget.',
        'handlinger': 'Knapper til at følge aktien eller registrere et køb.',
        'valuta': 'Den valuta, kursen står i.',
        'kursdato': 'Tidspunktet for den seneste kurs.',
        'købsdato': 'Dagen, aktien blev købt.',
        'salgsdato': 'Dagen, aktien blev solgt.',
        'salgskurs / seneste': 'Salgskursen, eller seneste kurs hvis aktien stadig ejes.',
        'købt': 'Købskurs og dato.',
        'solgt': 'Salgskurs og dato.',
        'periode': 'Rundens start- og slutdato.',
        'start (kr.)': 'Beløbet, runden startede med.',
        'slut (kr.)': 'Værdien ved rundens afslutning.',
        'gevinst': 'Værdi minus købsbeløb.'
    };
    // Samme ord betyder noget andet i tabeller uden Playbook-kolonner.
    var HELP_PLAIN = {
        'værdi': 'Positionens værdi nu.',
        'handling': 'Knapper til fx at sælge, slette eller fjerne aktien.',
        'størrelse': 'Selskabets størrelse: Mega til Micro ud fra markedsværdi.'
    };

    function isDetail(row) {
        return row.classList.contains('asc-chart-row') || row.classList.contains('asc-rule-row')
            || row.querySelector(':scope > td[colspan]') !== null;
    }

    /** Rækker samlet med deres grafrække og salgsregel, så de følges ad. */
    function groups(body) {
        var list = [];
        Array.prototype.forEach.call(body.rows, function (row) {
            if (isDetail(row)) {
                if (list.length) { list[list.length - 1].rows.push(row); }
            } else {
                list.push({ main: row, rows: [row] });
            }
        });
        return list;
    }

    /** Cellens første tekst: tallet eller navnet, ikke underteksten. */
    function cellText(cell) {
        if (!cell) { return ''; }
        for (var i = 0; i < cell.childNodes.length; i++) {
            var text = cell.childNodes[i].textContent.trim();
            if (text) { return text; }
        }
        return '';
    }

    /** Dato eller tal i dansk eller engelsk format; null når teksten er andet. */
    function parse(text) {
        var match = text.match(/^(\d{2})-(\d{2})-(\d{4})/);
        if (match) { return Date.UTC(+match[3], +match[2] - 1, +match[1]); }
        match = text.match(/^(?:\S+ )?(\d{4})-(\d{2})-(\d{2})/);
        if (match) { return Date.UTC(+match[1], +match[2] - 1, +match[3]); }
        match = text.replace(/[\s ]/g, '').replace('−', '-').match(/^([+-]?)(\d[\d.,]*)(%|%-point|kr\.?|[A-Z]{3})?$/);
        if (!match) { return null; }
        var digits = match[2];
        if (digits.indexOf(',') !== -1) {
            digits = digits.replace(/\./g, '').replace(',', '.');
        } else if (/^\d{1,3}(\.\d{3})+$/.test(digits)) {
            digits = digits.replace(/\./g, '');
        }
        var value = parseFloat(digits);
        if (isNaN(value)) { return null; }
        return match[1] === '-' ? -value : value;
    }

    function empty(text) {
        return text === '' || text === '–' || text === '-' || text === '—' || text === 'ukendt';
    }

    function compare(a, b, direction) {
        // Tomme felter står altid nederst, uanset retning.
        if (empty(a) || empty(b)) { return empty(a) - empty(b); }
        var x = parse(a), y = parse(b);
        if (x !== null && y !== null) { return (x - y) * direction; }
        if (x !== null || y !== null) { return (x === null ? 1 : -1) * direction; }
        return a.localeCompare(b, 'da', { sensitivity: 'base', numeric: true }) * direction;
    }

    function remember(key, value) {
        try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* kun en bekvemmelighed */ }
    }

    function recall(key) {
        try { return JSON.parse(sessionStorage.getItem(key)); } catch (e) { return null; }
    }

    function sortBy(table, body, column, direction) {
        var list = groups(body);
        var rank = list.map(function (group, index) {
            return { group: group, index: index, text: cellText(group.main.cells[column]) };
        });
        rank.sort(function (a, b) { return compare(a.text, b.text, direction) || a.index - b.index; });
        rank.forEach(function (item) {
            item.group.rows.forEach(function (row) { body.appendChild(row); });
        });
        Array.prototype.forEach.call(table.tHead.rows[0].cells, function (head, index) {
            if (index === column) {
                head.setAttribute('aria-sort', direction > 0 ? 'ascending' : 'descending');
            } else {
                head.removeAttribute('aria-sort');
            }
        });
    }

    function addSorting(table, body, key) {
        Array.prototype.forEach.call(table.tHead.rows[0].cells, function (head, column) {
            var label = head.textContent.trim();
            if (!label) { return; }
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'asc-sort';
            button.textContent = label;
            button.title = (helpFor(label, table) ? helpFor(label, table) + ' ' : '') + 'Klik for at sortere.';
            button.addEventListener('click', function () {
                // Ved første klik står tal med højeste øverst og tekst fra A.
                var state = head.getAttribute('aria-sort');
                var numeric = groups(body).some(function (group) {
                    return parse(cellText(group.main.cells[column])) !== null;
                });
                var direction = state ? (state === 'ascending' ? -1 : 1) : (numeric ? -1 : 1);
                sortBy(table, body, column, direction);
                remember(key, { column: column, direction: direction });
            });
            head.textContent = '';
            head.appendChild(button);
            if (/^(Nyheder|Begrundelse)$/.test(label)) { head.style.minWidth = '13rem'; }   // lange tekster
        });
        var saved = recall(key);
        if (saved && table.tHead.rows[0].cells[saved.column]) {
            sortBy(table, body, saved.column, saved.direction);
        }
    }

    // Forkortelser: vises med prikket streg og forklaring, og samlet i en boks nederst på hver side.
    var TERMS = {
        'MSS': 'MyStockScanner, den tjeneste metoden er bygget ud fra.',
        'TPI': 'Turning Point Indicator: viser, om aktien er ved at vende.',
        'MTI': 'Momentum Trend Indicator: viser, om aktien klarer sig bedre end markedet lige nu.',
        'PEG': 'Price/Earnings to Growth: P/E delt med væksten.',
        'P/E': 'Price/Earnings: kursen delt med indtjeningen pr. aktie.',
        'EPS': 'Earnings Per Share: indtjening pr. aktie.',
        'RSP': 'Invesco S&P 500 Equal Weight ETF: vores målestok for markedet.',
        'ETF': 'Exchange Traded Fund: en indeksfond, der handles som en aktie.',
        'SMA50': 'Gennemsnitskursen over 50 handelsdage (Simple Moving Average).',
        'SMA200': 'Gennemsnitskursen over 200 handelsdage (Simple Moving Average).',
        'ATR': 'Average True Range: hvor meget aktien typisk svinger pr. dag.',
        'ECB': 'Den Europæiske Centralbank. Herfra kommer valutakurserne.',
        'ISIN': 'Aktiens internationale nummer (International Securities Identification Number).',
        'StockMap': 'Kort over aktiens styrke mod markedet. Herfra kommer købs- og salgssignalet.',
        'Moat': 'Voldgrav: det der holder konkurrenterne væk, fx brand eller patenter.',
        'Bear': 'Det dårlige scenarie for kursen om 2 år. Lavt P/E, men analytikernes estimat.',
        'Base': 'Det normale scenarie for kursen om 2 år.',
        'Bull': 'Det gode scenarie for kursen om 2 år.',
        'Asymmetri': 'Forholdet mellem mulig gevinst og muligt tab.',
        'Upside': 'Hvor meget kursen kan stige til et kursmål, i procent.',
        'Likviditet': 'Hvor let aktien kan købes og sælges.',
        'ÅTD': 'År til dato: fra 1. januar til i dag.'
    };
    var TERM_RE = new RegExp('(^|[^A-Za-zÆØÅæøå0-9/])(' + Object.keys(TERMS).map(function (t) {
        return t.replace('/', '\\/');
    }).sort(function (a, b) { return b.length - a.length; }).join('|') + ')(?![A-Za-zÆØÅæøå0-9])');
    var TERM_SKIP = 'a,button,script,style,select,option,textarea,svg,abbr,summary,tbody,details,dl,noscript';

    function markTerms(node, found) {
        var match = TERM_RE.exec(node.nodeValue);
        if (!match) { return; }
        var term = match[2];
        var start = match.index + match[1].length;
        var rest = node.splitText(start);
        rest.nodeValue = rest.nodeValue.slice(term.length);
        var abbr = document.createElement('abbr');
        abbr.className = 'asc-abbr';
        abbr.title = TERMS[term];
        abbr.textContent = term;
        node.parentNode.insertBefore(abbr, rest);
        found[term] = true;
        markTerms(rest, found);
    }

    function addTerms() {
        var root = document.querySelector('.asc-app-content') || document.querySelector('.asc-dashboard, .asc-portfolio');
        if (!root || document.getElementById('asc-help')) { return; }
        var nodes = [];
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            var parent = walker.currentNode.parentElement;
            if (parent && !parent.closest(TERM_SKIP)) { nodes.push(walker.currentNode); }
        }
        var found = {};
        nodes.forEach(function (node) { markTerms(node, found); });
        // Kolonneoverskrifter og tabelceller får ikke streg, men tæller med i boksen.
        var all = root.textContent;
        Object.keys(TERMS).forEach(function (term) {
            if (new RegExp('(^|[^A-Za-zÆØÅæøå0-9/])' + term.replace('/', '\\/') + '(?![A-Za-zÆØÅæøå0-9])').test(all)) {
                found[term] = true;
            }
        });
        var names = Object.keys(found);
        if (!names.length) { return; }
        var box = document.createElement('details');
        box.className = 'asc-col-help asc-page-terms';
        var title = document.createElement('summary');
        title.textContent = 'Forkortelser på denne side';
        var list = document.createElement('dl');
        names.sort(function (a, b) { return a.localeCompare(b, 'da'); }).forEach(function (name) {
            var term = document.createElement('dt');
            term.textContent = name;
            var meaning = document.createElement('dd');
            meaning.textContent = TERMS[name];
            list.appendChild(term);
            list.appendChild(meaning);
        });
        box.appendChild(title);
        box.appendChild(list);
        root.appendChild(box);
    }

    var MARKETS = { CO: 'Danmark', ST: 'Sverige', OL: 'Norge', HE: 'Finland', DE: 'Tyskland', F: 'Tyskland',
        PA: 'Frankrig', AS: 'Holland', MC: 'Spanien', L: 'Storbritannien', SW: 'Schweiz', MI: 'Italien' };

    /** Markedet ud fra symbolet (fx NOVO-B.CO). Null når rækken ikke er en aktie. */
    function marketOf(row) {
        var link = row.cells[0] && row.cells[0].querySelector('a[href*="asc_ticker="]');
        var symbol = link ? new URL(link.href, location.href).searchParams.get('asc_ticker') : cellText(row.cells[0]);
        if (!/^[A-Z0-9^][A-Z0-9.^=-]*$/.test(symbol || '')) { return null; }
        var dot = symbol.lastIndexOf('.');
        return dot === -1 ? 'USA' : (MARKETS[symbol.slice(dot + 1)] || 'Andet');
    }

    function addSearch(wrap, body, key) {
        var total = groups(body).length;
        if (total < SEARCH_FROM) { return; }
        var bar = document.createElement('div');
        bar.className = 'asc-table-tools';
        var input = document.createElement('input');
        input.type = 'search';
        input.placeholder = 'Søg i tabellen …';
        input.setAttribute('aria-label', 'Søg i tabellen');
        var count = document.createElement('span');
        count.className = 'asc-table-count';
        count.setAttribute('role', 'status');
        var names = [];
        groups(body).forEach(function (group) {
            var market = marketOf(group.main);
            if (market && names.indexOf(market) === -1) { names.push(market); }
        });
        var select = null;
        bar.appendChild(input);
        if (names.length > 1) {
            select = document.createElement('select');
            select.setAttribute('aria-label', 'Vælg marked');
            select.add(new Option('Alle markeder', ''));
            names.sort(function (a, b) { return a.localeCompare(b, 'da'); }).forEach(function (name) {
                select.add(new Option(name, name));
            });
            var saved = recall(key + ':market');
            if (saved && names.indexOf(saved) !== -1) { select.value = saved; }
            bar.appendChild(select);
        }
        bar.appendChild(count);
        wrap.parentNode.insertBefore(bar, wrap);

        function apply() {
            var words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
            var market = select ? select.value : '';
            var shown = 0;
            groups(body).forEach(function (group) {
                var text = group.main.textContent.toLowerCase();
                var hit = words.every(function (word) { return text.indexOf(word) !== -1; })
                    && (!market || marketOf(group.main) === market);
                group.rows.forEach(function (row) { row.hidden = !hit; });
                if (hit) { shown++; }
            });
            count.textContent = shown === total ? total + ' rækker' : shown + ' af ' + total + ' rækker';
        }
        input.addEventListener('input', apply);
        if (select) {
            select.addEventListener('change', function () {
                remember(key + ':market', select.value);
                apply();
            });
        }
        apply();
    }

    function helpFor(label, table) {
        var key = label.trim().toLowerCase();
        var plain = !/StockMap|Kvalitet/.test(table.tHead.textContent);
        var scores = /Kvalitet/.test(table.tHead.textContent) && !/StockMap/.test(table.tHead.textContent);
        if (plain && HELP_PLAIN[key]) { return HELP_PLAIN[key]; }
        if (scores && key === 'størrelse') { return HELP_PLAIN[key]; }
        return HELP[key] || '';
    }

    /** Fold-ud-boks under tabellen: virker også på mobil, hvor der ikke er mus-over. */
    function addHelp(wrap, table) {
        var items = [];
        Array.prototype.forEach.call(table.tHead.rows[0].cells, function (head) {
            var label = head.textContent.trim();
            var text = helpFor(label, table);
            if (text) { items.push([label, text]); }
        });
        if (!items.length) { return; }
        var box = document.createElement('details');
        box.className = 'asc-col-help';
        var title = document.createElement('summary');
        title.textContent = 'Hvad betyder kolonnerne?';
        var list = document.createElement('dl');
        items.forEach(function (item) {
            var term = document.createElement('dt');
            term.textContent = item[0];
            var meaning = document.createElement('dd');
            meaning.textContent = item[1];
            list.appendChild(term);
            list.appendChild(meaning);
        });
        box.appendChild(title);
        box.appendChild(list);
        if (document.querySelector('.asc-side-link')) {     // kun på forsiden med menuen findes Hjælp som visning
            var guide = document.createElement('a');
            var url = new URL(location.href);
            url.search = '?asc_view=help';
            url.hash = 'asc-help';
            guide.href = url.href;
            guide.textContent = 'Læs hele hjælpen';
            box.appendChild(guide);
        }
        wrap.parentNode.insertBefore(box, wrap.nextSibling);
    }

    function init() {
        var seen = 0;
        Array.prototype.forEach.call(document.querySelectorAll('.asc-table-wrap'), function (wrap) {
            var table = wrap.querySelector('table');
            if (!table || !table.tHead || !table.tBodies.length) { return; }
            var body = table.tBodies[0];
            var page = new URLSearchParams(location.search).get('asc_view') || '';
            var key = 'asc-sort:' + location.pathname + ':' + page + ':' + (seen++);
            if (!groups(body).length) { return; }
            if (table.tHead.rows[0].cells.length > 7 || table.scrollWidth > wrap.clientWidth) { wrap.classList.add('asc-wide'); }
            addHelp(wrap, table);
            addSorting(table, body, key);
            addSearch(wrap, body, key);
        });
    }

    function start() {
        init();
        addTerms();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
