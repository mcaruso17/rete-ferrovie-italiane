"""Appendice 9 alla Relazione Informativa dell'aggiornamento 2025: "Elenco
opere inserite nel PNRR e PNC". Tre tabelle, ognuna con un'impaginazione sua:

- PNRR Missione 3 Componente 1 (pp. 2-3): misura, intervento, riferimento CdP
  (codice intervento, o "CdP-Servizi"), CUP, codice locale di progetto (CLP),
  risorse PNRR (totale, progetti in essere, nuovi progetti nel CdP-I, nuovi
  progetti nel CdP-S), altri finanziamenti (nazionali, UE) e totale risorse.
  Le colonne numeriche si riconoscono per ascissa: le righe di dettaglio non
  stampano la colonna CdP-S, che c'e' solo nei subtotali.
- PNRR altre missioni (p. 4): M5C3, M5C2, M2C4, con totale, progetti in essere
  e nuovi progetti. La sigla della missione sta nell'intestazione del blocco.
- PNC, Piano complementare (p. 5): missione, intervento, CUP e un importo.
  Qui la sigla della missione e' centrata in altezza sul suo blocco, che si
  chiude con un "subTotale".

Uno stesso CUP puo' comparire su piu' righe (J41H01000080008: Frasso-Telese e
Telese-Vitulano, 0279B). Controlli: le righe di dettaglio sommano ai totali
stampati (Totale M3C1, Totale altre missioni, Totale Piano Complementare).

Uso:
  python3 extract_appendice9.py ../documenti/cdpi-agg2025/appendice_9_elenco_opere_pnrr_e_pnc.pdf \
          ../data/appendice9-agg2025.json
"""
import json
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import to_float

RE_CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
RE_NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
# ascissa di inizio delle colonne numeriche della tabella M3C1
COL_M3C1 = [(712, "pnrr_totale"), (775, "pnrr_progetti_in_essere"), (838, "pnrr_nuovi_progetti_cdpi"),
            (903, "pnrr_nuovi_progetti_cdps"), (970, "altri_finanziamenti_nazionali"),
            (1035, "altri_finanziamenti_ue"), (1094, "totale_risorse_disponibili")]
COL_ALTRE = [(404, "pnrr_totale"), (476, "pnrr_progetti_in_essere"), (547, "pnrr_nuovi_progetti")]


def testo(w, a, b):
    return " ".join(t for x, t, _ in w if a <= x < b)


def colonne(w, col):
    v = {}
    for x, t, _ in w:
        if RE_NUM.match(t):
            dx, nome = min((abs(c - x), n) for c, n in col)
            if dx < 25:
                v[nome] = to_float(t)
    return v


def attacca(righe, testi, campo):
    """Le righe di solo testo (nome dell'intervento a capo) vanno alla riga
    con CUP piu' vicina in altezza, prima o dopo secondo dove stanno."""
    for pag, y, t in testi:
        vic = [r for r in righe if r["pagina"] == pag and abs(r["_y"] - y) < 14]
        if vic:
            r = min(vic, key=lambda r: abs(r["_y"] - y))
            r[campo] = (t + " " + r[campo] if y > r["_y"] else r[campo] + " " + t).strip()


def main():
    pdf, out = sys.argv[1], sys.argv[2]
    doc = PDF(pdf)
    righe, totali, problemi = [], {}, []
    for n, pg in enumerate(doc.pages(), 1):
        linee = []
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            linee.append((it[0].y, parole(it)))
        tutto = " ".join(t for _, w in linee for _, t, _ in w)
        if "Componente 1 - INVESTIMENTI SULLA RETE FERROVIARIA" in tutto or n == 3:
            for y, w in linee:
                cup = [t for x, t, _ in w if 505 <= x < 570 and RE_CUP.match(t)]
                if cup:
                    righe.append({"sezione": "PNRR M3C1", "misura": testo(w, 0, 105),
                                  "intervento": testo(w, 105, 455), "rif_cdp": testo(w, 455, 505),
                                  "cup": cup[0], "clp": testo(w, 570, 705), "pagina": n, "_y": y,
                                  **colonne(w, COL_M3C1)})
                elif w and w[0][1] == "Totale" and testo(w, 0, 200).endswith("M3C1"):
                    totali["PNRR M3C1"] = colonne(w, COL_M3C1)
        elif "Altre missioni" in tutto:
            missione, testi = "", []
            for y, w in linee:
                sig = [t for x, t, _ in w if 470 <= x < 490 and re.match(r"^M\dC\d$", t)]
                if sig:
                    missione = sig[0]
                    continue
                cup = [t for x, t, _ in w if 295 <= x < 340 and RE_CUP.match(t)]
                if cup:
                    righe.append({"sezione": "PNRR altre missioni", "misura": missione,
                                  "intervento": testo(w, 0, 262), "rif_cdp": testo(w, 262, 300),
                                  "cup": cup[0], "clp": "", "pagina": n, "_y": y, **colonne(w, COL_ALTRE)})
                elif testo(w, 0, 300).startswith("Totale altre missioni"):
                    totali["PNRR altre missioni"] = colonne(w, COL_ALTRE)
                elif w and 15 < w[0][0] < 30 and not any(RE_NUM.match(t) for _, t, _ in w) \
                        and not w[0][1].isupper() and w[0][1] not in ("Componente", "Missione", "Altre"):
                    # nome a capo sopra o sotto la riga: "Alluvioni - interventi ..."
                    # e "a partire dal giorno 1 maggio 2023" (M2C4)
                    testi.append((n, y, testo(w, 0, 262)))
            attacca([r for r in righe if r["sezione"] == "PNRR altre missioni"], testi, "intervento")
        elif "PIANO COMPLEMENTARE" in tutto:
            blocco, sigle = [], []
            for y, w in linee:
                sig = [(y, t) for x, t, _ in w if x < 60 and re.match(r"^M\dC\d$", t)]
                sigle += sig
                cup = [t for x, t, _ in w if 570 <= x < 640 and RE_CUP.match(t)]
                if cup:
                    r = {"sezione": "PNC", "misura": "", "intervento": testo(w, 95, 510),
                         "rif_cdp": testo(w, 510, 570), "cup": cup[0], "clp": "", "pagina": n, "_y": y,
                         "pnc_totale": to_float(next(t for x, t, _ in w if x > 640 and RE_NUM.match(t)))}
                    righe.append(r)
                    blocco.append(r)
                elif testo(w, 95, 300).startswith("subTotale"):
                    # la sigla della missione sta in mezzo al blocco che si chiude qui
                    s = [t for ys, t in sigle if min(b["_y"] for b in blocco) - 8 <= ys <= max(b["_y"] for b in blocco) + 8]
                    for b in blocco:
                        b["misura"] = s[0] if s else ""
                    blocco, sigle = [], []
                elif testo(w, 0, 400).startswith("Totale Piano Complementare"):
                    totali["PNC"] = {"pnc_totale": to_float(next(t for x, t, _ in w if RE_NUM.match(t)))}
    # controlli contro i totali stampati
    for sez, tot in totali.items():
        for k, v in tot.items():
            s = round(sum(r.get(k) or 0 for r in righe if r["sezione"] == sez), 2)
            if abs(s - v) > 0.05:
                problemi.append("%s, %s: righe %.2f, totale stampato %.2f" % (sez, k, s, v))
    for sez in ("PNRR M3C1", "PNRR altre missioni", "PNC"):
        if sez not in totali:
            problemi.append("%s: totale non trovato" % sez)
    for r in righe:
        r.pop("_y")
    json.dump({"doc": "agg2025", "fonte": pdf.split("/")[-1], "righe": righe, "totali": totali},
              open(out, "w"), ensure_ascii=False, indent=1)
    print("%s: %d righe (%s), %d CUP distinti; totali %s" % (
        out, len(righe), ", ".join("%s %d" % (s, sum(1 for r in righe if r["sezione"] == s)) for s in totali),
        len({r["cup"] for r in righe}), "ok" if not problemi else "DIVERSI"))
    for p in problemi:
        print("  attenzione:", p)
    if problemi:
        sys.exit(1)


if __name__ == "__main__":
    main()
