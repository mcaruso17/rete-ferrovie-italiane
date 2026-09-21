"""Rimpiazza il blocco dati incorporato nella piattaforma.

La pagina e' un file unico: i dati stanno dentro uno <script type="application/json">
cosi' il sito funziona anche aperto da disco, senza server. Uso:
  python3 inject_data.py ../piattaforma/index.html ../data/cdp-rfi-app.json
"""
import sys, re, json, os

pagina, dati = sys.argv[1], sys.argv[2]
html = open(pagina).read()
blob = json.dumps(json.load(open(dati)), ensure_ascii=False, separators=(",", ":"))
nuovo, n = re.subn(r'(<script type="application/json" id="dati">).*?(</script>)',
                   lambda m: m.group(1) + blob + m.group(2), html, flags=re.S)
if n != 1:
    sys.exit("blocco dati non trovato in %s (trovati %d)" % (pagina, n))
open(pagina, "w").write(nuovo)
print("%s aggiornato: %d KB di dati" % (os.path.basename(pagina), len(blob) // 1024))
