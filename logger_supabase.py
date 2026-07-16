"""Logger centralizzato su Supabase.

Gli errori vengono salvati nella tabella `log_errori` (visibile online),
invece di scrivere file locali sui PC degli utenti.
"""

import requests

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def log_errore(tipo="generico", messaggio="", dettaglio=None, operatore=None, pagina=None):
    """Salva un errore nella tabella log_errori su Supabase.

    Non solleva mai eccezioni: in caso di problemi di rete, fallisce silenziosamente
    (l'errore viene comunque stampato in console lato server per debug).
    """
    try:
        payload = {
            "tipo": str(tipo)[:50],
            "messaggio": str(messaggio)[:500],
            "dettaglio": str(dettaglio)[:2000] if dettaglio is not None else None,
            "operatore": str(operatore)[:100] if operatore else None,
            "pagina": str(pagina)[:100] if pagina else None,
        }
        requests.post(f"{URL_REST}/log_errori", headers=HEADERS, json=payload, timeout=10)
    except Exception as e:
        # Fallback minimo in console (lato server), mai su file utente
        print(f"[LOG SUPABASE FALLITO] {tipo}: {messaggio} -> {e}")


def leggi_log_errori(limite=200):
    """Restituisce l'elenco degli errori piu' recenti (piu' recenti prima)."""
    try:
        r = requests.get(
            f"{URL_REST}/log_errori?select=*&order=creato_il.desc&limit={limite}",
            headers=HEADERS,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []