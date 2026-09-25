"""Esporta il dataset in CSV, un file per tabella.

I JSON restano la fonte completa; questi CSV servono a chi vuole aprire i dati
in un foglio di calcolo. Uso:  python3 export_csv.py ../data/cdp-rfi-dataset.json ../data
"""
import sys, os, re, csv, json

D = json.load(open(sys.argv[1]))
OUT = sys.argv[2]

# Chi apre un CSV in un foglio di calcolo non vede gli avvisi che in pagina
# accompagnano i dati dedotti. La natura del dato sta quindi in una colonna di
# ogni riga: si perde solo cancellandola apposta.
NATURA_COMUNI = ("comune nominato nel titolo dell'intervento, non comune "
                 "attraversato: i CdP non contengono tracciati")
NATURA_AGGANCI = ("dedotto: i CdP Investimenti non dichiarano la linea; "
                  "associazione ricavata da nomi e comuni citati, in corso di "
                  "verifica")


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
                      s["avanzamento"] if s["avanzamento"] is not None else "",
                      "|".join(s.get("stato") or [])])
scrivi("serie-storica.csv",
       ["codice", "documento", "pagina", "costo_mln", "finanziato_mln",
        "da_finanziare_mln", "avanzamento_mln", "stato_attuativo"], righe)

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
                              p["ultimo_doc"], NATURA_COMUNI])
    scrivi("comuni-interventi.csv",
           ["codice_intervento", "descrizione", "programma", "com_istat_code",
            "comune", "prov_acr", "provincia", "reg_istat_code",
            "ordine_di_citazione", "ordine_geografico",
            "costo_totale_mln", "ultimo_documento", "natura_del_dato"], righe)
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

# --- registro ufficiale delle linee (CdP Servizi, Allegato 3) --------------
A = json.load(open(app)) if os.path.exists(app) else {}
REG = A.get("registro_rfi", {})
FON = A.get("registro_rfi_fonti", {})
RRL = (A.get("rete_rfi") or {}).get("linee") or {}
righe = [[c, r["n"], r.get("g") or "", r.get("km"), r.get("tr"),
          FON.get(r.get("doc"), r.get("doc")), r.get("pag"),
          FON.get(r.get("doc_n"), r.get("doc_n")), r.get("pag_n"),
          # dalla rete RFI: il codice di linea commerciale e gli attributi
          (RRL.get(c) or {}).get("rfi", ""), "si" if c in RRL else "no",
          (RRL.get(c) or {}).get("ten", ""), (RRL.get(c) or {}).get("peso", ""),
          (RRL.get(c) or {}).get("dal", "")]
         for c, r in sorted(REG.items())]
scrivi("linee-rfi.csv",
       ["codice_linea", "denominazione", "gruppo_traffico", "km",
        "treni_giorno_programmati", "fonte_dati", "pagina_dati",
        "fonte_denominazione", "pagina_denominazione",
        "codice_rete_rfi", "tracciato_rfi", "rete_ten_t", "massa_assiale",
        "in_esercizio_dal_osm"], righe)

# --- agganci intervento -> linea, dai due registri --------------------------
# Una riga per coppia intervento-linea, su entrambi i registri: chi filtra per
# "confermato" trova le due righe della stessa conferma, una per registro.
byc = {x["codice"]: x for x in D["progetti"]}
CONF = A.get("confermati", {})
OSMN = A.get("linee", {})
righe = []
for cod, lista in sorted((A.get("linee_rfi_intervento") or {}).items()):
    for t in lista:
        righe.append([cod, (byc.get(cod) or {}).get("descrizione", ""),
                      "registro RFI (CdP Servizi, Allegato 3)", t["c"],
                      (REG.get(t["c"]) or {}).get("n", ""), t["conf"],
                      "nome" if len(t["capi"]) >= 2 else "nome-parziale",
                      "|".join(t["capi"]), "",
                      "si" if (CONF.get(cod) or {}).get("rfi") == t["c"] else "no",
                      NATURA_AGGANCI])
for cod, lista in sorted((A.get("linee_intervento") or {}).items()):
    for t in lista:
        righe.append([cod, (byc.get(cod) or {}).get("descrizione", ""),
                      "OpenStreetMap (relazione route=railway)", t["id"],
                      t["nome"], t["conf"], "+".join(t["prova"]),
                      "|".join(t["capi"]), t.get("comuni") or "",
                      "si" if str((CONF.get(cod) or {}).get("osm")) == str(t["id"]) else "no",
                      NATURA_AGGANCI])
# il terzo registro: il Piano Commerciale di RFI, dove il legame e' scritto da
# RFI. Si esportano i codici e i nomi, non la geometria: la licenza del
# servizio non e' indicata
PCD = A.get("pc") or {}
for cod, ids in sorted((PCD.get("per_int") or {}).items()):
    for i in ids:
        e = PCD["el"][i]
        righe.append([cod, (byc.get(cod) or {}).get("descrizione", ""),
                      "RFI Piano Commerciale 2026 (%s)" % {"tr": "tratta", "lp": "localita' potenziata",
                                                          "ln": "localita' nuova"}[e["t"]],
                      e.get("cod", ""), e.get("den") or e.get("n", ""), "dichiarato",
                      "codice CdP scritto da RFI", "", "", "",
                      "fonte esterna (dichiarato da RFI)"])
scrivi("agganci-linee.csv",
       ["codice_intervento", "descrizione", "registro", "codice_linea",
        "linea", "confidenza", "prova", "capi_nominati",
        "comuni_citati_attraversati", "confermato", "natura_del_dato"], righe)

# --- parte Servizi: fonti per cassa, impieghi, assegnazioni per CUP ---------
S = A.get("servizi") or {}
TIT_S = {e["id"]: e["titolo"] for e in S.get("edizioni", [])}
SEZ_S = {"esercizio": "conto esercizio", "impianti": "conto impianti",
         "totale": "totale fonti", "spesa_residuo": "spesa residuo contratti precedenti",
         "residuo": "fonti residuo contratti precedenti"}
righe = []
for tab, chiave in (("4b fonti per cassa", "fonti"), ("4a impieghi per competenza", "impieghi")):
    for doc, lista in (S.get(chiave) or {}).items():
        for r in lista:
            righe.append([TIT_S.get(doc, doc), tab, r["r"], SEZ_S.get(r["s"], r["s"]),
                          r["v"], r["c"], r["pm"]] + list(r["a"]) +
                         [r["t"], r["o"], r["k"], r["p"]])
scrivi("servizi-fonti-cassa.csv",
       ["edizione", "allegato", "rigo", "sezione", "voce", "capitolo_bilancio",
        "cumulato_al_2021_pm", "2022", "2023", "2024", "2025", "2026",
        "totale_2022_2026", "oltre_2026", "totale_complessivo", "pagina"], righe)
righe = []
for a_ in S.get("assegnazioni", []):
    righe.append([a_["cup"], a_["d"], "Allegato 4c", a_["f"], a_["atto"], a_["rif"],
                  a_["prec"], a_["corr"], a_["t"], a_["sede"], "",
                  TIT_S.get(a_["doc"], a_["doc"]), a_["p"]])
REGN = A.get("regioni", {})
for p in S.get("pnrr", []):
    righe.append([p["cup"], p["n"], "Allegato 12 (PNRR)", "PNRR " + p["m"], "", "",
                  "", p["pnrr"], p["t"], "", "|".join(REGN.get(r, r) for r in p["reg"]),
                  TIT_S.get(p["doc"], p["doc"]), p["p"]])
scrivi("servizi-assegnazioni-cup.csv",
       ["cup", "descrizione", "allegato", "fonte", "atto_integrativo",
        "riferimento_normativo", "cdps_2016_2021", "cdps_2022_2026",
        "totale_riga", "sede_doit_nominata", "regioni_nominate", "edizione",
        "pagina"], righe)

# --- catalogo dei file ------------------------------------------------------
# Un solo elenco, da cui escono sia il riquadro dei download in pagina sia il
# LEGGIMI.txt: due descrizioni scritte a mano divergerebbero al primo file
# nuovo. "natura" e' la cosa che conta: letto dal documento (e verificato sui
# totali stampati), dedotto da regole di questo progetto, o preso da una fonte
# esterna.
DOC = "dal documento"
DED = "dedotto"
EST = "fonte esterna"
CAT = [
    ("progetti.csv", "Interventi, uno per riga",
     "Tabella A e B dei CdP Investimenti: programma, classe, CUP, stato, "
     "costi all'ultimo contratto in cui l'intervento compare.", DOC,
     "CdP Investimenti 2017-2026"),
    ("serie-storica.csv", "Interventi, contratto per contratto",
     "Costo, finanziato, da finanziare, avanzamento e stato attuativo di ogni "
     "intervento in ciascun contratto, con la pagina del PDF. Lo stato manca "
     "dove il documento non lo indica, soprattutto per i programmi pluriennali "
     "e la Tabella B, che sono programmi e non opere singole.", DOC,
     "CdP Investimenti 2017-2026"),
    ("opere-ultimate.csv", "Opere entrate in esercizio",
     "Tabella C, dettaglio: descrizione, CUP, costo, data di messa in "
     "esercizio.", DOC, "CdP Investimenti 2017-2026"),
    ("opere-ultimate-sintesi.csv", "Opere entrate in esercizio, prospetto",
     "Tabella C, prospetto cumulato per categoria.", DOC,
     "CdP Investimenti 2017-2026"),
    ("capitoli-piani-gestionali.csv", "Cassa per capitolo di bilancio",
     "Tavola 2: importi per capitolo e piano gestionale, anno per anno.", DOC,
     "CdP Investimenti 2017-2026"),
    ("linee-rfi.csv", "Registro ufficiale delle linee",
     "%d linee RFI con codice, denominazione, gruppo di traffico, km e treni "
     "al giorno dell'edizione piu' recente, con documento e pagina di "
     "provenienza. Le ultime colonne vengono dalla rete RFI (codice di linea "
     "commerciale, rete TEN-T, massa assiale) e, per la data di apertura, da "
     "OpenStreetMap." % len(REG), DOC,
     "CdP Servizi 2022-2026, Allegato 3; rete RFI; OpenStreetMap"),
    ("servizi-fonti-cassa.csv", "Servizi: fonti per cassa e impieghi",
     "Allegato 4b di ogni edizione leggibile (leggi, capitolo di bilancio, "
     "profilo annuo, oltre il 2026, residuo dei contratti precedenti) e "
     "Allegato 4a del contratto base (impieghi per competenza).", DOC,
     "CdP Servizi 2022-2026, Allegati 4a e 4b"),
    ("servizi-assegnazioni-cup.csv", "Servizi: assegnazioni per CUP",
     "Allegato 4c (fondi straordinari, per CUP e decreto) e opere PNRR "
     "attribuite al CdP-S (Allegato 12). E' l'unico dettaglio per progetto "
     "della parte Servizi, e copre una frazione piccola del totale. Sede DOIT "
     "e regioni sono quelle scritte nella descrizione, non dedotte.", DOC,
     "CdP Servizi 2022-2026, atto integrativo 2026, Allegati 4c e 12"),
    ("comuni-interventi.csv", "Comuni nominati negli interventi",
     "I comuni citati nel titolo di ciascun intervento. Non sono i comuni "
     "attraversati: i contratti non contengono tracciati.", DED,
     "regole di lettura dei nomi di luogo (tools/toponimi.py)"),
    ("agganci-linee.csv", "Agganci intervento-linea",
     "Per ogni intervento, le linee su cui insiste. Le righe del registro RFI "
     "e di OpenStreetMap sono dedotte, con confidenza, prova e conferma, e sono "
     "in corso di verifica; le righe del Piano Commerciale RFI sono dichiarate "
     "da RFI, che scrive il codice CdP accanto al progetto. La colonna "
     "natura_del_dato le distingue riga per riga.", DED,
     "tools/aggancio.py, tools/registro_rfi.py e tools/aggancio_pc.py"),
    ("cup-da-cercare.csv", "CUP da interrogare",
     "Tutti i CUP presenti nei contratti, pronti per un'interrogazione su "
     "OpenCUP.", DOC, "CdP Investimenti 2017-2026"),
    ("rete-rfi.geojson", "Rete RFI",
     "Le tratte della rete RFI con codice di tratta e di linea, linea "
     "commerciale (il codice del registro con la lettera cambiata), rete "
     "TEN-T, massa assiale. Comprende anche 46 tratte di progetto (codice PRJ), "
     "che il sito non disegna come rete in esercizio.", EST,
     "RFI, rete del Piano Commerciale 2026 (servizio ArcGIS pubblico)"),
    ("piano-commerciale-2026.json", "Progetti del Piano Commerciale RFI",
     "Tratte e localita' di progetto con il codice dell'intervento CdP scritto "
     "da RFI, anno di attivazione e caratteristiche, e la geometria "
     "semplificata.", EST,
     "RFI, Piano Commerciale 2026, Scenari infrastrutturali"),
    ("rete-ferroviaria.geojson", "Tracciati della rete",
     "Linee in esercizio, in costruzione e in progetto, semplificate a circa "
     "15 m. Licenza ODbL: attribuzione a OpenStreetMap e condivisione alle "
     "stesse condizioni.", EST, "OpenStreetMap, contributori, ODbL"),
    ("linee-ferroviarie.geojson", "Linee con nome",
     "Relazioni route=railway con nome, data di apertura dove nota e "
     "geometria. Licenza ODbL.", EST, "OpenStreetMap, contributori, ODbL"),
    ("cdp-rfi-dataset.json", "Dataset completo (JSON)",
     "Tutto quanto letto dai CdP Investimenti, normalizzato, con storico e "
     "pagine.", DOC, "CdP Investimenti 2017-2026"),
    ("validazione.txt", "Rapporto di validazione, Investimenti",
     "I controlli dei dati ricostruiti contro i totali stampati nei PDF.",
     DOC, "tools/validate.py"),
    ("validazione-servizi.txt", "Rapporto di validazione, Servizi",
     "Chilometri del registro linee e tabelle finanziarie (4a, 4b, 4c, 12) "
     "ricostruiti contro i totali stampati.", DOC,
     "tools/extract_servizi.py e tools/extract_servizi_fin.py"),
]
TIT_PDF = {v["file"]: v["titolo"] for v in D["documenti"].values()}
TIT_PDF.update({
    "CdP_Servizi_2022-2026.pdf": "CdP 2022-2026 parte Servizi",
    "CdP_Servizi_2022-2026_AI1_Agg2023.pdf": "CdP Servizi, primo atto integrativo (agg. 2023)",
    "CdP_Servizi_2022-2026_AI2_Agg2024.pdf": "CdP Servizi, secondo atto integrativo (agg. 2024)",
    "CdP_Servizi_2022-2026_AI3_Agg2025.pdf": "CdP Servizi, terzo atto integrativo (agg. 2025)",
    "CdP_Servizi_2022-2026_AI4_Agg2026.pdf": "CdP Servizi, quarto atto integrativo (agg. 2026)",
    "PIR_2027_dicembre_2025_vDEF.pdf": "Prospetto Informativo della Rete 2027 (consultato, non elaborato)",
})
radice = os.path.dirname(os.path.abspath(OUT))
pdf = sorted(f for f in os.listdir(radice) if f.lower().endswith(".pdf"))
catalogo = {
    "dati": [{"file": f, "titolo": t, "contenuto": c, "natura": n, "fonte": fo}
             for f, t, c, n, fo in CAT if os.path.exists(os.path.join(OUT, f))],
    "documenti": [{"file": f, "titolo": TIT_PDF.get(f, f)} for f in pdf],
    "nature": {
        DOC: "letto dai PDF e, dove il documento stampa un totale, verificato "
             "contro quel totale",
        DED: "prodotto da regole di questo progetto: non sta nei documenti, "
             "e puo' essere sbagliato",
        EST: "preso da una fonte esterna ai contratti, con la sua licenza",
    },
}
json.dump(catalogo, open(os.path.join(OUT, "catalogo.json"), "w"),
          ensure_ascii=False, indent=1)
mancanti = [f for f, *_ in CAT if not os.path.exists(os.path.join(OUT, f))]
with open(os.path.join(OUT, "LEGGIMI.txt"), "w") as fh:
    fh.write("I DATI DI QUESTA PIATTAFORMA\n\n")
    fh.write("Ogni file ha una natura, e conta piu' del contenuto:\n")
    for k, v in catalogo["nature"].items():
        fh.write("  %-15s %s\n" % (k, v))
    fh.write("\n")
    for x in catalogo["dati"]:
        fh.write("%s\n  %s. %s\n  natura: %s\n  fonte: %s\n\n"
                 % (x["file"], x["titolo"], x["contenuto"], x["natura"],
                    x["fonte"]))
    fh.write("DOCUMENTI ORIGINALI\n\n")
    for x in catalogo["documenti"]:
        fh.write("%s\n  %s\n" % (x["file"], x["titolo"]))
print("catalogo.json e LEGGIMI.txt: %d file di dati, %d documenti"
      % (len(catalogo["dati"]), len(catalogo["documenti"])))
if mancanti:
    print("  assenti, esclusi dal catalogo: %s" % ", ".join(mancanti))
