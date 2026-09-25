"""Riconoscimento dei nomi di luogo nelle descrizioni degli interventi.

I Contratti di Programma non hanno un campo territoriale: l'unico appiglio e'
il nome dell'intervento. Qui stanno le regole di lettura condivise fra
l'attribuzione regionale (geo.py) e quella comunale (comuni.py), perche' le due
devono leggere lo stesso testo allo stesso modo.
"""
import re, unicodedata

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


# comuni omonimi di toponimi ferroviari che non sono quel comune: il Terzo
# Valico non e' Terzo (AL), la stazione di Cervaro sulla Napoli-Bari non e'
# Cervaro (FR). A livello regionale non davano fastidio, a livello comunale si'.
ESCLUSI_COMUNI = ESCLUSI | {"terzo", "cervaro"}

# stazioni, frazioni e aeroporti che i CdP nominano e che non sono comuni:
# ciascuno riportato al comune che lo ospita, verificato uno per uno
MANUALI_COMUNI = {
    "passo corese": ("Fara in Sabina", "RI"),
    "vicofertile": ("Parma", "PR"),
    "fornovo": ("Fornovo di Taro", "PR"),
    "giampilieri": ("Messina", "ME"),
    "fiumefreddo": ("Fiumefreddo di Sicilia", "CT"),
    "mestre": ("Venezia", "VE"),
    "brignole": ("Genova", "GE"),
    "voltri": ("Genova", "GE"),
    "tiburtina": ("Roma", "RM"),
    "santa maria novella": ("Firenze", "FI"),
    "fontanarossa": ("Catania", "CT"),
    "campo marzio": ("Trieste", "TS"),
    "romagnano": ("Romagnano al Monte", "SA"),
    # la stazione di Malpensa Terminal 1 sta a Ferno; il Terminal 2 sconfina
    # in Somma Lombardo, ma i tre interventi del corpus parlano dello scalo
    "malpensa": ("Ferno", "VA"),
}


def compila(nomi):
    """Espressione che cerca i nomi dal piu' lungo al piu' corto.

    L'ordine conta: senza, "Reggio" mangerebbe "Reggio Calabria".
    """
    ordinati = sorted(nomi, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in ordinati) + r")\b")


def trova(descrizione, pattern):
    """Nomi di luogo citati, nell'ordine, senza sovrapposizioni.

    Il nome vale solo se nel testo di partenza ha l'iniziale maiuscola, cioe'
    se e' usato come nome proprio: senza questo vincolo "trasporto di massa"
    diventerebbe la citta' di Massa.
    """
    originale = testo_confronto(descrizione or "")
    testo = originale.lower()
    usati = []
    for m in pattern.finditer(testo):
        if any(a <= m.start() and m.end() <= b for a, b in usati):
            continue
        if not originale[m.start()].isupper():
            continue
        usati.append((m.start(), m.end()))
        yield m.group(1)


# Alta velocita' e linea storica fra le stesse citta' hanno gli stessi capi:
# "Bologna - Firenze AV/AC" e la Direttissima, "Milano-Bologna AV/AC" e la
# storica per Lodi e Piacenza. Ne' il nome ne' la geometria le distinguono (le
# due corrono parallele e attraversano gli stessi comuni), e i due registri
# sbagliavano nello stesso modo: "Potenziamento linea Bologna-Prato" risultava
# confermato sull'AV da RFI e da OSM insieme. Due fonti che condividono la
# stessa ambiguita' non sono indipendenti. L'unico appiglio e' il testo
# dell'intervento: una linea AV vale solo se l'intervento dice di esserlo.
_AV = re.compile(r"\b(av|ac|avac|av ac|alta velocita|alta capacita)\b")


def linea_av(nome, codice=""):
    """La linea e' una linea AV/AC: dal nome, o dal codice RFI (A001, F023AV)."""
    if re.match(r"^A\d{3}$", codice or "") or (codice or "").endswith("AV"):
        return True
    return bool(_AV.search(norm(nome)))


def cita_av(testo):
    """La descrizione dell'intervento parla di alta velocita' o alta capacita'."""
    return bool(_AV.search(norm(testo)))


def declassa(conf):
    """Un livello in meno: alta diventa media, media diventa bassa."""
    return {"alta": "media", "media": "bassa"}.get(conf, conf)
