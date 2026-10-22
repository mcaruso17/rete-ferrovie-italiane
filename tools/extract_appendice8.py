"""Appendice 8 alla Relazione Informativa dell'aggiornamento 2025: "Quadro
riepilogativo aggiornato delle opere incluse nel Programma delle
Infrastrutture Strategiche" (PIS, legge obiettivo). Una riga per CUP:
descrizione, se e' nel PNRR, se e' commissariato, lo stato di attuazione in
quattro colonne (conclusi, in corso di realizzazione, in progettazione,
progetti gia' sottoposti o da sottoporre al CIPESS) e note. Nelle colonne di
stato c'e' una "x" oppure un testo ("in esercizio opera principale il
02/12/2016, in via di completamento le opere accessorie"): si tengono
entrambi. Il testo va a capo sopra e sotto la riga del CUP e si attacca al
CUP piu' vicino in altezza.

Uso:
  python3 extract_appendice8.py ../documenti/cdpi-agg2025/appendice_8_quadro_riepilogativo_delle_opere_incluse_nel_pis.pdf \
          ../data/appendice8-agg2025.json
"""
import json
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines

RE_CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
CAMPI = [("descrizione", 70, 204), ("pnrr", 204, 238), ("commissariato", 238, 265),
         ("conclusi", 265, 385), ("in_corso_di_realizzazione", 385, 460), ("in_progettazione", 460, 570),
         ("cipess", 570, 650), ("note", 650, 9999)]
STATI = ["conclusi", "in_corso_di_realizzazione", "in_progettazione", "cipess"]


def main():
    pdf, out = sys.argv[1], sys.argv[2]
    doc = PDF(pdf)
    opere = []
    for n, pg in enumerate(doc.pages(), 1):
        linee = []
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            linee.append((it[0].y, parole(it)))
        ancore = [y for y, w in linee if w and w[0][0] < 70 and RE_CUP.match(w[0][1])]
        if not ancore:
            continue
        # l'intestazione finisce con "fattibilita')" e "CIPESS", poco sopra il primo CUP
        alto = min([y for y, w in linee if any(t in ("fattibilità)", "(esecutiva,") for _, t, _ in w)] or [999]) - 1
        dati = {y: {k: [] for k, _, _ in CAMPI} for y in ancore}
        for k, a, b in CAMPI:
            # il testo di una cella va a capo sopra e sotto la riga, centrato: si
            # raccolgono le righe consecutive della colonna (passo ~6) in blocchi e
            # il blocco va al CUP piu' vicino al suo centro. Per riga, il testo di
            # Arcisate (y 458-429) finiva sotto Treviglio-Brescia
            pezzi = [(y, " ".join(t for x, t, _ in w if a <= x < b)) for y, w in linee if y < alto]
            pezzi = [p for p in pezzi if p[1]]
            blocchi = []
            for y, s in pezzi:
                if blocchi and blocchi[-1][-1][0] - y < 7.5:
                    blocchi[-1].append((y, s))
                else:
                    blocchi.append([(y, s)])
            for bl in blocchi:
                if any(y in dati for y, _ in bl):
                    # il blocco tocca la riga di un CUP: celle contigue di righe
                    # diverse (Spoleto-Terni e PM228, passo 3), si assegna riga
                    # per riga al CUP piu' vicino
                    for y, s in bl:
                        dati[min(ancore, key=lambda a: abs(a - y))][k].append(s)
                    continue
                c = (bl[0][0] + bl[-1][0]) / 2
                ya = min(ancore, key=lambda y: abs(y - c))
                if abs(ya - c) < 20:
                    dati[ya][k] += [s for _, s in bl]
        for ya in sorted(ancore, reverse=True):
            o = {k: " ".join(v).strip() for k, v in dati[ya].items()}
            o["cup"] = next(t for y, w in linee if y == ya for x, t, _ in w if x < 70 and RE_CUP.match(t))
            o["stato_attuazione"] = "|".join(s for s in STATI if o[s])
            o["pagina"] = n
            opere.append(o)
    json.dump({"doc": "agg2025", "fonte": pdf.split("/")[-1], "opere": opere}, open(out, "w"),
              ensure_ascii=False, indent=1)
    print("%s: %d opere, %d CUP distinti; senza stato di attuazione: %d" % (
        out, len(opere), len({o["cup"] for o in opere}), sum(1 for o in opere if not o["stato_attuazione"])))


if __name__ == "__main__":
    main()
