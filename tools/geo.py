"""Aggiunge al dataset dell'app la geografia: mappa e attribuzione regionale.

Attribuisce ogni intervento a una o piu' regioni, deducendola dal nome.

I Contratti di Programma non contengono un campo territoriale: la regione qui
e' DEDOTTA dai luoghi citati nella descrizione dell'intervento, confrontati con
i nomi dei comuni e delle province ISTAT. E' una stima, non un dato del
documento, e va presentata come tale.

Regole:
  * si cercano i nomi di luogo con confini di parola, dal piu' lungo al piu'
    corto, cosi' che "Reggio Calabria" vinca su "Reggio";
  * i nomi ambigui (stesso comune in piu' regioni) valgono solo se capoluogo;
  * il nome deve comparire con l'iniziale maiuscola, cioe' come nome proprio:
    senza questo vincolo "trasporto di massa" diventa la citta' di Massa;
  * si guarda solo la descrizione dell'intervento, non il sotto-programma: la
    direttrice "Brennero-Verona-Bologna" non rende veneta una galleria altoatesina;
  * i nomi che sono anche parole comuni italiane sono esclusi, perche'
    produrrebbero falsi positivi su descrizioni tecniche;
  * un intervento che tocca piu' regioni ripartisce l'importo in proporzione a
    quante volte ciascuna regione e' citata nella descrizione, dopo aver
    scartato quelle sotto il 15% delle menzioni. Una divisione in parti uguali
    darebbe meta' dell'anello ferroviario di Roma alla Toscana, per via di una
    sola occorrenza di "Firenze" fra sei di "Roma". Resta un surrogato: il peso
    vero sarebbe la lunghezza di tratta per regione, che i documenti non danno.
    Le quote sommano a 1, quindi i totali regionali sommano al totale attribuito.
"""
import json, re, sys, os, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toponimi import ESCLUSI, norm, testo_confronto, compila, trova

MUN = sys.argv[1]
PROV = sys.argv[2]
APP = sys.argv[3]
MAPPA = sys.argv[4]
OUT = sys.argv[5]

# sotto questa quota di menzioni la regione e' considerata una citazione
# incidentale (il nome di una linea che passa di li'), non una sede dei lavori
SOGLIA_MENZIONI = 0.15

# luoghi e denominazioni ferroviarie assenti dall'elenco dei comuni
MANUALI = {
    "brennero": "04", "vesuvio": "15", "terzo valico": "07",
    "valico dei giovi": "07", "metaponto": "17", "malpensa": "03",
    "fiumicino": "12", "orte": "12", "salento": "16", "gargano": "16",
    "sannio": "15", "irpinia": "15", "cilento": "15", "murgia": "16",
    "sibari": "18", "sila": "18", "aspromonte": "18", "etna": "19",
    "gallura": "20", "sulcis": "20", "monferrato": "01", "langhe": "01",
    "brianza": "03", "valtellina": "03", "valcamonica": "03",
    "cadore": "05", "carnia": "06", "romagna": "08", "chianti": "09",
    "maremma": "09", "conero": "11", "fucino": "13", "matese": "14",
    "pollino": "17", "iblei": "19", "peloritani": "19",
    "santa maria novella": "09", "tiburtina": "12", "termini": "12",
    "fontanarossa": "19", "punta raisi": "19", "capodichino": "15",
    "marco polo": "05", "linate": "03", "caselle": "01",
    "campo marzio": "06", "castelli romani": "12", "brignole": "07",
    "principe": "07", "mestre": "05", "tiburtina": "12",
    # Cervaro esiste sia in Lazio sia come localita' pugliese sulla
    # Napoli-Bari: in questo corpus e' sempre la seconda
    "cervaro": "16",
}


def carica():
    mun = json.load(open(MUN))
    prov = json.load(open(PROV))
    capoluoghi, reg_nome = {}, {}
    for f in prov["features"]:
        p = f["properties"]
        capoluoghi[norm(p["prov_name"])] = p["reg_istat_code"]
        reg_nome[p["reg_istat_code"]] = p["reg_name"].split("/")[0]
    conteggio = collections.defaultdict(set)
    for f in mun["features"]:
        p = f["properties"]
        conteggio[norm(p["name"])].add(p["reg_istat_code"])
        reg_nome[p["reg_istat_code"]] = p["reg_name"].split("/")[0]
    gaz = {}
    for nome, regs in conteggio.items():
        if not nome or nome in ESCLUSI or len(nome) < 5:
            continue
        if len(regs) == 1:
            gaz[nome] = next(iter(regs))
    # i capoluoghi vincono sempre, anche se il nome e' condiviso o corto
    for nome, reg in capoluoghi.items():
        if nome and nome not in ESCLUSI:
            gaz[nome] = reg
    gaz.update(MANUALI)
    return gaz, reg_nome


def main():
    gaz, reg_nome = carica()
    pattern = compila(gaz)

    app = json.load(open(APP))
    attrib, pesi, senza = {}, {}, 0
    for p in app["progetti"]:
        menzioni, ordine = collections.Counter(), []
        for nome in trova(p.get("n") or "", pattern):
            r = gaz[nome]
            if r not in menzioni:
                ordine.append(r)
            menzioni[r] += 1
        if not menzioni:
            senza += 1
            continue
        tot = sum(menzioni.values())
        forti = [r for r in ordine if menzioni[r] / tot >= SOGLIA_MENZIONI]
        if not forti:
            forti = ordine
        somma = sum(menzioni[r] for r in forti)
        attrib[p["c"]] = forti
        pesi[p["c"]] = {r: round(menzioni[r] / somma, 4) for r in forti}
    app["regioni"] = {r: reg_nome[r] for r in sorted(reg_nome)}
    app["attribuzione_regionale"] = attrib
    app["pesi_regionali"] = pesi
    app["mappa"] = json.load(open(MAPPA))
    json.dump(app, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))

    tot = len(app["progetti"])
    print("interventi con almeno una regione: %d su %d (%.0f%%)"
          % (tot - senza, tot, 100 * (tot - senza) / tot))
    c = collections.Counter(len(v) for v in attrib.values())
    print("regioni per intervento:", dict(sorted(c.items())))
    per_reg = collections.Counter()
    for regs in attrib.values():
        for r in regs:
            per_reg[reg_nome[r]] += 1
    for r, n in per_reg.most_common():
        print("   %-24s %3d" % (r, n))


main()
