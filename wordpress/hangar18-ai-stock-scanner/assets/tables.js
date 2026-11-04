/* Sortering og søgning på alle tabeller (.asc-table-wrap). Virker uden ændringer i de enkelte sider:
   klik på en kolonneoverskrift for at sortere, og skriv i søgefeltet over tabellen for at filtrere.
   Sorteringen huskes i fanen, så den overlever genindlæsningen hvert 15. minut. */
(function () {
    'use strict';
    var SEARCH_FROM = 4;   // Søgefelt fra så mange rækker.

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
            button.title = 'Sortér efter ' + label;
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
        });
        var saved = recall(key);
        if (saved && table.tHead.rows[0].cells[saved.column]) {
            sortBy(table, body, saved.column, saved.direction);
        }
    }

    function addSearch(wrap, body) {
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
        count.textContent = total + ' rækker';
        bar.appendChild(input);
        bar.appendChild(count);
        wrap.parentNode.insertBefore(bar, wrap);
        input.addEventListener('input', function () {
            var words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
            var shown = 0;
            groups(body).forEach(function (group) {
                var text = group.main.textContent.toLowerCase();
                var hit = words.every(function (word) { return text.indexOf(word) !== -1; });
                group.rows.forEach(function (row) { row.hidden = !hit; });
                if (hit) { shown++; }
            });
            count.textContent = words.length ? shown + ' af ' + total + ' rækker' : total + ' rækker';
        });
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
            addSorting(table, body, key);
            addSearch(wrap, body);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
