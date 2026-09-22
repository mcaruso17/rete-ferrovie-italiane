"""Esporta il dataset in CSV, un file per tabella.

I JSON restano la fonte completa; questi CSV servono a chi vuole aprire i dati
in un foglio di calcolo. Uso:  python3 export_csv.py ../data/cdp-rfi-dataset.json ../data
"""
import sys, os, re, csv, json

D = json.load(open(sys.argv[1]))
OUT = sys.argv[2]


def scrivi(nome, intestazione, righe):
    percorso = os.path.join(OUT, nome)
    with open(percorso, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(intestazione)
        w.writerows(righe)
    print("%-32s %6d righe" % (nome, len(righe)))


# --- interventi di Tabella A e B, una riga per intervento -------------------
righe = []
for p in sorted(D["progetti"], key=lambda x: x["codice"]):
    ultimo = next((s for s in p["storico"] if s["doc"] == p["ultimo_doc"]), None)
    righe.append([
        p["codice"], p["descrizione"], p["programma_num"], p["programma"],
        p["sottoprogramma"] or "", p["classe"], p["classe_nome"],
        p["cup"] or "", "|".join(p["cups"]), p["classe_dpp"] or "",
        "si" if p["paniere_pnrr"] else "no",
        "|".join(p["stato_attuativo"] or []), p["stato_finanziario"],
        p["ultimo_doc"], ultimo["pagina"] if ultimo else "",
        p["costo_totale"], p["finanziato"], p["da_finanziare"],
        p["avanzamento"] if p.get("avanzamento") is not None else "",
    ])
scrivi("progetti.csv",
       ["codice", "descrizione", "programma_num", "programma", "sottoprogramma",
        "classe", "classe_nome", "cup", "cups", "classe_dpp", "paniere_pnrr",
        "stato_attuativo", "stato_finanziario", "ultimo_documento", "pagina",
        "costo_totale_mln", "finanziato_mln", "da_finanziare_mln",
        "avanzamento_mln"], righe)

# --- la stessa cosa documento per documento --------------------------------
ORD = {k: v["ordine"] for k, v in D["documenti"].items()}
righe = []
for p in sorted(D["progetti"], key=lambda x: x["codice"]):
    for s in sorted(p["storico"], key=lambda s: ORD.get(s["doc"], 9)):
        righe.append([p["codice"], s["doc"], s["pagina"], s["costo"],
                      s["finanziato"], s["da_finanziare"],
                      s["avanzamento"] if s["avanzamento"] is not None else ""])
scrivi("serie-storica.csv",
       ["codice", "documento", "pagina", "costo_mln", "finanziato_mln",
        "da_finanziare_mln", "avanzamento_mln"], righe)

# --- Tabella C: le opere entrate in esercizio ------------------------------
righe = [[u["doc"], u["page"], u["riga"], u["cup"] or "", u["npp"] or "",
          u["descr"], u["costo"], u["data_esercizio"] or "n.a."]
         for u in D["opere_ultimate"]]
scrivi("opere-ultimate.csv",
       ["documento", "pagina", "riga", "cup", "npp", "descrizione",
        "costo_mln", "data_messa_in_esercizio"], righe)

# --- Tabella C: il prospetto cumulato per categoria ------------------------
righe = []
for s in D["sintesi_ultimate"]:
    # il prospetto porta due stock cumulati piu' la loro differenza: l'ultimo
    # valore non ha un anno proprio, e' la variazione fra i due
    etichette = list(s["anni"]) + ["variazione"]
    for i, v in enumerate(s["valori"]):
        if i < len(etichette):
            righe.append([s["doc"], s["page"], s["categoria"], s["voce"],
                          etichette[i], v])
scrivi("opere-ultimate-sintesi.csv",
       ["documento", "pagina", "categoria", "voce", "anno",
        "importo_cumulato_mln"], righe)

# --- Tavola 2: cassa per capitolo e piano gestionale -----------------------
righe = []
for r in D["tavola2"]:
    for i, anno in enumerate(r["anni"]):
        v = r["valori"][i] if i < len(r["valori"]) else None
        if v is not None:
            righe.append([r["doc"], r["page"], r["riga"], r["sezione"] or "",
                          r["capitolo"] or "", r["pg"] or "", r["voce"],
                          anno, v])
scrivi("capitoli-piani-gestionali.csv",
       ["documento", "pagina", "riga", "sezione", "capitolo",
        "piano_gestionale", "voce", "anno", "importo_mln"], righe)

# --- i comuni che il contratto nomina, uno per riga ------------------------
# questi NON sono i comuni attraversati: sono quelli citati nel titolo
righe = []
app = os.path.join(OUT, "cdp-rfi-app.json")
if os.path.exists(app):
    A = json.load(open(app))
    com, per = A.get("comuni", {}), A.get("comuni_intervento", {})
    forme, tratte = A.get("mappa_comuni", {}), A.get("tratte_schematiche", {})
    byc = {x["codice"]: x for x in D["progetti"]}
    for cod in sorted(per):
        p = byc.get(cod)
        # la stessa sequenza della spezzata sulla mappa: i punti messi in fila
        # lungo l'asse del gruppo, che non e' l'ordine in cui il PDF li cita
        seq = {}
        if cod in tratte:
            punti = re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", tratte[cod])
            dove = {(str(forme[i][1]), str(forme[i][2])): i
                    for i in per[cod] if i in forme}
            for n, xy in enumerate(punti, 1):
                if xy in dove:
                    seq[dove[xy]] = n
        for n_cit, istat in enumerate(per[cod], 1):
            c = com.get(istat)
            if p and c:
                righe.append([cod, p["descrizione"], p["programma"], istat,
                              c[0], c[1], c[3], c[2], n_cit,
                              seq.get(istat, ""), p["costo_totale"],
                              p["ultimo_doc"]])
    scrivi("comuni-interventi.csv",
           ["codice_intervento", "descrizione", "programma", "com_istat_code",
            "comune", "prov_acr", "provincia", "reg_istat_code",
            "ordine_di_citazione", "ordine_geografico",
            "costo_totale_mln", "ultimo_documento"], righe)
else:
    print("cdp-rfi-app.json assente: comuni-interventi.csv non aggiornato")

# --- i CUP da interrogare su OpenCUP per avere la localizzazione -----------
righe = []
for p in sorted(D["progetti"], key=lambda x: x["codice"]):
    ultimo = next((s for s in p["storico"] if s["doc"] == p["ultimo_doc"]), None)
    for cup in ([p["cup"]] if p["cup"] else []) + p["cups"]:
        righe.append([cup, "A/B", p["codice"], p["descrizione"], p["programma"],
                      p["costo_totale"], p["ultimo_doc"],
                      ultimo["pagina"] if ultimo else ""])
# anche le opere gia' entrate in esercizio portano un CUP interrogabile
for u in D["opere_ultimate"]:
    if u["cup"]:
        righe.append([u["cup"], "C", "", u["descr"], "", u["costo"],
                      u["doc"], u["page"]])
scrivi("cup-da-cercare.csv",
       ["cup", "tabella", "codice_intervento", "descrizione", "programma",
        "importo_mln", "documento", "pagina"], righe)
