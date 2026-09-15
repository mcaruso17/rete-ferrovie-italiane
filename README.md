# Contratti di Programma MIT – RFI, parte Investimenti

Estrazione e lettura strutturata dei sei Contratti di Programma fra il Ministero
delle Infrastrutture e dei Trasporti e Rete Ferroviaria Italiana (2017–2021 e
2022–2026, con i relativi aggiornamenti), contenuti in questa repository come PDF.

**Piattaforma interattiva:** https://claude.ai/artifact/Jx3AUvQopmum34mX1uxxqk

## Cosa contengono i dati

| File | Contenuto |
|---|---|
| `data/progetti.csv` | 336 interventi: costo, risorse assegnate, fabbisogno residuo, stato attuativo, programma, pagina del PDF |
| `data/serie-storica.csv` | Lo stesso intervento visto in ciascuno dei contratti in cui compare |
| `data/opere-ultimate.csv` | 822 opere dichiarate ultimate, con CUP e data di messa in esercizio (Tabella C) |
| `data/capitoli-piani-gestionali.csv` | Tavola 2: fonti e impieghi di cassa per anno, per capitolo di bilancio e piano gestionale |
| `data/cdp-rfi-dataset.json` | Dataset completo, comprese le tavole di sintesi ufficiali |
| `data/cdp-rfi-app.json` | Versione compatta usata dalla piattaforma |

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

### Limiti noti

L'aggiornamento 2023 ha una struttura di tabella diversa dagli altri cinque e non
è incluso nel confronto per intervento; le sue opere ultimate restano nel dataset.
Nei font di alcuni documenti la legatura «ti» non è mappata nel CMap `ToUnicode`
e il font incorporato non espone né `cmap` né nomi dei glifi: è stata ricostruita
dal contesto (1241 occorrenze nel corpus) e la scelta è documentata nel codice.

## Rigenerare i dati

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
python3 build_app.py ../data/cdp-rfi-dataset.json ../data/cdp-rfi-app.json
```
