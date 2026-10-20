"""Appendice 3 alla Relazione Informativa dell'aggiornamento 2025: "Schede
interventi". Una scheda per intervento delle Tabelle A e B (214 su 223), con
due tabelle che danno il CUP opera per opera, cosa che le Tabelle A e B non
fanno (stampano i CUP sotto il codice, senza dire a quale opera vanno):

- "Stato attuativo / Iter procedurale" (progetti): opera, CUP, stato
  attuativo in parole ("Realizzazione", "Iter autorizzativo", "Valutazione di
  fattibilita' alternative progettuali"), e le date di inizio e fine di
  progetto preliminare, definitivo, esecutivo, attivita' negoziali,
  esecuzione, e la data di funzionalita'. Colonne: opera x < 195, CUP
  195-236, stato 236-276, date da 276.
- "Avanzamento programma" (programmi): sottoprogetto, CUP, costo, risorse,
  % finanziata, contabilizzato, % contabilizzata, stato attuativo. Colonne:
  nome x < 289, CUP 289-350, numeri, stato da 505. L'ultima riga e' il totale
  del programma, senza CUP ne' stato: chiude la tabella e serve da controllo.

- "Piano della spesa" (tutte le schede): per opera costo, risorse,
  fabbisogno, obbligazioni giuridicamente vincolanti (lavori e somme a
  disposizione), impegni, pagamenti e la produzione al 2019, 2020...2024 e
  oltre, come la stampa la scheda. Nome x < 225, quattordici numeri. La riga
  senza nome e' il totale dell'intervento.

Il nome dell'opera e lo stato vanno a capo sulle righe sotto. Due date
contigue possono uscire attaccate dal PDF ("10-20248-2018"): si separano con
l'espressione regolare e si contano in ordine, perche' le colonne sono 11.

Uso:
  python3 extract_appendice3.py ../documenti/cdpi-agg2025/appendice_3_schede_intervento.pdf \
          ../data/appendice3-agg2025.json
"""
import json
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import to_float

RE_CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
RE_DATA = re.compile(r"\d{1,2}-\d{4}|-")
RE_NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
RE_PERC = re.compile(r"^\d+%$")
SPESA = ["costo", "risorse", "fabbisogno", "ogv_lavori", "ogv_somme_a_disposizione", "impegni",
         "pagamenti", "produzione_al_2019", "produzione_2020", "produzione_2021", "produzione_2022",
         "produzione_2023", "produzione_2024", "produzione_oltre"]
DATE = ["prog_preliminare_inizio", "prog_preliminare_fine", "prog_definitivo_inizio",
        "prog_definitivo_fine", "prog_esecutivo_inizio", "prog_esecutivo_fine",
        "attivita_negoziali_inizio", "attivita_negoziali_fine", "esecuzione_inizio",
        "esecuzione_fine", "funzionalita"]


def testo(w, a, b):
    return " ".join(t for x, t, _ in w if a <= x < b)


def attacca(tabella):
    """Le righe di solo testo (nome o stato andati a capo) vanno alla riga con
    importi o date piu' vicina in altezza, sulla stessa pagina: il PDF centra
    il testo sulla riga, quindi un nome di tre righe ne ha una sopra e una
    sotto (P134, "Potenziamento tecnologico nodo di Napoli 1^ fase")."""
    righe = [x for x in tabella if x[0] == "riga"]
    for tipo, pag, y, dato in tabella:
        if tipo != "testo":
            continue
        vicine = [r for r in righe if r[1] == pag and abs(r[2] - y) < 10]
        if not vicine:
            continue
        _, _, yr, r = min(vicine, key=lambda r: abs(r[2] - y))
        for campo, parte in dato.items():
            if parte:
                r[campo] = (parte + " " + r[campo] if y > yr else r[campo] + " " + parte).strip()


def main():
    pdf, out = sys.argv[1], sys.argv[2]
    doc = PDF(pdf)
    schede, cur, modo, tab = {}, None, None, []
    for n, pg in enumerate(doc.pages(), 1):
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            y, w = it[0].y, parole(it)
            s = " ".join(t for _, t, _ in w)
            if y > 805 or not w:
                continue
            m = re.match(r"(Progetto|Programma) (\S+?):", s) if 790 < y < 800 else None
            if m:
                if not cur or cur["codice"] != m.group(2):
                    attacca(tab)
                    cur = schede.setdefault(m.group(2), {"codice": m.group(2), "tipo": m.group(1).lower(),
                                                         "pagina": n, "opere": [], "avanzamento": [], "spesa": []})
                    modo, tab = None, []
                continue
            # la prima riga di una pagina di seguito sta a y ~783, subito sotto
            # il titolo della scheda: non va saltata (A1004A, "TS - Miglioramento")
            if cur is None or y > 790:
                continue
            if s.startswith("CUP Prog.Prel."):
                attacca(tab)
                modo, tab = "opere", []
                continue
            if s.startswith("AVANZAMENTO PROGRAMMA"):
                attacca(tab)
                modo, tab = "programma", []
                continue
            if s.startswith("Costo Risorse Fabbis."):
                attacca(tab)
                modo, tab = "spesa", []
                continue
            # una riga di solo testo e' un a capo solo se sta a ridosso della
            # tabella; le intestazioni in maiuscolo la chiudono
            # su una pagina di seguito il primo a capo arriva prima della sua riga
            # ("e linee afferenti" in cima a p. 374, P224)
            vicino = tab and (tab[-1][1] != n or tab[-1][2] - y < 17)
            titolo = w[0][1].isupper() and len(w[0][1]) > 3
            if modo == "opere":
                if s.startswith(("Inizio", "Stato attuativo")):
                    continue
                date = [d for x, t, _ in w if x >= 276 for d in RE_DATA.findall(t)]
                cup = [t for x, t, _ in w if 190 <= x < 232 and RE_CUP.match(t)]
                if len(date) == len(DATE):
                    r = {"opera": testo(w, 0, 190), "cup": cup[0] if cup else "",
                         "stato": testo(w, 232, 276), "pagina": n, "date": dict(zip(DATE, date))}
                    cur["opere"].append(r)
                    tab.append(("riga", n, y, r))
                elif vicino and not titolo and all(x < 276 for x, _, _ in w):
                    tab.append(("testo", n, y, {"opera": testo(w, 0, 190), "stato": testo(w, 232, 276)}))
                else:
                    attacca(tab)
                    modo, tab = None, []
            elif modo == "programma":
                nums = [t for x, t, _ in w if 340 <= x < 505 and (RE_NUM.match(t) or RE_PERC.match(t))]
                cup = [t for x, t, _ in w if 285 <= x < 350 and RE_CUP.match(t)]
                for k in range(1, len(w)):
                    # la prima lettera del CUP attaccata al nome: "l'interportoJ" "91B21004120001" (P224)
                    if not cup and 285 <= w[k][0] < 350 and re.match(r"^\d{2}[A-Z]\d{11}$", w[k][1]) \
                            and w[k - 1][1][-1:].isupper():
                        cup = [w[k - 1][1][-1] + w[k][1]]
                        w = w[:k - 1] + [[w[k - 1][0], w[k - 1][1][:-1], w[k - 1][2]]] + w[k + 1:]
                        break
                stato = testo(w, 505, 900)
                # il piano della spesa, subito sopra, ha numeri anche a sinistra
                # della colonna del costo
                if len(nums) == 5 and not any(RE_NUM.match(t) for x, t, _ in w if x < 340):
                    # senza CUP ne' stato e' un subtotale (segue le sue righe:
                    # "Upgrading tecnologico Napoli Centrale" = ACC + nuovo posto
                    # centrale, P134) o il totale del programma, che e' l'ultimo
                    r = {"nome": testo(w, 0, 285), "cup": cup[0] if cup else "", "stato": stato, "pagina": n,
                         "costo": to_float(nums[0]), "risorse": to_float(nums[1]),
                         "contabilizzato": to_float(nums[3]), "subtotale": not cup and not stato}
                    cur["avanzamento"].append(r)
                    tab.append(("riga", n, y, r))
                elif vicino and not titolo and not nums:
                    tab.append(("testo", n, y, {"nome": testo(w, 0, 285), "stato": stato}))
                else:
                    attacca(tab)
                    modo, tab = None, []
            elif modo == "spesa":
                nums = [t for x, t, _ in w if x >= 225 and RE_NUM.match(t)]
                if len(nums) == len(SPESA):
                    r = {"nome": testo(w, 0, 225), "pagina": n, **dict(zip(SPESA, map(to_float, nums)))}
                    if r["nome"]:
                        cur["spesa"].append(r)
                        tab.append(("riga", n, y, r))
                    else:
                        cur["spesa_totale"] = r
                elif vicino and not titolo and not nums and all(x < 225 for x, _, _ in w):
                    tab.append(("testo", n, y, {"nome": testo(w, 0, 225)}))
                else:
                    attacca(tab)
                    modo, tab = None, []
    attacca(tab)
    # il controllo sulle somme lo fa assegnazioni_cup.py, che ha il costo
    # dell'intervento: l'ultima riga senza CUP ne' stato non e' sempre il totale
    # del programma (P221 ha piu' gruppi, ognuno col suo subtotale)
    json.dump({"doc": "agg2025", "fonte": pdf.split("/")[-1], "schede": schede}, open(out, "w"),
              ensure_ascii=False, indent=1)
    n_op = sum(len(s["opere"]) for s in schede.values())
    n_av = sum(len(s["avanzamento"]) for s in schede.values())
    cups = {r["cup"] for s in schede.values() for r in s["opere"] + s["avanzamento"] if r["cup"]}
    # il piano della spesa: le opere sommano al totale dell'intervento
    diversi = [c for c, s in schede.items() if s["spesa"] and "spesa_totale" in s and any(
        abs(sum(r[k] for r in s["spesa"]) - s["spesa_totale"][k]) > 0.05 * len(s["spesa"]) for k in SPESA)]
    print("%s: %d schede, %d opere, %d righe di avanzamento programma, %d CUP distinti; piano della spesa "
          "in %d schede (%d righe), senza totale %d, opere che non sommano al totale: %s" % (
              out, len(schede), n_op, n_av, len(cups), sum(1 for s in schede.values() if s["spesa"]),
              sum(len(s["spesa"]) for s in schede.values()),
              sum(1 for s in schede.values() if s["spesa"] and "spesa_totale" not in s), diversi or "nessuna"))


if __name__ == "__main__":
    main()
