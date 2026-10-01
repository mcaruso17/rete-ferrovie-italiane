"""Distribuzione territoriale degli investimenti in corso: Appendice 7 alla
Relazione Informativa dell'aggiornamento Investimenti.

Tre parti:
- p. 2, il riepilogo per regione: valore normalizzato (le opere
  pluriregionali ripartite "sulla base del perimetro di attivita' ricadenti
  nella regione", i programmi diffusi "su base parametrica" coi km di linea),
  risorse, nuove risorse, definanziamenti, rimodulazioni, incidenza delle nuove
  risorse;
- "Principali investimenti Regione X": gli interventi che il contratto
  colloca in ogni regione. Gli importi di riga sono quelli dell'intervento
  intero, non la quota regionale: servono solo a riconoscere le righe;
- "Programmi pluriennali": i programmi diffusi sull'intera rete.

E' la distribuzione territoriale ufficiale: la piattaforma finora la
stimava dai luoghi citati nel nome dell'intervento (geo.py).

Uso:
  python3 extract_appendice7.py appendice_7.pdf agg2025 ../data/mappa-regioni.json ../data/appendice7-agg2025.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF                        # noqa: E402
from pdftext import extract_page, group_lines  # noqa: E402
from tables import raw_cells                   # noqa: E402

NUM = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
RIEPILOGO = re.compile(r"^(.+?)\s+(%s)\s+(%s)\s+(%s)\s+(%s)\s+(%s)\s+(\d+)%%$" % ((NUM,) * 5))
CODICE = re.compile(r"^([A-Z]{0,2}\d{3,4}(?:_?[A-Z0-9])?)\s+(.*)$")
PROGRAMMA = re.compile(r"^A\d{2}\s+-\s")
# i nomi del documento contro quelli ISTAT della mappa
ALIAS = {"emilia romagna": "emilia-romagna", "friuli venezia giulia": "friuli-venezia giulia",
         "trentino alto adige": "trentino-alto adige", "val d'aosta": "valle d'aosta"}


def num(t):
    return float(t.replace(".", "").replace(",", "."))


def norm(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def linee(doc, pg):
    return [" ".join(t for _a, _b, t, _i in raw_cells(ln)).strip()
            for ln in group_lines(extract_page(doc, pg))]


def main():
    pdf, doc_id, mappa, dest = sys.argv[1:5]
    istat = {}
    for r in json.load(open(mappa, encoding="utf-8"))["regioni"]:
        istat[norm(r["n"])] = r["istat"]
    def cod_regione(nome):
        n = norm(nome)
        n = ALIAS.get(n, n)
        if n in istat:
            return istat[n]
        cand = [k for k in istat if k.startswith(n[:8])]
        return istat[cand[0]] if len(cand) == 1 else None

    doc = PDF(pdf)
    pagine = doc.pages()
    riepilogo = []
    for l in linee(doc, pagine[1]):
        l = re.sub(r"^(Nord|Centro|Sud)\s+", "", l)
        m = RIEPILOGO.match(l)
        if not m or m.group(1).startswith(("Subtotale", "Totale")):
            continue
        nome = m.group(1)
        riepilogo.append({"regione": nome, "istat": cod_regione(nome),
                          "valore_normalizzato": num(m.group(2)), "risorse": num(m.group(3)),
                          "nuove_risorse": num(m.group(4)), "definanziamenti": num(m.group(5)),
                          "rimodulazioni": num(m.group(6)), "incidenza_nuove_pct": int(m.group(7))})

    per_regione, diffusi, pagine_reg = {}, [], {}
    for n, pg in enumerate(pagine[2:], 3):
        L = linee(doc, pg)
        testa = " ".join(L[:3])
        m = re.search(r"Principali investimenti Regione (.+?)$", L[1] if len(L) > 1 else "")
        m = m or re.search(r"Principali investimenti Regione (.+)", testa)
        if m:
            chiave = cod_regione(m.group(1).strip())
            dest_l = per_regione.setdefault(chiave, [])
            pagine_reg.setdefault(chiave, []).append(n)
        elif "Programmi pluriennali" in testa:
            dest_l = diffusi
        else:
            continue
        for l in L:
            if PROGRAMMA.match(l):
                continue
            c = CODICE.match(l)
            # una riga d'intervento porta gli importi: almeno tre numeri
            if c and len(re.findall(NUM, l)) >= 3:
                if c.group(1) not in [x["c"] for x in dest_l]:
                    dest_l.append({"c": c.group(1), "p": n})

    out = {"documento": os.path.basename(pdf), "doc": doc_id,
           "note": {"pluriregionali": "ripartiti sulla base del perimetro di attivita' ricadenti nella regione",
                    "diffusi": "normalizzati sulle regioni su base parametrica, coi km di linea"},
           "riepilogo": riepilogo, "per_regione": per_regione, "pagine": pagine_reg,
           "diffusi": diffusi}
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    tot = sum(r["valore_normalizzato"] for r in riepilogo)
    tutti = {x["c"] for v in per_regione.values() for x in v}
    pluri = sum(1 for c in tutti if sum(1 for v in per_regione.values() if any(x["c"] == c for x in v)) > 1)
    print("appendice 7 %s: %d regioni nel riepilogo (valore normalizzato %.2f mln), %d regioni con "
          "interventi, %d interventi (%d in piu' regioni), %d programmi diffusi; regioni non riconosciute: %s"
          % (doc_id, len(riepilogo), tot, len(per_regione), len(tutti), pluri, len(diffusi),
             [r["regione"] for r in riepilogo if not r["istat"]] + [k for k in per_regione if not k]))


if __name__ == "__main__":
    main()
