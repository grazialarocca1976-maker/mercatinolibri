"""
Esportazione del resoconto di fine anno in un file separato (JSON).

Permette di scaricare l'intero stato del gestionale (clienti, copie, catalogo,
vendite, liquidazioni e totali di cassa) prima di azzerare il database,
cosi' da conservare lo storico e tenere il DB pulito e ordinato.
"""

import json
import datetime
import requests

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
}


def _get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def genera_resoconto_fine_anno():
    """
    Raccoglie tutti i dati rilevanti e restituisce una tupla:
    (testo_json, nome_file)
    """
    clienti = _get(f"{URL_REST}/clienti?select=*")
    copie = _get(f"{URL_REST}/copie_libri?select=*")
    catalogo = _get(f"{URL_REST}/catalogo_libri?select=*")

    # Calcoli riepilogo
    venduti = [c for c in copie if c.get("stato") == "venduto"]
    tot_contanti = 0.0
    tot_bancomat = 0.0
    for c in venduti:
        prezzo_base = float(c.get("prezzo_inserito_mano", 0.0) or 0.0)
        if prezzo_base == 0.0:
            # recupera prezzo copertina dal catalogo
            isbn = c.get("isbn")
            pc = next((x.get("prezzo_copertina", 0.0) for x in catalogo if x.get("isbn") == isbn), 0.0)
            prezzo_base = float(pc or 0.0)
        prezzo_vendita = (prezzo_base / 2) + 0.50
        metodo = (c.get("metodo_pagamento") or "").lower()
        if metodo == "contanti":
            tot_contanti += prezzo_vendita
        elif "bancomat" in metodo:
            tot_bancomat += prezzo_vendita

    # Liquidazioni per cliente (solo chi ha venduto)
    liquidazioni = []
    for cl in clienti:
        libri_cl = [c for c in venduti if c.get("id_venditore") == cl.get("id")]
        if libri_cl:
            da_liquidare = 0.0
            dettaglio = []
            for c in libri_cl:
                prezzo_base = float(c.get("prezzo_inserito_mano", 0.0) or 0.0)
                if prezzo_base == 0.0:
                    isbn = c.get("isbn")
                    pc = next((x.get("prezzo_copertina", 0.0) for x in catalogo if x.get("isbn") == isbn), 0.0)
                    prezzo_base = float(pc or 0.0)
                liq = (prezzo_base / 2) - 0.50
                da_liquidare += liq
                dettaglio.append({
                    "id_libro": c.get("id_libro"),
                    "isbn": c.get("isbn"),
                    "prezzo_liquidazione": round(liq, 2),
                    "data_vendita": c.get("data_vendita"),
                })
            liquidazioni.append({
                "id_cliente": cl.get("id"),
                "codice_personale": cl.get("codice_personale"),
                "nome": cl.get("nome"),
                "cognome": cl.get("cognome"),
                "totale_da_liquidare": round(da_liquidare, 2),
                "libri": dettaglio,
            })

    resoconto = {
        "metadata": {
            "generato_il": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "gestionale": "Mercatino Libri Marconi Verona",
            "tipo": "Resoconto Fine Anno",
        },
        "riepilogo_cassa": {
            "totale_contanti": round(tot_contanti, 2),
            "totale_bancomat": round(tot_bancomat, 2),
            "totale_generale": round(tot_contanti + tot_bancomat, 2),
            "n_libri_venduti": len(venduti),
            "n_clienti_totali": len(clienti),
        },
        "clienti": clienti,
        "copie_libri": copie,
        "catalogo_libri": catalogo,
        "liquidazioni_per_cliente": liquidazioni,
    }

    testo_json = json.dumps(resoconto, indent=2, ensure_ascii=False)
    nome_file = f"resoconto_fine_anno_{datetime.date.today().strftime('%Y_%m_%d')}.json"
    return testo_json, nome_file