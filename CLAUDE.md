# Note per chi riprende il lavoro

Questo file viene caricato all'avvio di ogni sessione. Serve a non ripartire da
zero: dice dove sta il lavoro, perché certe scelte sono state fatte e cosa resta
aperto. Il README descrive il progetto per chi lo guarda da fuori; qui c'è quello
che serve per lavorarci dentro.

## Com'è fatta la catena

Tutto parte dai sei PDF dei Contratti di Programma nella radice del repository.
Nessuna libreria di terze parti: il parser PDF è scritto in Python puro perché
all'inizio del progetto PyPI non era raggiungibile, e va tenuto così.

```
tools/pdfmini.py     livello oggetti PDF (xref stream, ObjStm, Flate, LZW, predictor PNG)
tools/ttf.py         cmap e post dei font incorporati, quando il ToUnicode è incompleto
tools/pdftext.py     testo con coordinate, rotazione pagina, legature del corpus
tools/tables.py      colonne dedotte dai bordi destri, "atomi" mai spezzati da un confine
tools/extract.py     Tabella A e B (gli interventi)
tools/extract_extra.py  Tabella C (opere ultimate), Tavola 1, Tavola 2
tools/normalize.py   unisce i sei documenti in data/cdp-rfi-dataset.json
tools/validate.py    13 controlli sui dati contro i totali stampati nei PDF
tools/export_csv.py  i CSV scaricabili
tools/build_app.py   versione compatta per la piattaforma
tools/build_mappa.py confini regionali ISTAT -> tracciati SVG (esporta la proiezione)
tools/toponimi.py    regole di lettura dei nomi di luogo, condivise
tools/geo.py         attribuzione regionale
tools/comuni.py      attribuzione comunale e spezzate schematiche
tools/rete_osm.py    rete ferroviaria da un estratto OSM (fuori da build_all.sh)
tools/build_rete.py  la rete sulla proiezione della mappa, semplificata
tools/aggancio.py    intervento -> linea OSM (nome + comuni attraversati)
tools/extract_servizi.py  CdP Servizi, Allegato 3: registro ufficiale linee
tools/extract_servizi_fin.py  CdP Servizi, Allegati 4a, 4b, 4c e 12 (tabelle finanziarie)
tools/build_servizi.py    le viste Servizi della piattaforma (app["servizi"])
tools/registro_rfi.py     intervento -> linea RFI (nome) e livello "confermato"
tools/piano_commerciale.py  scarica i progetti del Piano Commerciale RFI (fuori da build_all.sh)
tools/aggancio_pc.py      intervento -> tracciato dichiarato da RFI, e prova degli agganci dedotti
tools/rete_rfi.py         la rete RFI sulla mappa, agganciata al registro delle linee per codice
tools/geometria.py        funzioni geometriche condivise (proiezione, semplificazione, prossimita')
tools/extract_pc.py       schede progetto dal PDF del Piano Commerciale (codice CdP, benefici, anno)
tools/inject_data.py incorpora i dati nel file unico della piattaforma
tools/wrap_site.py   dal frammento al documento HTML completo
tools/audit.py       cerca pagine con tabelle non riconosciute
```

Ricostruire tutto: `cd tools && sh build_all.sh` (circa due minuti).

## Prerequisiti d'ambiente

`build_all.sh` ha bisogno dei confini ISTAT, che non stanno in questo repository.
Se la cartella non c'è, si riclona da GitHub:

```sh
git clone --depth 1 https://github.com/openpolis/geojson-italy /home/user/openpolis/geojson-italy
```

Senza, lo script salta la geografia e lo dice: mappa, regioni e comuni non
vengono aggiornati, il resto sì.

`data/rete-ferroviaria.geojson` e' versionato come i PDF, quindi la pagina Rete
ferroviaria si ricostruisce senza rete. Si rigenera solo per aggiornare la
geometria, e allora serve `osmium`, unica dipendenza esterna del progetto: per
questo il passo sta fuori da build_all.sh.

```sh
pip install osmium
curl -O https://download.openstreetmap.fr/extracts/europe/italy-latest.osm.pbf
python3 tools/rete_osm.py italy-latest.osm.pbf
```

Per provare la piattaforma c'è Chromium headless in
`/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell`.
Playwright non è installabile. Il modo che funziona è pilotare il DOM con uno
script iniettato in una copia della pagina e poi `--dump-dom`: si vedono i
risultati veri delle interazioni, non solo che la pagina si carica.

## Le regole che non si negoziano

**I dati devono tornare con i documenti.** `tools/validate.py` confronta le somme
ricostruite con i totali stampati nei PDF. Sta a 13 controlli su 13 e ci deve
restare: se una modifica lo fa scendere, la modifica è sbagliata finché non si
capisce perché. Il rapporto finisce in `data/validazione.txt` e viene pubblicato
col sito.

**Non si inventano dati che sembrano veri.** Questo progetto vive di
verificabilità. Due esempi concreti di dove passa la linea:

- I comuni della pagina *Comuni* sono quelli **nominati** nel titolo
  dell'opera, non quelli attraversati dalla ferrovia. I Contratti di Programma
  non contengono geometrie. La differenza è scritta in grassetto sulla pagina e
  nel Metodo, e va tenuta lì.
- Le spezzate tratteggiate fra i comuni sono un aiuto visivo, non un tracciato.
  Da quelle linee **non** si ricava nessun comune nuovo: sarebbe un dato falso
  con l'aria di un dato vero.

**Quando un numero cambia, si dice perché.** Diversi numeri pubblicati sono stati
corretti in corsa dopo aver trovato errori di estrazione. Ogni correzione sta nel
messaggio di commit con la causa, non solo con l'effetto.

## Cose imparate sui PDF di RFI, che costano ore se le riscopri

- La Tabella A stampa gli stessi interventi in **due viste** (per stato attuativo
  e per classi). Contarle entrambe raddoppia i totali. Si tiene `vista == "status"`.
- I richiami di nota finiscono **dentro** al numero, non ai lati: `5.7*79,42`.
- Nella Tavola 2 il trattino è uno **zero stampato**, non un dato mancante.
- Sempre nella Tavola 2 il numero di riga può coincidere con un importo della
  stessa riga (la riga 15 vale 15 mln nel 2023): va scartato una volta sola.
- Il CdP 2017-2021 alterna **due formati di data** nella stessa colonna
  (`31/12/2016` e `30.11.2014`), e alcune righe hanno `n.a.`.
- Il titolo della Tabella C a volte ha i due punti, a volte no, e il dettaglio
  prosegue su pagine che non ripetono il titolo: si riconoscono dall'intestazione.
- Sei formule della Tavola 2 sono **stampate sbagliate da RFI** (righe che
  richiamano se stesse, intervalli che sconfinano). Sono elencate una per una
  nell'errata dentro `validate.py`, con la correzione verificata su tutti gli anni.
- In `agg2024` il documento **riusa i numeri di riga** 29, 30 e 31 in due blocchi
  diversi.

## Ambiente di rete

L'egress è deciso dalla policy dell'environment, non dal codice. Per buona parte
del progetto passavano solo GitHub via git, i registri di pacchetti e la ricerca
web, mentre overpass, geofabrik, rfi.it e dati.gov.it rispondevano 403. Se una
fonte esterna serve e non risponde, **prima di dire che è irraggiungibile**
controlla con `curl -sS "$HTTPS_PROXY/__agentproxy/status"` se il rifiuto viene
dal gateway: la policy può essere stata allargata nel frattempo.

## Il registro delle linee e la sua geometria

Il registro ufficiale e' l'Allegato 3 dei CdP Servizi (codice, nome, km,
treni/giorno). La rete RFI del Piano Commerciale (`data/rete-rfi.geojson`,
scaricata da `piano_commerciale.py`) usa lo stesso codice con la lettera
cambiata: **C->K, F->J, N->R, A->A** (C001 = K001). Non e' documentato da RFI:
si accetta solo se anche il nome ha una parola significativa in comune.
290 linee su 299 hanno cosi' il tracciato; mancano le 4 sezioni AV affiancate
(F023AV...), 3 linee subentrate dalle Regioni, Bari-Bitritto e Vievola-Breil.

Da qui in poi **la rete di riferimento e' RFI**, non OSM: la mappa disegna la
rete RFI, le linee cliccabili sono quelle del registro, e registro_rfi.py
aggancia gli interventi con due prove (nome dei capi, comuni attraversati
dalla linea RFI). OSM resta come strato facoltativo (ferrovie non RFI,
cantieri), come fonte della data di apertura quando una linea OSM ricopre
quasi tutto il tracciato RFI, e come indizio aggiuntivo nella scheda.
"Confermato" richiede ancora alta su entrambi e un capo comune non nodo, e si
toglie quando il tracciato dichiarato da RFI lo smentisce.

Le quote di sovrapposizione si misurano sulla lunghezza (punti a passo
costante, ognuno alla linea piu' vicina), non sui vertici: su tratte corte due
vertici in stazione pesavano un terzo. Una linea "porta" un tracciato
dichiarato se ne ha almeno il 20% e 3 km, oppure il 60%.

Nell'estrazione dell'Allegato 3: i codici possono finire in AV (F023AV), le
colonne si spostano fra un'edizione e l'altra (la riga si ancora al codice), i
nomi lunghi vanno a capo sopra e sotto la riga del codice, e un numero da solo
al posto del nome e' un rimando a nota (F055 risultava chiamata "1").

## La terza fonte: il Piano Commerciale RFI

RFI pubblica il Piano Commerciale anche come servizi ArcGIS pubblici
(`services3.arcgis.com/GS5pg5GvYXCMCEen`, organizzazione RFI). Nei layer
"Scenari infrastrutturali" tratte e localita' di progetto hanno il campo
"Riferimento CdP-I" con i codici intervento: il legame e' dichiarato, non
dedotto. `data/piano-commerciale-2026.json` e' un estratto versionato (solo i
campi mostrati e la geometria semplificata): la scheda del servizio **non indica
una licenza**, quindi non si ripubblica la geometria come file scaricabile.

Lo stesso dato mette alla prova gli agganci dedotti. Primo esito (settembre
2026): le associazioni OSM "alta" coincidono col tracciato RFI in 31 casi su 35,
le "media" in 40 su 241. Le conferme smentite si tolgono (P247). La rete RFI
completa (`TrattePC2026`, 2.414 tratte) e il PDF del Piano Commerciale (847
pagine) ora sono usati: vedi sotto.

Il PDF del Piano Commerciale (`PianoCommerciale_ed_ottobre_2025.pdf`, scaricato
dall'hub ArcGIS di RFI) ha una scheda per progetto nella sezione "Progetti per
regione" (da pagina 375), con la riga "Rif. CdP-I: <codici> - <descrizione>".
extract_pc.py ne legge titolo, anno di attivazione, misura PNRR, descrizione,
benefici e il riquadro dei numeri. Il testo e' su due colonne mescolate riga
per riga: si separano per ascissa (300 punti). Le etichette dei benefici sono
centrate sul blocco di testo, quindi si assegnano per altezza, non per riga.
In testata a destra "Benefici commerciali a completamento del progetto" e' una
didascalia, non l'inizio dei benefici. 181 progetti con codice, 133 interventi;
con la mappa 2026, 140 interventi su 336 hanno un riferimento scritto da RFI.

## Le due parti nella piattaforma

Ogni sezione ha una vista Investimenti e una vista Servizi (`.solo-inv` e
`.solo-srv`), scelte dal selettore in testata e scritte nell'indirizzo
(`#/servizi/quadro`), cosi' un link porta alla vista giusta. La parte Servizi non
ha la struttura degli Investimenti e **non va forzata a imitarla**: non ci sono
opere con costo e copertura. Le viste mostrano quello che il contratto contiene:

- Quadro e Capitoli: Allegato 4b (fonti per cassa per legge e capitolo), in
  ogni edizione leggibile; 4a (impieghi per competenza) solo nel contratto base;
- Interventi: Allegato 4c (fondi straordinari per CUP e decreto) e Allegato 12
  (opere PNRR del CdP-S). Valgono meno del 2% del totale, e la pagina lo dice;
- Mappa: solo le regioni scritte nei nomi PNRR; Comuni: le sedi DOIT nominate;
- Rete: il registro dell'Allegato 3 con i treni al giorno edizione per edizione;
- Opere concluse: il residuo dei contratti Servizi precedenti (rigo 4 del 4b).

L'atto integrativo 2025 porta gli allegati in scansione (13 pagine senza
testo): non c'e' OCR nell'ambiente, e le sue modifiche sono riassorbite nel 4b
dell'atto 2026. Nell'atto 2026 l'Allegato 3 ha cambiato titolo ("Elenco linee",
non piu' "Gruppi Linee"): l'estrattore lo scartava e il registro si fermava al
2024. I suoi km hanno un decimale invece di tre, per questo la tolleranza sui
totali cresce con la radice del numero di righe. Il totale generale stampato del
4c 2026 (150,83) non e' la somma dei suoi totali per fonte (147,79): incoerenza
della fonte, segnalata e non corretta.

## Cosa resta aperto

1. **Agganciare gli interventi alle linee.** La geometria ora c'è: la pagina
   *Rete ferroviaria* disegna i tracciati veri da OpenStreetMap
   (`data/rete-ferroviaria.geojson`, 1.773 polilinee). Quello che manca è il
   legame fra un intervento e la linea su cui insiste. 190 interventi su 336
   hanno un nome a forma di tratta, quindi agganciabile per nome, ma serve
   verifica manuale: i nomi dei capi tratta nei contratti non coincidono sempre
   con i nomi OSM, e un aggancio sbagliato produrrebbe esattamente il tipo di
   dato falso che questo progetto evita.

   Da lì si arriverebbe ai comuni realmente attraversati, per intersezione con i
   confini ISTAT. Finché quel legame non è verificato, le due cose restano
   separate di proposito: la pagina *Comuni* continua a mostrare i comuni
   nominati, e la rete sta in una pagina sua senza che nessun dato ne derivi.
   Le spezzate schematiche non sono state toccate.
2. **La localizzazione dei CUP.** `data/cup-da-cercare.csv` ha 1.971 righe pronte
   per un export OpenCUP. Il CUP **non** contiene geografia: verificato su 130
   interventi mono-regione, 127 iniziano con la stessa lettera. Va interrogata la
   banca dati, non decifrato il codice.
3. **ePIR ed ePOD di RFI** (`epir.rfi.it`, `epod.rfi.it`) hanno le caratteristiche
   ufficiali linea per linea, ma **richiedono registrazione**: non bastano rete
   aperta e download anonimo.
4. **Il PIR in PDF non serve allo scopo.** È in repository
   (`PIR_2027_dicembre_2025_vDEF.pdf`, 288 pagine) ed è stato esaminato: delega
   ogni dettaglio infrastrutturale al portale ePIR, e per l'estensione della rete
   rimanda alla pagina web di RFI, che riporta solo statistiche aggregate. Le sue
   tabelle sono quasi tutte tariffarie. Non rifare questa verifica.
5. **Il README ha punti invecchiati**: dice 1.711 opere ultimate (ora sono 1.767),
   parla della repository come privata e non cita le pagine Comuni e Metodo.

## Convenzioni

Commenti e messaggi di commit in italiano, senza lettere accentate nel codice
(`perche'`, `piu'`). I commenti spiegano **perché**, non cosa: quasi tutti nascono
da un caso reale incontrato nei PDF, e quel caso va citato. I messaggi di commit
raccontano la causa del problema, non solo la soluzione.
