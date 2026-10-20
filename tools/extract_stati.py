"""Stato attuativo e fase finanziata delle opere, Tabelle A e B dell'ultimo
aggiornamento Investimenti.

Sotto ogni intervento la tabella elenca le sue opere (lotti, fasi, tratte),
ciascuna con il proprio costo a vita intera, i propri importi e due sigle:
- fase finanziata (colonna a x ~ 290): fino a quale fase arrivano i soldi;
- stato attuativo (colonna a x ~ 316): dove si trova oggi l'opera.
Le sigle del 2025 (legenda in fondo a ogni pagina): FAP valutazione di
fattibilita' delle alternative progettuali, PROG progettazione, ITER iter
autorizzativo, AN attivita' negoziali, RE realizzazione, ES esercizio; la
fase finanziata puo' avere (P) parziale o (PR) intervento in project review.
L'ordine delle due colonne e' il contrario di quello che verrebbe da
supporre: "Nuova linea a monte del Vesuvio RE ES" e' finanziata fino alla
realizzazione ed e' gia' in esercizio. Si leggono per posizione, non per
ordine, dopo averle trovate sotto le intestazioni a p. 82.

extract.py non le legge (non conosce PROG e ITER e somma le sigle delle due
colonne): qui si rileggono le pagine con le coordinate. Gli importi delle
opere si assegnano alle colonne per bordo destro, con le colonne prese dalle
righe intervento complete; l'avanzamento di un'opera e' spesso stampato da
solo sulla riga sotto, e va a quell'opera.

Controllo: dove un intervento ha opere, la somma dei loro costi si confronta
col costo dell'intervento (non sempre coincide: alcune righe elencano solo le
opere avviate).

Uso:
  python3 extract_stati.py "../CdP_2022-2026_Investimenti_Agg_ 2025.pdf" raw/agg2025.json \
          ../data/stati-opere-agg2025.json
"""
import json
import re
import statistics
import sys

from pdfmini import PDF
from pdftext import extract_page, group_lines
from schema import TABELLA_A
from tables import to_float

SIGLE = ("FAP", "PROG", "ITER", "AN", "RE", "ES")
RE_SIGLA = re.compile(r"^(FAP|PROG|ITER|AN|RE|ES)(\((P|PR)\))?$")
RE_NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
# fasce delle colonne a sinistra degli importi (pagine 842x595, Tabelle A e B 2025)
X_NUOVO = (238, 282)
X_FASE = (284, 312)
X_STATO = (312, 338)
X_PANIERE = (338, 356)
X_TESTO = 284          # la descrizione sta a sinistra della prima sigla


def parole(it):
    """Caratteri -> parole con ascissa iniziale e finale."""
    out, cur = [], None
    for i in sorted(it, key=lambda i: i.x):
        if not i.text.strip():
            if cur:
                out.append(cur)
                cur = None
            continue
        if cur and i.x - cur[2] < 1.8:
            cur = [cur[0], cur[1] + i.text, i.x + i.w]
        else:
            if cur:
                out.append(cur)
            cur = [i.x, i.text, i.x + i.w]
    if cur:
        out.append(cur)
    return out


def dentro(x, fascia):
    return fascia[0] <= x < fascia[1]


def main():
    pdf, raw, out = sys.argv[1], sys.argv[2], sys.argv[3]
    R = json.load(open(raw))
    doc_id = R.get("doc") or "agg2025"
    righe_int = [r for r in R["rows"] if r["kind"] in ("A", "B") and r.get("vista") != "classi"]
    codici = {r["code"]: r for r in righe_int}
    pagine = range(min(r["page"] for r in righe_int), max(r["page"] for r in righe_int) + 1)
    nomi = [TABELLA_A[doc_id]["map"][i] for i in sorted(TABELLA_A[doc_id]["map"])]
    ncol = len(nomi)

    doc = PDF(pdf)
    P = doc.pages()
    linee = []   # (pagina, y, parole)
    for p in pagine:
        for l in group_lines(extract_page(doc, P[p - 1])):
            it = l[1] if isinstance(l, tuple) else l
            linee.append((p, it[0].y, parole(it)))

    def codice_in_testa(w):
        # il codice puo' essere attaccato alla descrizione ("0279AItinerario"):
        # si prende il codice piu' lungo che fa da prefisso alla prima parola
        if not w or w[0][0] >= 50:
            return None
        cand = [c for c in codici if w[0][1].startswith(c)]
        return max(cand, key=len) if cand else None

    # colonne degli importi: bordo destro mediano dei numeri delle righe intervento complete
    bordi = [[] for _ in range(ncol)]
    for p, y, w in linee:
        if w and w[0][0] < 50 and any(w[0][1].startswith(c) for c in codici):
            nums = [x for x in w if RE_NUM.match(x[1])]
            if len(nums) == ncol:
                for k, x in enumerate(nums):
                    bordi[k].append(x[2])
    colonne = [statistics.median(b) for b in bordi]

    def importi(w):
        v = {}
        for x in w:
            if RE_NUM.match(x[1]) and x[0] > X_PANIERE[0]:
                k = min(range(ncol), key=lambda k: abs(colonne[k] - x[2]))
                if abs(colonne[k] - x[2]) < 6:
                    v[nomi[k]] = to_float(x[1])
        return v

    interventi, cur, ultima = {}, None, None
    for p, y, w in linee:
        if not w:
            continue
        testo = " ".join(t for x0, t, _ in w if x0 < X_TESTO)
        # legenda, note e intestazioni: le opere di un intervento possono
        # continuare nella pagina dopo, quindi non chiudono l'intervento
        if testo.startswith(("Legenda", "Stato attuativo", "Nota", "Contratto di Programma", "TABELLA",
                             "Articolazione", "copertura", "procedure")) or y > 400 and not cur:
            continue
        cod = codice_in_testa(w)
        if cod:
            cur = {"codice": cod, "pagina": p, "opere": [], "importi": importi(w)}
            interventi[cod] = cur
            ultima = None
            # sigle sulla riga dell'intervento stesso: e' anche la sua unica opera
            if not any(RE_SIGLA.match(x[1]) and (dentro(x[0], X_FASE) or dentro(x[0], X_STATO)) for x in w):
                continue
            testo = " ".join(t for x0, t, _ in w if x0 < X_TESTO)[len(cod):].strip()
        sigle_f = [x[1] for x in w if dentro(x[0], X_FASE) and RE_SIGLA.match(x[1])]
        sigle_s = [x[1] for x in w if dentro(x[0], X_STATO) and RE_SIGLA.match(x[1])]
        nums = [x for x in w if RE_NUM.match(x[1])]
        if sigle_f or sigle_s:
            if cur is None:
                continue
            m_f = RE_SIGLA.match(sigle_f[0]) if sigle_f else None
            op = {
                "descrizione": testo,
                "fase_finanziata": m_f.group(1) if m_f else "",
                "fase_parziale": bool(m_f and m_f.group(3) == "P"),
                "project_review": bool(m_f and m_f.group(3) == "PR"),
                "stato_attuativo": RE_SIGLA.match(sigle_s[0]).group(1) if sigle_s else "",
                "nuovo_inserimento": any(x[1] == "X" and dentro(x[0], X_NUOVO) for x in w),
                "paniere_pnrr": any(x[1] == "X" and dentro(x[0], X_PANIERE) for x in w),
                "pagina": p, "importi": importi(w),
            }
            cur["opere"].append(op)
            ultima = op
        elif nums and not testo and ultima is not None:
            # l'avanzamento (o un altro importo) stampato da solo sotto l'opera
            for k, v in importi(w).items():
                ultima["importi"].setdefault(k, v)
        elif testo and not nums and ultima is not None and cur is not None:
            # descrizione che va a capo sotto la riga dell'opera
            ultima["descrizione"] = (ultima["descrizione"] + " " + testo).strip()
        elif testo and nums:
            # riga di totale di programma o di classe: chiude l'intervento corrente
            cur, ultima = None, None

    # controlli
    n_op = sum(len(i["opere"]) for i in interventi.values())
    torna = diversi = 0
    for i in interventi.values():
        c = i["importi"].get("costo_totale")
        s = [o["importi"].get("costo_totale") for o in i["opere"]]
        if i["opere"] and c is not None and None not in s:
            if abs(sum(s) - c) < 0.05:
                torna += 1
            else:
                diversi += 1
                i["costo_opere_diverso"] = round(sum(s) - c, 2)
    senza = [k for k in codici if k not in interventi]
    json.dump({"doc": doc_id, "colonne": nomi, "interventi": interventi}, open(out, "w"),
              ensure_ascii=False, indent=1)
    print("%s: %d interventi letti su %d, %d opere; costo delle opere = costo dell'intervento in %d, diverso in %d; "
          "interventi senza riga trovata: %s" % (out, len(interventi), len(codici), n_op, torna, diversi, senza))


if __name__ == "__main__":
    main()
