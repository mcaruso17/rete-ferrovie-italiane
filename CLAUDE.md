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

## Cosa resta aperto

1. **Il tracciato vero delle linee.** Serve la geometria da OpenStreetMap
   (relazioni `route=railway`, oppure `railway=rail` con `usage=main|branch`).
   Con quella, i comuni realmente attraversati diventano calcolabili per
   intersezione con i confini ISTAT che abbiamo già in locale, e le spezzate
   schematiche vanno sostituite. 190 interventi su 336 hanno un nome a forma di
   tratta, quindi agganciabile per nome con verifica manuale.
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
