<?php
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

/** Hjælp: sådan læses Playbook, kolonner og signaler. Ren tekst uden data, så der intet er at escape. */
final class ASC_Help {
    public static function register(): void {
        add_shortcode('ai_stock_help', [self::class, 'render']);
    }

    /** @param array<int, array{0: string, 1: string}> $rows */
    private static function terms(array $rows): string {
        $html = '<dl class="asc-help-terms">';
        foreach ($rows as $row) {
            $html .= '<dt>' . esc_html($row[0]) . '</dt><dd>' . esc_html($row[1]) . '</dd>';
        }
        return $html . '</dl>';
    }

    public static function render(): string {
        wp_enqueue_style('hangar18-asc');
        ob_start();
        echo '<section class="asc-dashboard asc-help" id="asc-help"><h2>Hjælp: sådan læser du tallene</h2>';
        echo '<p>Scanneren stiller tre spørgsmål i fast rækkefølge. Alle kolonner hører til ét af dem. '
            . 'Det er en screening efter faste regler, ikke en købsanbefaling.</p>';

        echo '<h3>Hvad bruges siderne til?</h3>';
        echo self::terms([
            ['Overblik', 'Forsiden: antal køb, aktier på watchlisten og scannerresultater, med links videre.'],
            ['Min portefølje', 'De aktier, du selv ejer: køb, værdi, gevinst og salgsregler. Privat, kun du ser den.'],
            ['Danske aktier', 'Katalog over aktier på den danske børs. Søg, følg en aktie, eller registrér et køb.'],
            ['Watchlist', 'Aktier, du vil følge uden at eje dem. Kommer med i næste scanning. Privat.'],
            ['Aktie', 'Alt om én aktie: graf, Playbook-analyse, Bear/Base/Bull, regnskab og nyheder. Søg, eller klik på et symbol i en tabel.'],
            ['Aktiescanner', 'Kort liste over aktierne fra mandagslisten med score og signal. Ikke hele markedet.'],
            ['Playbook → Mandagsliste', 'Ugens vigtigste side: fuld analyse af research-listen, dine aktier og universets kandidater (★).'],
            ['Playbook → Screenere', 'Faste søgninger i universet. Triple Green: stærk trend på alle tidsskalaer. TPI-trend: nordisk optrend med et fald. Stock of the Day: stort amerikansk selskab i optrend med et fald.'],
            ['Playbook → Værdi & entry', 'Start her for at finde aktier: hele universet med svar på, om aktien er billig, og om der er en entry nu.'],
            ['Playbook → Aktie-scores', 'Alle cirka 300 aktier i universet med scores. Globalt eller inden for regionen. Her finder du andre aktier end dem på mandagslisten.'],
            ['Playbook → Papirportefølje', 'Scannerens egen test, fælles for alle brugere: den køber og sælger selv efter reglerne med fiktive penge, så vi kan se, om de virker.'],
            ['Simulator', 'Din egen virtuelle børs: køb aktier for fiktive penge, og følg dem i 30 dage mod RSP. Privat.'],
            ['Analyse', 'Bear/Base/Bull for en valgt aktie, en beregner hvor du selv kan ændre tallene, og signalfordelingen.'],
            ['Hjælp', 'Denne side.'],
            ['Indstillinger', 'Oplysninger om, hvor kurser og valutakurser kommer fra. Administratoren finder også links til datakilder og opdatering af pluginet.'],
        ]);

        echo '<h3>De tre spørgsmål</h3><ol>';
        echo '<li><strong>Er det et godt selskab?</strong> Se Kvalitet og Moat.</li>';
        echo '<li><strong>Er prisen fornuftig?</strong> Se Kanal, PEG, Asymmetri og Værdi.</li>';
        echo '<li><strong>Er tidspunktet rigtigt?</strong> Se StockMap, TPI, MTI og Regnskab.</li></ol>';
        echo '<p>Først når alle tre er i orden, står der KØB-KANDIDAT. Derfor kan en aktie med en høj MSS-score '
            . 'godt stå som "pil ned": selskabet er godt, men tidspunktet er dårligt.</p>';

        echo '<h3>Hvad betyder 0-100?</h3>';
        echo '<p>Kvalitet, Moat, Værdi og Momentum er percentiler. 99 betyder, at aktien er bedre end 99 % af '
            . 'de cirka 300 aktier i universet, og 5 betyder, at kun 5 % er dårligere. Det er altså en placering '
            . 'mod de andre aktier, ikke en karakter og ikke en sandsynlighed for gevinst.</p>';

        echo '<h3>Handling</h3>';
        echo self::terms([
            ['KØB-KANDIDAT', 'Alle købskrav er opfyldt (se listen nedenfor). Det stærkeste signal, scanneren giver.'],
            ['hold øje', 'Mindst ét krav mangler. Begrundelse-kolonnen siger hvilket.'],
            ['pil ned', 'StockMap gav salgssignal denne uge. Gælder aktier, du ikke ejer: køb ikke nu.'],
            ['BEHOLD (ejet)', 'Aktien er i din egen portefølje på hjemmesiden, og ingen salgsregel er ramt efter dine købsdatoer. Vises kun for dine egne aktier.'],
            ['SÆLG (ejet)', 'Aktien er i din egen portefølje, og en salgsregel er ramt efter din købsdato.'],
        ]);

        echo '<h3>Bear / Base / Bull</h3>';
        echo '<p>Tre kort med et kursmål hver. Kursmålet er et regnestykke: forventet EPS (indtjening pr. aktie) ved horisonten, '
            . 'normalt to år frem, gange en P/E. Bear bruger den laveste, Base den midterste og Bull den højeste P/E fra aktiens '
            . 'egen historie. EPS kommer fra analytikernes estimater. Det er ikke en prognose for kursen.</p>';
        echo self::terms([
            ['Kursmål', 'EPS ved horisonten gange P/E for scenariet. Kortet viser regnestykket nederst, fx "EPS 5,00 × P/E 15,0".'],
            ['Upside', 'Hvor mange procent kursmålet ligger over (+) eller under (−) kursen nu.'],
            ['Årligt', 'Det årlige afkast, der skal til for at nå kursmålet over horisonten.'],
            ['Kurs nu', 'Står over kortene, og en linje under dem siger, hvor kursen ligger: under Bear, mellem Bear og Base, mellem Base og Bull eller over Bull.'],
            ['Asymmetri', 'Upside ved Base delt med nedsiden ved Bear. ∞ betyder, at kursen allerede ligger under Bear (ingen nedside i regnestykket).'],
        ]);
        echo '<p>Scenarierne findes i analysepanelet på aktiesiden og i simulatorens opslag, og på Analyse-siden kan du vælge en aktie og '
            . 'rette EPS og P/E i den manuelle beregner. "Ikke beregnet endnu" betyder, at aktien mangler positive EPS-estimater eller '
            . 'P/E-historik; følg aktien, så kommer den med ved næste kørsel.</p>';

        echo '<h3>Krav til en KØB-KANDIDAT</h3><ul>';
        foreach ([
            'StockMap-køb inden for de seneste 2 uger',
            'Kvalitet mindst 60',
            'Kanal mindst 50 (kursen i den billige halvdel af værdikanalen)',
            'PEG under 2, når den kendes',
            'Asymmetri mindst 3, når den kendes',
            'Intet regnskab inden for 7 dage',
            'Ingen faldende indtjeningsestimater (value trap)',
            'Ikke Lav likviditet, og ingen stor negativ nyhed',
        ] as $rule) {
            echo '<li>' . esc_html($rule) . '</li>';
        }
        echo '</ul>';

        echo '<h3>1. Godt selskab?</h3>';
        echo self::terms([
            ['Kvalitet', 'Rentabilitet, gæld og pengestrøm mod universet. Højere er bedre.'],
            ['Moat', 'Hvor varig indtjeningen ser ud, altså om selskabet kan holde konkurrenterne væk. Højere er bedre.'],
            ['MSS-score', 'Gennemsnittet af Kvalitet, Kanal (afskåret til 0-100) og Moat. Den samler spørgsmål 1 og noget af spørgsmål 2, men siger intet om tidspunktet. "–" betyder, at et af tallene mangler.'],
        ]);

        echo '<h3>2. Fornuftig pris?</h3>';
        echo self::terms([
            ['Kanal', 'Kursen mod aktiens egen beregnede værdi ud fra indtjening og historisk P/E. 50 er midten, over 50 er den billige halvdel, og over 100 ligger kursen under kanalen.'],
            ['Værdi', 'Hvor billig aktien er på nøgletal mod de andre aktier. Højere er billigere.'],
            ['PEG', 'P/E delt med indtjeningsvækst. Under 1 er billigt, og over 2 er dyrt i forhold til væksten.'],
            ['Asymmetri', 'Mulig gevinst delt med muligt tab. 3 betyder tre gange så meget at vinde som at tabe. ∞ betyder, at der ikke er beregnet noget tab.'],
        ]);
        echo '<p><strong>Kanal og Værdi kan godt være uenige.</strong> Værdi sammenligner med andre aktier, mens Kanal '
            . 'sammenligner med aktiens egen historie. En kvalitetsaktie er ofte dyr mod andre, men billig mod sig selv.</p>';

        echo '<h3>3. Rigtigt tidspunkt?</h3>';
        echo self::terms([
            ['StockMap', 'Seneste købs- eller salgssignal med dato, ud fra aktiens styrke mod markedet (RSP). Vurderes ugentligt.'],
            ['TPI', 'To dele: "grøn" eller "rød" er den lange trend (over en stigende 40-ugers linje), og "oversolgt", "neutral" eller "overkøbt" er de seneste 4 uger mod aktiens egen historie. Grøn/oversolgt er et fald i en optrend.'],
            ['MTI', 'Kortere trend: rød, uge grøn, dag grøn eller dobbelt grøn (både uge og dag).'],
            ['Momentum', 'Kursudviklingen mod de andre aktier. Højere er stærkere.'],
            ['Regnskab', 'Dato og nedtælling. Inden for 7 dage spærres for køb, og fra 14 dage før vises regnskabsrisiko.'],
            ['Regnskabsrisiko', 'Lav, Middel eller Høj ud fra lavere estimater, negative nyheder og stor kursstigning. Et risikomål, ikke et salgssignal.'],
        ]);

        echo '<h3>Praktisk</h3>';
        echo self::terms([
            ['Størrelsesklasse', 'Selskabets markedsværdi: Mega, Large, Mid, Small eller Micro.'],
            ['Likviditet', 'Hvor meget aktien handles for pr. dag. Lav betyder, at det kan være svært at købe og sælge uden at flytte kursen, og den blokerer køb.'],
            ['Størrelse', 'På mandagslisten: foreslået antal aktier ud fra din risiko, som du sætter i boksen Positionsstørrelse på mandagslisten, med stop ved kurs minus 3 gange ATR.'],
            ['Nyheder', 'Positive og negative overskrifter de seneste 7 dage, vurderet af den lokale AI. Kun et hint.'],
            ['Begrundelse', 'De regler, der afgjorde Handling. Start her, når du undrer dig.'],
        ]);

        echo '<h3>Værdi &amp; entry</h3>';
        echo self::terms([
            ['Entry', 'Alle købskrav er opfyldt, altså det samme som KØB-KANDIDAT.'],
            ['Vent: billig, men intet købssignal', 'Aktien er god og billig nok, men StockMap har ikke givet køb. Hold øje med den.'],
            ['Nej', 'Aktien falder fra af den grund, der står: salgssignal, for lidt handel, svag kvalitet eller ikke billig.'],
            ['Ingen vurdering', 'Der mangler estimater eller P/E-historik, så scanneren gætter ikke.'],
            ['Bear % og Base %', 'Kursmålet i de to scenarier om 2 år i forhold til kursen. Se Bear / Base / Bull.'],
        ]);

        echo '<h3>Aktie-scores og screenere</h3>';
        echo self::terms([
            ['Region', 'USA, Norden eller Europa.'],
            ['Upside %', 'Analytikernes gennemsnitlige kursmål i forhold til kursen nu.'],
            ['Mkt.værdi (mia. USD)', 'Selskabets samlede markedsværdi i milliarder USD.'],
            ['Størrelse', 'Her: selskabets størrelsesklasse, Mega til Micro.'],
        ]);

        echo '<h3>Aktiesidens graf og nøgletal</h3>';
        echo self::terms([
            ['Perioder', '1 D og 1 U er intradag (5 og 15 minutter), 1 M til 5 Å er daglige kurser. ÅTD er siden nytår. Standard er 6 M, og valget huskes i fanen.'],
            ['Linje / Candles', 'Linje viser lukkekursen (grøn ved stigning i perioden, rød ved fald). Candles viser åbning, høj, lav og luk for hver dag.'],
            ['Trådkors', 'Før musen hen over grafen (på en telefon: hold fingeren nede på grafen og træk) for at se dato, kurs, ændring i kroner og procent siden periodens start og volumen. Uden mus vises seneste kurs.'],
            ['Zoom', 'Brug musehjulet, knib på en telefon, eller træk grafen sidelæns. Vælg en periode for at nulstille.'],
            ['SMA50 / SMA200', 'Glidende gennemsnit af lukkekursen over 50 og 200 handelsdage. Kun på daglige perioder; slås til og fra med knapperne.'],
            ['K, V og S', 'Dine handler på grafen: K = køb i porteføljen, V = køb i simulatoren, S = salg i simulatoren.'],
            ['Åbning, Høj, Lav, Volumen', 'Tal fra seneste handelsdag i kurshistorikken.'],
            ['52 ugers høj / lav', 'Højeste og laveste kurs det seneste år, beregnet ud fra kurshistorikken. Vises kun med mindst et års historik.'],
            ['P/E', 'Kurs delt med forventet EPS i dag fra Playbook-analysen. "–" hvis aktien ikke er analyseret eller EPS ikke er positiv.'],
            ['Markedsværdi', 'Selskabets samlede værdi på børsen i mia. USD fra Playbook-universet. "–" hvis den ikke findes.'],
        ]);

        echo '<h3>Aktiescanner</h3>';
        echo self::terms([
            ['Type', 'Aktie eller ETF (indeksfond).'],
            ['Marked', 'Det land, aktien handles i. "Andet" er øvrige børser.'],
            ['Handelsdato', 'Dagen for seneste kurs, som scanningen bygger på.'],
            ['Signal', 'Købskandidat, Hold øje, Salgssignal eller Afvent. Samme vurdering som Handling.'],
        ]);

        echo '<h3>Portefølje, watchlist og simulator</h3>';
        echo self::terms([
            ['Antal', 'Antal aktier.'],
            ['Købskurs', 'Kursen, aktien blev købt til.'],
            ['Seneste kurs', 'Nyeste kurs fra Yahoo. Forsinket, og den ændrer sig kun, når børsen er åben.'],
            ['Investeret', 'Det samlede købsbeløb.'],
            ['Værdi', 'Her: positionens værdi nu.'],
            ['Gevinst/tab', 'Værdi minus købsbeløb, i beløb og procent.'],
            ['Valuta og Kursdato', 'Kursens valuta og tidspunkt.'],
            ['Resultat', 'Salg minus køb, efter omkostninger.'],
            ['Periode, Start og Slut', 'En afsluttet simulatorrundes datoer og beløb.'],
            ['Afkast og RSP', 'Rundens afkast mod S&P 500 med lige vægt i samme periode.'],
            ['Handler', 'Antal køb og salg i runden.'],
        ]);

        echo '<h3>Papirportefølje</h3>';
        echo self::terms([
            ['Købsdato og Købskurs', 'Hvornår og til hvilken kurs scanneren købte.'],
            ['Salgsdato og Salgskurs', 'Hvornår og til hvilken kurs den solgte, eller seneste kurs hvis den stadig ejer aktien.'],
            ['Afkast', 'Gevinst eller tab i procent.'],
            ['Salgsgrund', 'Den salgsregel, der lukkede handlen.'],
        ]);

        echo '<h3>Danske aktier</h3>';
        echo self::terms([
            ['Selskab, Ticker og ISIN', 'Navn, symbol og internationalt identifikationsnummer.'],
            ['Sektor', 'Den branche, selskabet hører til.'],
            ['Status', 'Om aktien er aktiv på børsen ifølge kataloget.'],
            ['Handlinger', 'Knapper til at følge aktien eller registrere et køb.'],
        ]);

        echo '<h3>Eksempler</h3>';
        echo self::terms([
            ['ASML.AS: pil ned, Kvalitet 99, Moat 96, MSS 98', 'Et meget stærkt selskab, men StockMap gav salg 30/10, og MTI er rød. TPI er grøn/oversolgt: optrend med et fald. Godt selskab, forkert tidspunkt. Vent på et nyt StockMap-køb.'],
            ['CAT: pil ned, TPI rød/oversolgt, Momentum 19', 'Middel kvalitet i en nedadgående trend. Billig kan blive billigere.'],
            ['HARB-B.CO: pil ned, Kvalitet 16, Værdi 80, MSS –', 'Billig, men svag kvalitet og meget lidt handel. Lav pris alene er ikke nok.'],
        ]);

        echo '<h3>Sådan kan du bruge det</h3><ol>';
        echo '<li>Mandag: åbn Playbook → Mandagsliste, og sortér på Handling.</li>';
        echo '<li>Læs Begrundelse for hver KØB-KANDIDAT.</li>';
        echo '<li>Åbn aktien, og tjek graf, regnskabsdato og nyheder.</li>';
        echo '<li>Prøv først i Simulatoren, før du bruger rigtige penge.</li></ol>';

        echo '<p class="asc-disclaimer">Tallene er forsinkede og kan være forkerte. Ikke investeringsrådgivning.</p>';
        echo '</section>';
        return (string)ob_get_clean();
    }
}
