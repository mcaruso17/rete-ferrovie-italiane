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
  * un intervento che tocca piu' regioni ripartisce l'importo in parti uguali,
    cosi' che la somma regionale resti pari al totale attribuito.
"""
import json, re, sys, unicodedata, collections

MUN = sys.argv[1]
PROV = sys.argv[2]
APP = sys.argv[3]
MAPPA = sys.argv[4]
OUT = sys.argv[5]

# nomi di comune che sono anche parole ricorrenti nelle descrizioni tecniche
ESCLUSI = {
    "nuova", "nuovo", "ponte", "porto", "lotto", "nodo", "opere", "opera",
    "monte", "monti", "marina", "fiume", "bosco", "bella", "bagni", "cave",
    "certosa", "palazzo", "castello", "torre", "villa", "borgo", "campo",
    "campi", "valle", "colle", "rocca", "isola", "isole", "lago", "mare",
    "sotto", "sopra", "grande", "piano", "prato", "serra", "stazione",
    "terme", "pianura", "riviera", "collina", "vetta", "gallo", "corso",
    "muro", "ripa", "arco", "rete", "centro", "porta", "porte", "molo",
    "capo", "costa", "punta", "cima", "cornate", "scalo", "bivio", "fermata",
    "linea", "lotti", "tratta", "fase", "nord", "sud", "est", "ovest",
    "centrale", "capolinea", "vado", "spina", "roccia", "penna", "arena",
    "vetralla", "sale", "atri", "zone", "salto", "ferro", "argine",
    "bene", "verde", "pace", "piane", "quarto", "quinto", "sesto", "ora",
    "vigna", "livo", "sale marasino", "canale", "piedimonte", "acqua",
    "massa", "novella", "moretta", "sassa", "roccella", "trasporto",
    "merci", "nuove", "dorsale", "storico", "civile", "veloce", "media",
    # omonimie fra comuni e toponimi ferroviari: Genova Terralba non e'
    # Terralba (OR), Trieste Campo Marzio non e' Marzio (VA), il ponte sul
    # Brenta e' il fiume, Porta Romana e' una stazione
    "terralba", "marzio", "castelli", "brenta", "romana", "romani",
}

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


def senza_accenti(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm(s):
    """Chiave di confronto: minuscola, senza accenti, senza punteggiatura."""
    return re.sub(r"[^a-z0-9 ]+", " ", senza_accenti(s).lower()).strip()


def testo_confronto(s):
    """Come norm, ma conserva le maiuscole per riconoscere i nomi propri.

    La punteggiatura diventa spazio mantenendo le posizioni, cosi' che indici
    sul testo minuscolo e su questo restino allineati.
    """
    return re.sub(r"[^A-Za-z0-9 ]", " ", senza_accenti(s))


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
    # dal piu' lungo al piu' corto: "reggio calabria" prima di "reggio"
    ordinati = sorted(gaz, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in ordinati) + r")\b")

    app = json.load(open(APP))
    attrib, senza = {}, 0
    for p in app["progetti"]:
        originale = testo_confronto(p.get("n") or "")
        testo = originale.lower()
        trovati, usati = [], []
        for m in pattern.finditer(testo):
            nome = m.group(1)
            if any(a <= m.start() and m.end() <= b for a, b in usati):
                continue
            # deve essere un nome proprio nel testo di partenza
            if not originale[m.start()].isupper():
                continue
            usati.append((m.start(), m.end()))
            r = gaz[nome]
            if r not in trovati:
                trovati.append(r)
        if trovati:
            attrib[p["c"]] = trovati
        else:
            senza += 1
    app["regioni"] = {r: reg_nome[r] for r in sorted(reg_nome)}
    app["attribuzione_regionale"] = attrib
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
