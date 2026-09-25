"""Scarica dal Piano Commerciale di RFI i progetti che dichiarano il codice CdP.

Il Piano Commerciale e' pubblicato da RFI anche come servizi cartografici
ArcGIS interrogabili. Tre layer degli "Scenari infrastrutturali" (tratte di
progetto, localita' potenziate, localita' nuove) portano un campo
"Riferimento CdP-I" con i codici intervento del Contratto di Programma
(es. "0362A", "0099A,0099B,0279A"). E' il legame intervento-tracciato che i
contratti non danno, e qui e' scritto da RFI: non va dedotto.

Che cosa si tiene. Non si ripubblica il servizio: la sua scheda non indica una
licenza, e finche' non e' chiarita il progetto usa e cita questi dati ma non li
rimette in circolazione come file scaricabili. Si versiona solo un estratto:
i campi mostrati dal sito e la geometria gia' semplificata dal servizio stesso
(maxAllowableOffset), abbastanza per disegnarla alla scala della mappa.

Come per rete_osm.py, il passo richiede la rete e sta fuori da build_all.sh:
build_all.sh legge solo il file versionato.

Con un secondo argomento scarica anche la rete RFI completa (layer
TrattePC2026, circa 2.400 tratte), che ha il codice di linea commerciale: e'
lo stesso codice dell'Allegato 3 dei contratti Servizi con la lettera
cambiata (C001 -> K001, F011 -> J011, N001 -> R001), e da' finalmente una
geometria ufficiale al registro delle linee. Vedi rete_rfi.py.

Uso:
  python3 piano_commerciale.py ../data/piano-commerciale-2026.json \
          [../data/rete-rfi.geojson]
"""
import datetime
import json
import sys
import urllib.parse
import urllib.request

SERVIZIO = ("https://services3.arcgis.com/GS5pg5GvYXCMCEen/arcgis/rest/services/"
            "Scenari_Infrastrutturali_PC2026/FeatureServer")
RETE = ("https://services3.arcgis.com/GS5pg5GvYXCMCEen/arcgis/rest/services/"
        "TrattePC2026/FeatureServer")
# gradi: circa 55 m in latitudine, ben sotto l'unita' della mappa (circa 1 km)
SEMPLIFICA = 0.0005
CAMPI_RETE = ["OBJECTID", "CODTRATTA_BDL", "TRATTA_BDL", "CODLINEA_BDL", "LINEA_BDL",
              "CODLINEA_COMM", "LINEA_COMM", "LINEA_AV", "RETE_EUROPEA",
              "TIPO_RETE_TEN_T", "TIPO_CORE_CENTRALE", "PESO_ASSIALE", "SCT",
              "LENGTH_PIR", "EDIZIONE_PIR"]

CAMPI_COMUNI = ["OBJECTID", "CODICE_PROG_LIN", "PROGETTO", "CDP",
                "DESC_INTERVENTO_CDP", "ANNO_ATT_PC", "ANNO_COMPLETAMENTO"]
LAYER = {
    "tratte": (0, CAMPI_COMUNI + [
        "ANNO_ATT_PI", "DESCRIZIONE_TRATTE", "NUOVA_LINEA",
        "RADDOPPIO_QUADRUPLICAMENTO", "RIAPERTURA_LINEA", "ELETTRIFICAZIONE",
        "UPGRADE_TECNOLOGICO", "UPGRADE_PRESTAZIONALE", "VELOCIZZAZIONE",
        "LP", "MERCI", "TPL"]),
    "localita_potenziate": (1, CAMPI_COMUNI + [
        "DENOMINAZIONE", "REGIONE", "FINANZIATO", "PRG", "NUOVO_IMPIANTO",
        "NUOVO_TERMINAL", "POTENZIAMENTO_TERMINAL", "VELOCIZZAZIONE",
        "UPGRADE_TECNOLOGICO", "UPGRADE_PRESTAZIONALE"]),
    "localita_nuove": (2, CAMPI_COMUNI + [
        "DENOMINAZIONE", "REGIONE", "FINANZIATO", "STATO", "ATTIVATA",
        "NUOVA_DELOC", "STAZIONE_FERMATA"]),
}


def leggi(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        j = json.load(r)
    # un campo inesistente non fa fallire la richiesta: il servizio risponde
    # con un oggetto "error" e zero righe. Al primo tentativo il layer delle
    # localita' nuove risultava vuoto per questo, senza nessun avviso
    if "error" in j:
        raise RuntimeError("%s: %s" % (url.split("?")[0], j["error"]))
    return j


def interroga(layer, campi, servizio=SERVIZIO, semplifica=SEMPLIFICA):
    """Tutte le righe del layer, a pagine: il servizio ne restituisce al massimo 2000."""
    # i campi cambiano fra un layer e l'altro e fra un'edizione e l'altra
    # (DESC_INTERVENTO_CDP non c'e' nelle localita' nuove): si chiedono solo
    # quelli che il layer ha, e si dice quali mancano
    esistenti = {c["name"] for c in leggi("%s/%d?f=json" % (servizio, layer))["fields"]}
    mancanti = [c for c in campi if c not in esistenti]
    if mancanti:
        print("  layer %d senza i campi %s" % (layer, ", ".join(mancanti)))
    campi = [c for c in campi if c in esistenti]
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": "1=1", "outFields": ",".join(campi), "outSR": 4326,
            "f": "geojson", "resultOffset": offset, "resultRecordCount": 1000,
            "maxAllowableOffset": semplifica, "geometryPrecision": 5})
        fs = leggi("%s/%d/query?%s" % (servizio, layer, q)).get("features", [])
        out.extend(fs)
        if len(fs) < 1000:
            return out
        offset += 1000


def pulisci(v):
    if isinstance(v, str):
        v = " ".join(v.split())
        return v or None
    return v


def main():
    dest = sys.argv[1]
    dati = {"fonte": "RFI, Piano Commerciale 2026, Scenari infrastrutturali "
                     "(servizio ArcGIS pubblico)",
            "servizio": SERVIZIO,
            "scaricato": datetime.date.today().isoformat(),
            "licenza": "non indicata nella scheda del servizio",
            "layer": {}}
    for nome, (lid, campi) in LAYER.items():
        fs = interroga(lid, campi)
        righe = []
        for f in fs:
            p = {k: pulisci(v) for k, v in f["properties"].items()}
            # un campo testuale a elenco: "0099A,0099B" diventa una lista
            p["CDP"] = [x.strip() for x in (p.get("CDP") or "").replace(";", ",").split(",")
                        if x.strip()]
            righe.append({"p": p, "g": f.get("geometry")})
        dati["layer"][nome] = righe
        print("%-20s %4d elementi, %4d con codice CdP"
              % (nome, len(righe), sum(1 for r in righe if r["p"]["CDP"])))
    json.dump(dati, open(dest, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))

    if len(sys.argv) > 2:
        # la rete e' il fondo della mappa: basta una semplificazione piu' fine
        # di quella dei progetti, perche' qui si ingrandisce fino al nodo
        fs = interroga(0, CAMPI_RETE, RETE, 0.0002)
        for f in fs:
            f["properties"] = {k: pulisci(v) for k, v in f["properties"].items()}
        gj = {"type": "FeatureCollection",
              "fonte": "RFI, rete ferroviaria (TrattePC2026, servizio ArcGIS pubblico)",
              "servizio": RETE, "scaricato": dati["scaricato"], "features": fs}
        json.dump(gj, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False,
                  separators=(",", ":"))
        print("%-20s %4d tratte" % ("rete RFI", len(fs)))


if __name__ == "__main__":
    main()
