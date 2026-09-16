# Contratti di Programma MIT – RFI, parte Investimenti

Estrazione e lettura strutturata dei sei Contratti di Programma fra il Ministero
delle Infrastrutture e dei Trasporti e Rete Ferroviaria Italiana (2017–2021 e
2022–2026, con i relativi aggiornamenti), contenuti in questa repository come PDF.

**Piattaforma interattiva:** https://claude.ai/artifact/Jx3AUvQopmum34mX1uxxqk

La piattaforma è un unico file HTML autonomo (`piattaforma/index.html`, 410 KB):
contiene i dati al suo interno, non chiama servizi esterni e funziona anche
aperta da disco. Per metterla online si veda [Pubblicare il sito](#pubblicare-il-sito).

## Cosa contengono i dati

| File | Contenuto |
|---|---|
| `data/progetti.csv` | 336 interventi: costo, risorse assegnate, fabbisogno residuo, stato attuativo, programma, pagina del PDF |
| `data/serie-storica.csv` | Lo stesso intervento visto in ciascuno dei contratti in cui compare |
| `data/opere-ultimate.csv` | 1.711 righe di movimento sulle opere ultimate, su 1.098 CUP distinti (Tabella C) |
| `data/opere-ultimate-sintesi.csv` | Totali cumulati del costruito per categoria (prospetto della Tabella C) |
| `data/capitoli-piani-gestionali.csv` | Tavola 2: fonti e impieghi di cassa per anno, per capitolo di bilancio e piano gestionale |
| `data/cdp-rfi-dataset.json` | Dataset completo, comprese le tavole di sintesi ufficiali |
| `data/cdp-rfi-app.json` | Versione compatta usata dalla piattaforma, con mappa e attribuzione regionale |
| `data/mappa-regioni.json` | Confini delle regioni italiane ridotti a tracciati SVG |
| `data/cup-da-cercare.csv` | Gli oltre mille CUP citati nei contratti, pronti per essere cercati su OpenCUP |

Tutti gli importi sono in milioni di euro, come nei documenti originali.

## Cosa i documenti **non** contengono

I Contratti di Programma non riportano impegni giuridici né stanziamenti di
competenza per singolo intervento. Riportano tre grandezze diverse:

- il **costo** stimato dell'opera;
- le **risorse assegnate** dal contratto (Sezione 1, «opere in corso finanziate»),
  ripartite per fonte (MEF, FSC/PAC, MIT, PNRR, UE e altro);
- il **fabbisogno residuo** per orizzonte temporale.

Il livello di **capitolo di bilancio e piano gestionale** compare solo nella
Tavola 2, come flusso di cassa annuo aggregato sull'intero contratto: non è
riconducibile al singolo intervento. Per impegni e stanziamenti effettivi servono
il bilancio e il rendiconto dello Stato; per l'avanzamento delle singole opere,
i CUP tramite OpenCUP e ReGiS.

## Pubblicare il sito

Questa repository è privata. GitHub Pages su repository privata richiede un piano
GitHub Pro o Team; sul piano gratuito funziona solo con repository pubblica.
Da qui, tre strade.

**1. Repository pubblica + GitHub Pages** — la via più semplice se i dati possono
essere pubblici (i PDF di partenza sono già documenti pubblici del MIT). Serve
una volta sola *Settings → Pages → Source: GitHub Actions*: il token di GitHub
Actions non ha il permesso di creare il sito Pages, quindi quel passaggio non è
automatizzabile. Fatto quello, il workflow `.github/workflows/pages.yml` pubblica
la piattaforma, i CSV, il JSON e i PDF originali a ogni push su `main`. Indirizzo
risultante: `https://mcaruso17.github.io/rete-ferrovie-italiane/`.

**2. Repository privata + host statico esterno** — Cloudflare Pages, Netlify o
Vercel si collegano a una repository privata e pubblicano un sito visibile a
chiunque, sul piano gratuito. Cloudflare Pages è la scelta con meno vincoli
(nessun limite di banda, dominio personalizzato incluso). Configurazione: nessun
comando di build, cartella di output `piattaforma`. Per servire anche i CSV,
copiare `data/` dentro la cartella pubblicata (è quello che fa il workflow Pages).

**3. Nessun hosting** — il file `piattaforma/index.html` si può inviare per email
o mettere su una chiavetta: si apre in qualsiasi browser e resta completo. In
questo caso la sezione «Scarica i dati» non compare, perché i CSV non sono
affiancati alla pagina.

La sezione «Scarica i dati» in fondo alla pagina appare solo dove la cartella
`data/` è servita insieme all'HTML: altrimenti resta nascosta, invece di mostrare
link che non portano da nessuna parte.

## Metodo di estrazione

I PDF usano font sottoinsiemizzati, flussi di oggetti compressi e pagine ruotate,
e in questo ambiente non era possibile installare librerie di terze parti: il
parser in `tools/` è scritto interamente sulla libreria standard di Python.

- `tools/pdfmini.py` — oggetti PDF, xref stream, object stream, filtri di decodifica
- `tools/ttf.py` — tabella `cmap` dei font incorporati, come ripiego quando il CMap `ToUnicode` è incompleto
- `tools/pdftext.py` — testo con coordinate (matrici di testo, font CID, larghezze dei glifi)
- `tools/tables.py` — segmentazione delle righe in celle e assegnazione alle colonne
- `tools/extract.py` — Tabelle A e B: colonne riconosciute dal bordo destro dei numeri, fascia di testo a sinistra interpretata per struttura
- `tools/extract_extra.py` — Tabella C, Tavola 1 e Tavola 2
- `tools/schema.py` — mappatura delle colonne di ciascun contratto
- `tools/normalize.py`, `tools/build_app.py` — dataset normalizzato e file della piattaforma
- `tools/build_mappa.py` — confini regionali ISTAT ridotti a tracciati SVG (2,7 MB → 28 KB)
- `tools/geo.py` — attribuzione regionale dedotta dai nomi degli interventi
- `tools/wrap_site.py` — documento HTML completo per l'hosting statico
- `tools/build_all.sh` — rigenera tutto, dai PDF ai file della piattaforma

### Verifiche

Ogni riga estratta è confrontata con le identità contabili del documento stesso:

- risorse assegnate = somma delle fonti: **1235 righe su 1235 (100%)**
- costo = risorse assegnate + fabbisogno residuo: **99,8%**, con gli scarti
  circoscritti alle righe che i documenti stessi segnalano a nota (stime di costo
  limitate all'arco di Piano)
- la somma degli interventi del CdP 2022–2026 riproduce la Tavola 1 ufficiale
  (229.401,52 mln €) a meno di quattro centesimi
- le due viste della Tabella A (per status attuativo e per classi tipologiche)
  coincidono al centesimo; nel dataset se ne conta una sola

### I CUP, e la strada per una localizzazione vera

I contratti citano **814 CUP distinti**: 233 accanto agli interventi della
Tabella A (219 interventi su 336, il 65%, pari al 62% del costo del portafoglio)
e 612 nella tabella delle opere ultimate. Sono in `data/cup-da-cercare.csv`.

Il CUP in sé non contiene il luogo: codifica il soggetto titolare, la natura e
il settore dell'investimento. La localizzazione è un campo della banca dati
OpenCUP. Incrociando quei codici con OpenCUP si otterrebbe comune e provincia
esatti per la maggior parte del portafoglio, al posto della stima descritta qui
sotto — e un aggancio diretto al monitoraggio dell'avanzamento reale.

### L'attribuzione regionale è una stima, non un dato

I Contratti non hanno un campo territoriale. La regione mostrata nella mappa è
**dedotta** dai luoghi citati nel nome dell'intervento, confrontati con i comuni
e le province ISTAT: il nome dev'essere un nome proprio, i nomi ambigui valgono
solo per i capoluoghi, e si guarda solo la descrizione dell'intervento, non il
sotto-programma. Copre 253 interventi su 336; il resto sono programmi di rete
senza un luogo nel nome (sicurezza, tecnologie, sistemi informativi).

Un'opera che tocca più regioni ripartisce l'importo **in proporzione a quante
volte ciascuna regione è citata** nella descrizione, dopo aver scartato quelle
sotto il 15% delle menzioni. Una divisione in parti uguali dava metà dell'anello
ferroviario di Roma alla Toscana, per una sola occorrenza di «Firenze» contro sei
di «Roma». Resta un surrogato: il peso vero sarebbe la lunghezza di tratta per
regione, che i documenti non riportano. Le quote sommano a uno, quindi i totali
regionali sommano al totale attribuito. Il **conteggio** degli interventi invece
non si divide: un'opera su due regioni compare nel conteggio di entrambe, quindi
la somma di quella colonna supera il numero di interventi distinti. La tabella
accanto alla mappa mostra i due totali separati, per non lasciare l'ambiguit&agrave;
al lettore.

Confini regionali: ISTAT via [openpolis/geojson-italy](https://github.com/openpolis/geojson-italy), CC BY 4.0.

### Le righe della Tabella C non sono opere

Il dettaglio della Tabella C registra la **variazione del periodo**, non il costo
dell'opera. Lo stesso CUP ricompare a distanza di anni con code di aggiustamento:
`J17E91000000011` vale 45,54 milioni nel 2016, poi 0,01 nel 2020, 0,00 nel 2022 e
−0,56 nel 2024. Nel solo aggiornamento 2025, 433 righe su 903 valgono zero.

Le 1.711 righe corrispondono a **1.098 CUP distinti**, 420 dei quali compaiono in
più di un documento.

Le variazioni dei sei documenti **non si sommano fra loro**: ciascuna è misurata
rispetto alla fotografia precedente della propria serie. Le date di riferimento
sono 2016, 2020, 2021, 2022, 2023 e 2024 — mancano 2017, 2018 e 2019, perché fra
il contratto 2017-2021 e il suo primo aggiornamento non c'è nessun documento — e
in mezzo cambia il ciclo contrattuale, con il perimetro ridefinito. Sommarle dà
11.777 milioni, che non è la variazione rispetto a niente.

Dentro un singolo ciclo la catena invece torna al centesimo:

| | milioni |
|---|---:|
| Cumulato al 31.12.2021 (Tavola 1 del contratto base) | 67.347,95 |
| + variazione 2022 (aggiornamento 2023) | 344,12 |
| + variazione 2023 (aggiornamento 2024) | 365,96 |
| = cumulato al 31.12.2023 | **68.058,03** |
| dichiarato dal prospetto dell'aggiornamento 2025 | 68.058,02 |
| + variazione 2024 (aggiornamento 2025) | 4.438,88 |
| = cumulato al 31.12.2024 | **72.496,91** |
| dichiarato dal prospetto | 72.496,58 |

### Le pagine di prosecuzione delle tabelle

Il dettaglio delle opere ultimate prosegue su pagine che **non ripetono il titolo
della tabella**: nell'aggiornamento 2025 sono tredici pagine, circa 890 righe, che
un riconoscimento basato solo sul titolo salta per intero. Ora quelle pagine si
riconoscono dall'intestazione di colonna (`Codice Riga | CUP | NPP | …`).

Nelle stesse pagine gli importi negativi sono composti con il segno staccato
dalla cifra (`-        0,02`): il riconoscitore stretto dei numeri li scartava,
e con essi l'intera riga.

Verifica: la somma delle 903 righe dell'aggiornamento 2025 fa 4.438,88 milioni
contro i 4.438,56 del totale stampato nella stessa tabella, uno scarto di
trentadue centesimi su arrotondamenti al centesimo.

### Limiti noti

L'aggiornamento 2023 ha una struttura di tabella diversa dagli altri cinque e non
è incluso nel confronto per intervento; le sue opere ultimate restano nel dataset.
Nei font di alcuni documenti la legatura «ti» non è mappata nel CMap `ToUnicode`
e il font incorporato non espone né `cmap` né nomi dei glifi: è stata ricostruita
dal contesto (1241 occorrenze nel corpus) e la scelta è documentata nel codice.

## Rigenerare i dati

```bash
cd tools && ./build_all.sh
```

Oppure passo per passo:

```bash
cd tools
for spec in "../CdP_2017-2021_Investimenti.pdf|cdp2017" \
            "../CdP_2017-2021_Investimenti_Agg2020-2021.pdf|agg2021" \
            "../CdP_2022-2026_Investimenti.pdf|cdp2022" \
            "../CdP_2022-2026_Investimenti_Agg2023.pdf|agg2023" \
            "../CdP_2022-2026_Investimenti_Agg2024.pdf|agg2024" \
            "../CdP_2022-2026_Investimenti_Agg_ 2025.pdf|agg2025"; do
  f="${spec%|*}"; id="${spec#*|}"
  python3 extract.py "$f" "$id" "raw/$id.json"
  python3 extract_extra.py "$f" "$id" "extra/$id.json"
done
python3 normalize.py raw extra ../data/cdp-rfi-dataset.json
python3 build_app.py ../data/cdp-rfi-dataset.json /tmp/app-base.json

# geografia (richiede una copia di openpolis/geojson-italy)
GEO=/percorso/a/geojson-italy/geojson
python3 build_mappa.py "$GEO/limits_IT_regions.geojson" ../data/mappa-regioni.json 0.012 0.004
python3 geo.py "$GEO/limits_IT_municipalities.geojson" "$GEO/limits_IT_provinces.geojson" \
  /tmp/app-base.json ../data/mappa-regioni.json ../data/cdp-rfi-app.json
```
