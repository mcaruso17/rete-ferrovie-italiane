"""Controlla i dati estratti contro i totali che i documenti dichiarano.

Ogni controllo confronta una somma ricostruita con una cifra stampata nel PDF,
oppure con un'identita' che il documento stesso enuncia. Non e' un test del
codice: e' un test dei dati, e passa solo se i numeri estratti tornano con la
fonte. Uso:  python3 validate.py ../data/cdp-rfi-dataset.json
"""
import sys, os, json, re, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import TABELLA_A

D = json.load(open(sys.argv[1]))
ORD = {k: v["ordine"] for k, v in D["documenti"].items()}
DOCS = sorted(D["documenti"], key=lambda k: ORD[k])
esiti = []


def esito(nome, ok, tot, dettaglio=""):
    esiti.append((nome, ok, tot, dettaglio))
    quota = 100.0 * ok / tot if tot else 0.0
    segno = "OK " if ok == tot else ("~  " if quota >= 99 else "!! ")
    print("%s%-46s %5d/%-5d %5.1f%%  %s" % (segno, nome, ok, tot, quota, dettaglio))


def vicino(a, b, toll=0.05):
    return a is not None and b is not None and abs(a - b) <= toll


print("=" * 92)
print("1. IDENTITA' CONTABILI DI TABELLA A, riga per riga")
print("=" * 92)
ok = tot = 0
okc = totc = 0
for p in D["progetti"]:
    for s in p["storico"]:
        sch = TABELLA_A.get(s["doc"])
        if not sch or not s.get("fonti"):
            continue
        fin = s["finanziato"]
        somma = sum(v for v in s["fonti"].values() if v)
        tot += 1
        if vicino(fin, somma, 0.1):
            ok += 1
        if s["costo"] is not None and fin is not None and s["da_finanziare"] is not None:
            totc += 1
            if vicino(s["costo"], fin + s["da_finanziare"], 0.1):
                okc += 1
esito("risorse assegnate = somma delle fonti", ok, tot)
esito("costo = assegnate + fabbisogni", okc, totc,
      "" if okc == totc else "righe con stima limitata all'arco di Piano")

print()
print("=" * 92)
print("2. SOMMA DEGLI INTERVENTI contro i totali della Tavola 1")
print("=" * 92)
t1 = {}
for r in D["tavola1"]:
    v = re.sub(r"\s+", " ", r["voce"]).strip().upper()
    if v.startswith("A ") and "PORTAFOGLIO" in v:
        t1.setdefault(r["doc"], r["valori"])
somma = collections.defaultdict(float)
for p in D["progetti"]:
    for s in p["storico"]:
        if s["doc"] in TABELLA_A and s["costo"]:
            somma[s["doc"]] += s["costo"]
ok = tot = 0
for doc in DOCS:
    if doc not in t1:
        continue
    tot += 1
    atteso = t1[doc][0]
    ottenuto = somma[doc]
    scarto = ottenuto - atteso
    buono = abs(scarto) < 1.0
    ok += 1 if buono else 0
    print("   %-9s ricostruito %12.2f  dichiarato %12.2f  scarto %+8.2f  %s"
          % (doc, ottenuto, atteso, scarto, "ok" if buono else "DIVERGE"))
esito("costo di Tabella A = Tavola 1 riga A", ok, tot, "tolleranza 1 mln")

print()
print("=" * 92)
print("3. TABELLA C: le categorie sommano al totale stampato")
print("=" * 92)
ok = tot = 0
for doc in DOCS + [d for d in {r["doc"] for r in D["sintesi_ultimate"]} if d not in DOCS]:
    righe = [r for r in D["sintesi_ultimate"] if r["doc"] == doc]
    if not righe:
        continue
    cat = [r for r in righe if r["categoria"].upper() != "TOTALE"]
    tt = [r for r in righe if r["categoria"].upper() == "TOTALE"]
    if not cat or not tt:
        continue
    for col in (0, 1):
        tot += 1
        a = sum(r["valori"][col] for r in cat if len(r["valori"]) > col)
        b = tt[0]["valori"][col]
        if vicino(a, b, 0.05):
            ok += 1
        else:
            print("   %-9s colonna %d: categorie %.2f contro totale %.2f" % (doc, col, a, b))
esito("somma categorie = TOTALE del prospetto", ok, tot)

print()
print("=" * 92)
print("4. TABELLA C: il dettaglio somma alla variazione dichiarata")
print("=" * 92)
ok = tot = 0
for doc in sorted({u["doc"] for u in D["opere_ultimate"]}, key=lambda k: ORD.get(k, 9)):
    righe = [u for u in D["opere_ultimate"] if u["doc"] == doc]
    tt = [r for r in D["sintesi_ultimate"]
          if r["doc"] == doc and r["categoria"].upper() == "TOTALE"]
    if not tt or len(tt[0]["valori"]) < 3:
        continue
    tot += 1
    a = sum(u["costo"] or 0 for u in righe)
    b = tt[0]["valori"][2]
    buono = abs(a - b) < 1.0
    ok += 1 if buono else 0
    print("   %-9s %4d righe sommano %10.2f  dichiarato %10.2f  scarto %+7.2f  %s"
          % (doc, len(righe), a, b, a - b, "ok" if buono else "DIVERGE"))
esito("dettaglio opere ultimate = variazione", ok, tot, "tolleranza 1 mln")

print()
print("=" * 92)
print("5. LA SERIE DEL COSTRUITO si incatena fra documenti")
print("=" * 92)
serie = sorted([r for r in D["sintesi_ultimate"] if r["categoria"].upper() == "TOTALE"],
               key=lambda r: ORD.get(r["doc"], 9))
def anni(t):
    return set(re.findall(r"(?:19|20)\d{2}", t or ""))


def consecutivi(dopo, prima):
    """Vero se il documento dichiara proprio l'altro come proprio precedente.

    Ogni CdP nomina in copertina l'aggiornamento da cui parte. Quando quel
    documento non e' nel corpus (manca l'aggiornamento 2018-2019) lo stock
    iniziale non puo' agganciarsi al finale del precedente disponibile: e' un
    buco della raccolta, non un errore di estrazione.
    """
    att = anni(D["documenti"][dopo].get("precedente"))
    return bool(att) and att <= anni(D["documenti"][prima].get("titolo"))


ok = tot = salti = 0
prec = None
for r in serie:
    if prec is not None:
        if not consecutivi(r["doc"], prec[0]):
            salti += 1
            print("   %-9s parte da %10.2f ma dichiara come precedente %r,"
                  " che non e' nel corpus: anello non verificabile"
                  % (r["doc"], r["valori"][0],
                     D["documenti"][r["doc"]].get("precedente")))
        else:
            tot += 1
            buono = vicino(r["valori"][0], prec[1], 0.05)
            ok += 1 if buono else 0
            print("   %-9s inizia da %10.2f, %-9s finiva a %10.2f  %s"
                  % (r["doc"], r["valori"][0], prec[0], prec[1],
                     "ok" if buono else "SALTO di %+.2f" % (r["valori"][0] - prec[1])))
    prec = (r["doc"], r["valori"][1])
esito("stock finale = stock iniziale del successivo", ok, tot,
      "%d anello saltato: manca l'aggiornamento intermedio" % salti if salti else "")

print()
print("=" * 92)
print("6. TAVOLA 2: le righe che dichiarano la propria formula")
print("=" * 92)
FORMULA = re.compile(r"\((\d+(?:\s*\+\s*\d+)+)\)")

# Formule che la Tavola 2 stampa sbagliate. Non sono errori di estrazione: il
# riferimento incrociato nel PDF e' scorretto e la somma torna solo con quello
# qui a fianco, verificato su tutti gli anni della colonna.
ERRATA = {
    # "MEF (10+13+14+15+16)": la riga 16 e' il MIMS, che il MEF non comprende.
    ("agg2021", "9"): ["10", "13", "14", "15"],
    # "RISORSE DA STATO (9+15)": la 15 e' gia' dentro la 9; l'addendo e' la 16.
    ("cdp2022", "8"): ["9", "16"],
    # "MIT, MIC (17+...+29)": la 29 apre il blocco UE, il capitolo finisce a 28.
    ("cdp2022", "16"): [str(i) for i in range(17, 29)],
    # "MIT (16+...+29)": il blocco prosegue fino alla 31 piu' la riga del
    # Commissario per il Sisma, che il documento numera di nuovo 29: l'asterisco
    # dice di sommare tutte le righe che portano quel numero.
    ("agg2024", "15"): [str(i) if i != 29 else "29*" for i in range(16, 32)],
    # "RISORSE DA EE.LL. e ALTRO (35+36)": la riga richiama se stessa.
    ("agg2024", "35"): ["36", "37"],
    # "RISORSE UE (34+...+39)": idem, la riga 34 richiama se stessa.
    ("agg2025", "34"): [str(i) for i in range(35, 40)],
}

# In agg2024 il documento riusa i numeri 29, 30 e 31 in due blocchi diversi:
# un addendo si risolve sulla riga piu' vicina, nell'ordine di stampa.
ordine = collections.defaultdict(list)
for r in D["tavola2"]:
    ordine[r["doc"]].append(r)


def risolvi(righe, i_rif, num):
    """Righe che rispondono a un numero di addendo.

    Con l'asterisco valgono tutte le omonime; altrimenti una sola, scelta fra
    quelle con almeno un valore diverso da zero (in agg2024 il documento
    numera 12 anche un capitolo vuoto che il totale MEF non conta) e poi per
    vicinanza nell'ordine di stampa.
    """
    tutte = num.endswith("*")
    num = num.rstrip("*")
    cand = [(abs(j - i_rif), j) for j, x in enumerate(righe) if str(x["riga"]) == num]
    if not cand:
        return []
    if tutte:
        return [righe[j] for _d, j in sorted(cand)]
    piene = [c for c in cand if any(righe[c[1]]["valori"])]
    return [righe[min(piene or cand)[1]]]


ok = tot = 0
corretti = 0
for doc, righe in ordine.items():
    for i, r in enumerate(righe):
        m = FORMULA.search(r["voce"])
        if not m:
            continue
        num = str(r["riga"])
        stampata = [a.strip() for a in m.group(1).split("+")]
        addendi = ERRATA.get((doc, num), stampata)
        if addendi is not stampata:
            corretti += 1
        gruppi = [risolvi(righe, i, a) for a in addendi]
        if not all(gruppi):
            continue
        parti = [x for g in gruppi for x in g]
        for k, anno in enumerate(r["anni"]):
            atteso = r["valori"][k] if k < len(r["valori"]) else None
            if atteso is None:
                continue
            vals = [p["valori"][k] if k < len(p["valori"]) else None for p in parti]
            if all(v is None for v in vals):
                continue
            somma = sum(v or 0 for v in vals)
            tot += 1
            if abs(somma - atteso) <= 2.5:
                ok += 1
            elif tot - ok <= 6:
                print("   %-9s riga %-5s %s: %s = %.0f, dichiarato %.0f"
                      % (doc, num, anno, "+".join(addendi), somma, atteso))
esito("somme interne dichiarate dalla Tavola 2", ok, tot,
      "tolleranza 2,5 mln; %d formule corrette secondo l'errata" % corretti)

print()
print("=" * 92)
print("7. COERENZA INTERNA del dataset")
print("=" * 92)
codici = [p["codice"] for p in D["progetti"]]
esito("codici intervento senza duplicati",
      len(set(codici)), len(codici))
senza = [p for p in D["progetti"] if not p["descrizione"]]
esito("interventi con una descrizione", len(D["progetti"]) - len(senza),
      len(D["progetti"]), "%d senza" % len(senza) if senza else "")
neg = [p for p in D["progetti"] if p["costo_totale"] is not None and p["costo_totale"] < 0]
esito("costi non negativi", len(D["progetti"]) - len(neg), len(D["progetti"]))
fuori = [p for p in D["progetti"]
         if p["da_finanziare"] is not None and p["costo_totale"]
         and p["da_finanziare"] > p["costo_totale"] + 0.1]
esito("fabbisogno non superiore al costo",
      len(D["progetti"]) - len(fuori), len(D["progetti"]),
      ", ".join(p["codice"] for p in fuori[:4]) if fuori else "")
# il prospetto stampa "n.a." per le opere senza data di esercizio: assenza
# dichiarata, non dato malformato
datate = [u for u in D["opere_ultimate"] if u["data_esercizio"]]
storte = [u for u in datate
          if not re.match(r"^\d{2}/\d{2}/\d{4}$", u["data_esercizio"])]
esito("date di messa in esercizio ben formate",
      len(datate) - len(storte), len(datate),
      "%d opere con data n.a. nel documento" % (len(D["opere_ultimate"]) - len(datate)))
CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
cup = [u for u in D["opere_ultimate"] if u["cup"] and not CUP.match(u["cup"])]
esito("CUP nel formato a 15 caratteri",
      sum(1 for u in D["opere_ultimate"] if u["cup"]) - len(cup),
      sum(1 for u in D["opere_ultimate"] if u["cup"]))

print()
print("=" * 92)
brutti = [e for e in esiti if e[2] and e[1] < e[2]]
gravi = [e for e in brutti if e[2] and e[1] / e[2] < 0.99]
print("ESITO: %d controlli, %d passati in pieno, %d con scarti, %d sotto il 99%%"
      % (len(esiti), len(esiti) - len(brutti), len(brutti), len(gravi)))
for n, o, t, _ in gravi:
    print("   sotto soglia: %s (%d/%d)" % (n, o, t))
