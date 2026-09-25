"""Estrae dai Contratti di Programma parte Servizi il registro delle linee.

L'Allegato 3, "Gruppi Linee: articolazione di dettaglio della Rete ferroviaria
per singola linea", e' l'elenco ufficiale delle linee secondo RFI: codice,
denominazione, treni al giorno programmati, estensione in chilometri, e il
gruppo di traffico in cui la linea ricade.

Perche' conta piu' di quanto sembri. Fino a qui la dimensione "linea" del sito
veniva da OpenStreetMap, cioe' da una fonte esterna con nomi dati dai
contributori. Questo allegato e' la stessa dimensione detta da RFI, con un
codice stabile: e' il riferimento a cui gli agganci andrebbero ancorati, e
permette di dire quanti chilometri e quanto traffico ha una linea senza dedurre
niente.

Uso:
  python3 extract_servizi.py ../CdP_Servizi_2022-2026.pdf cdps2022 out.json

Il documento base porta l'allegato completo; gli atti integrativi lo
ripubblicano solo quando lo modificano, quindi su alcuni il risultato e' vuoto
e non e' un errore.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF                        # noqa: E402
from pdftext import extract_page, group_lines   # noqa: E402
from tables import raw_cells, to_float          # noqa: E402

# Il suffisso AV non e' decorativo: distingue la sezione ad alta velocita'
# affiancata alla linea storica (F023 Pioltello-Brescia e F023AV, la stessa
# tratta in AV) e sono quattro righe per 92,3 km. Senza, il totale non torna
# ed e' esattamente lo scarto che si vedeva.
CODICE = re.compile(r"^[A-Z]{1,2}\d{3,4}(?:AV)?$")
NUMERO = re.compile(r"^-?[\d.]*\d(?:,\d+)?$")
TOTALE = re.compile(r"^TOTALE\b", re.I)


def righe_allegato3(doc, pg):
    """Le righe dell'Allegato 3 in una pagina, e i totali che vi sono stampati.

    Le colonne NON si riconoscono dalla posizione sulla pagina. Il primo
    tentativo lo faceva, con fasce di ascisse ricavate dal contratto base, e si
    rompeva in due modi: nell'atto integrativo 2023 le colonne sono spostate di
    una ventina di punti e la denominazione finiva dentro la fascia del codice,
    facendo scartare 33 righe su 34; e nel contratto base le righe con nomi
    lunghi perdevano la denominazione. Il risultato sembrava sano, 292 linee e
    16.739,9 km, e mancavano 91,9 km sul totale stampato.

    Qui la riga si ancora al codice, che e' l'unica cella riconoscibile da sola:
    quello che sta prima e' il gruppo, quello che sta dopo e' la denominazione
    piu' i due numeri in coda. Funziona a prescindere da dove cadano le colonne.
    """
    righe, totali = [], []
    for ln in group_lines(extract_page(doc, pg)):
        testi = [t for _x0, _x1, t, _i in raw_cells(ln) if t]
        if not testi:
            continue

        # i totali stampati servono a validare: si raccolgono qui perche' sono
        # righe della stessa tabella, non un di piu'
        if TOTALE.match(testi[0]) and NUMERO.match(testi[-1]):
            totali.append({"voce": " ".join(testi[:-1]).strip(),
                           "km": to_float(testi[-1])})
            continue

        pos = next((k for k, t in enumerate(testi) if CODICE.match(t)), None)
        if pos is None:
            continue
        coda = testi[pos + 1:]
        if not coda or not NUMERO.match(coda[-1]):
            continue
        km = to_float(coda[-1])
        tr = coda[-2] if len(coda) >= 2 else ""
        # il trattino al posto del numero e' "nessun treno programmato", non un
        # dato mancante: nel documento la colonna non resta mai vuota
        if tr in ("-", "–"):
            treni, nome = 0, coda[:-2]
        elif tr and NUMERO.match(tr):
            treni, nome = to_float(tr), coda[:-2]
        else:
            treni, nome = None, coda[:-1]
        righe.append({
            "gruppo": " ".join(testi[:pos]).strip(),
            "codice": testi[pos],
            "linea": " ".join(nome).strip(),
            "treni_giorno": treni,
            "km": km,
        })
    return righe, totali


def main():
    pdf, doc_id, out = sys.argv[1], sys.argv[2], sys.argv[3]
    doc = PDF(pdf)
    pagine = doc.pages()
    linee, pagine_viste, totali = [], [], []
    for i, pg in enumerate(pagine):
        try:
            testa = " ".join("".join(t.text for t in ln)
                             for ln in group_lines(extract_page(doc, pg))[:3])
        except Exception:
            continue
        # il titolo cambia fra le edizioni: "Gruppi Linee: articolazione di
        # dettaglio..." fino al 2024, "Elenco linee, comprese quelle di
        # continuita' territoriale" nel 2026. Col solo primo titolo l'atto
        # 2026 risultava senza allegato, ed era falso
        if "Allegato 3" not in testa or not ("Gruppi Linee" in testa
                                             or "Elenco linee" in testa):
            continue
        r, tot = righe_allegato3(doc, pg)
        if r:
            for x in r:
                x["pagina"] = i + 1
            linee.extend(r)
            pagine_viste.append(i + 1)
        totali.extend(tot)

    # lo stesso codice non deve comparire due volte: se succede la lettura sta
    # raccogliendo due volte la stessa pagina, o l'allegato e' ripetuto
    visti, doppi = set(), []
    for l in linee:
        if l["codice"] in visti:
            doppi.append(l["codice"])
        visti.add(l["codice"])

    dati = {"documento": doc_id, "pagine": pagine_viste, "linee": linee,
            "totali_stampati": totali}
    json.dump(dati, open(out, "w"), ensure_ascii=False, indent=1)

    km = sum(l["km"] or 0 for l in linee)
    senza_nome = sum(1 for l in linee if not l["linea"])
    print("%-38s %3d linee su %d pagine, %9.1f km ricostruiti"
          % (os.path.basename(pdf), len(linee), len(pagine_viste), km))
    if doppi:
        print("   ATTENZIONE: %d codici ripetuti, es. %s"
              % (len(doppi), doppi[:5]))
    if senza_nome:
        print("   ATTENZIONE: %d righe senza denominazione" % senza_nome)
    # Il confronto con i totali stampati e' il controllo che conta: senza,
    # una lettura parziale passa inosservata perche' il risultato sembra sano.
    # Si confronta gruppo per gruppo e non solo il totale: cosi' uno scarto si
    # localizza subito invece di restare un numero senza indirizzo. Fu proprio
    # questo a scoprire che mancavano i codici col suffisso AV.
    per_gruppo = {}
    for l in linee:
        per_gruppo[l["gruppo"]] = per_gruppo.get(l["gruppo"], 0.0) + (l["km"] or 0)
    sub = [t for t in totali if "complessivo" not in t["voce"].lower()]
    comp = [t for t in totali if "complessivo" in t["voce"].lower()]

    # La tolleranza non e' una scorciatoia: i chilometri sono stampati con un
    # decimale, quindi la somma di 296 valori arrotondati non puo' coincidere
    # al centesimo. Che lo scarto sia arrotondamento e non lettura sbagliata lo
    # dimostra il documento stesso, dove la somma dei sottototali stampati non
    # fa il totale stampato: l'incoerenza e' nella fonte. Nell'atto 2024, dove
    # la fonte e' coerente, la ricostruzione torna esatta su ogni gruppo.
    #
    # Nell'atto 2026 i chilometri passano da tre decimali a uno, e l'errore di
    # arrotondamento cresce con il numero di righe: la deviazione standard di
    # un arrotondamento al decimo e' 0,1/sqrt(12), circa 0,029 km, e sulla
    # somma di n righe vale 0,029*sqrt(n). La soglia e' tre deviazioni, mai
    # sotto 0,5: sul gruppo piu' numeroso (circa 150 linee) fa poco piu' di un
    # chilometro, ancora sotto la linea piu' corta del registro, quindi una
    # riga persa si vedrebbe comunque.
    def toll(n):
        return max(0.5, 3 * 0.0289 * n ** 0.5)
    n_gruppo = {}
    for l in linee:
        n_gruppo[l["gruppo"]] = n_gruppo.get(l["gruppo"], 0) + 1
    esiti = []
    for g, v in sorted(per_gruppo.items()):
        cand = [t for t in sub if g[:24].lower() in t["voce"].lower()]
        if not cand:
            continue
        d = v - cand[0]["km"]
        TOLL = toll(n_gruppo[g])
        esiti.append(abs(d) <= TOLL)
        print("   %-46s %9.1f  stampato %9.1f  %+.1f %s"
              % (g[:46], v, cand[0]["km"], d, "" if abs(d) <= TOLL else " NON TORNA"))
    TOLL = toll(len(linee))
    if comp:
        atteso = comp[0]["km"]
        d = km - atteso
        sub_somma = sum(t["km"] for t in sub)
        esiti.append(abs(d) <= TOLL)
        print("   %-46s %9.1f  stampato %9.1f  %+.1f %s"
              % ("TOTALE complessivo", km, atteso, d,
                 "" if abs(d) <= TOLL else " NON TORNA"))
        if abs(sub_somma - atteso) > 0.05:
            print("   (la fonte e' incoerente con se stessa: i suoi sottototali"
                  " sommano %.1f contro %.1f)" % (sub_somma, atteso))
    if esiti:
        print("   ESITO: %d confronti, %d entro la tolleranza di arrotondamento"
              % (len(esiti), sum(esiti)))
    elif linee:
        print("   nessun totale stampato in questo documento")


if __name__ == "__main__":
    main()
