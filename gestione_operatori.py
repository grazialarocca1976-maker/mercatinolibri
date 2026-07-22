"""
Gestione operatori (utenti) del gestionale Mercatino Libri Marconi.

L'amministratore (password master) puo' creare, elencare ed eliminare
operatori, ciascuno con il proprio username e password.
Le password vengono salvate come hash (SHA-256 + salt) su Supabase
nella tabella `operatori`.

Per creare la tabella su Supabase eseguire questo SQL nell'SQL Editor:

CREATE TABLE IF NOT EXISTS public.operatori (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    salt text NOT NULL,
    ruolo text NOT NULL DEFAULT 'operatore',
    creato_il timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.operatori ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anon full access operatori" ON public.operatori
    FOR ALL TO anon USING (true) WITH CHECK (true);
"""

import hashlib
import os
import requests
import tomllib
from pathlib import Path

# Legge le credenziali da secrets.toml
_secrets_path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
if _secrets_path.exists():
    with open(_secrets_path, "rb") as _f:
        _secrets = tomllib.load(_f)
    PROJECT_ID = _secrets["supabase"]["project_id"]
    CHIAVE_SUPABASE = _secrets["supabase"]["api_key"]
else:
    PROJECT_ID = os.environ.get("SUPABASE_PROJECT_ID", "")
    CHIAVE_SUPABASE = os.environ.get("SUPABASE_API_KEY", "")

URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
}

try:
    import streamlit as st
    PASSWORD_MASTER = st.secrets.get("password_master", "Marconi2026")
except Exception:
    PASSWORD_MASTER = "Marconi2026"


def _hash_password(password, salt=None):
    """Restituisce (hash_hex, salt_hex) usando SHA-256 + salt casuale."""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return digest, salt


def verifica_password(password, password_hash, salt):
    digest, _ = _hash_password(password, salt)
    return digest == password_hash


def crea_operatore(username, password, ruolo="operatore"):
    """Crea un nuovo operatore. Ritorna (ok, messaggio)."""
    username = (username or "").strip()
    password = password or ""
    if not username:
        return False, "Lo username non puo' essere vuoto."
    if len(password) < 4:
        return False, "La password deve contenere almeno 4 caratteri."

    # Controlla duplicati
    check = requests.get(
        f"{URL_REST}/operatori?username=eq.{username}",
        headers=HEADERS,
    )
    if check.status_code == 200 and check.json():
        return False, f"Lo username '{username}' esiste gia'."

    password_hash, salt = _hash_password(password)
    payload = {
        "username": username,
        "password_hash": password_hash,
        "salt": salt,
        "ruolo": ruolo,
    }
    res = requests.post(f"{URL_REST}/operatori", headers=HEADERS, json=payload)
    if res.status_code in (200, 201):
        return True, f"Operatore '{username}' creato con successo."
    return False, f"Errore creazione ({res.status_code}): {res.text}"


def elimina_operatore(username):
    """Elimina un operatore per username. Ritorna (ok, messaggio)."""
    username = (username or "").strip()
    if username.lower() == "admin":
        return False, "Non puoi eliminare l'account admin master."
    res = requests.delete(
        f"{URL_REST}/operatori?username=eq.{username}",
        headers=HEADERS,
    )
    if res.status_code in (200, 204):
        return True, f"Operatore '{username}' eliminato."
    return False, f"Errore eliminazione ({res.status_code}): {res.text}"


def cambia_ruolo(username, nuovo_ruolo):
    """Modifica il ruolo di un operatore esistente. Ritorna (ok, messaggio)."""
    username = (username or "").strip()
    nuovo_ruolo = (nuovo_ruolo or "").strip().lower()
    if not username:
        return False, "Username non valido."
    if nuovo_ruolo not in ("operatore", "admin"):
        return False, "Ruolo non valido (usa 'operatore' o 'admin')."
    if username.lower() == "admin" and nuovo_ruolo != "admin":
        return False, "Non puoi abbassare il ruolo dell'admin master."
    res = requests.patch(
        f"{URL_REST}/operatori?username=eq.{username}",
        headers=HEADERS,
        json={"ruolo": nuovo_ruolo},
    )
    if res.status_code < 400:
        return True, f"Ruolo di '{username}' aggiornato a '{nuovo_ruolo}'."
    return False, f"Errore aggiornamento ruolo ({res.status_code}): {res.text}"


def lista_operatori():
    """Ritorna la lista di operatori (senza dati sensibili)."""
    res = requests.get(
        f"{URL_REST}/operatori?select=username,ruolo,creato_il&order=username.asc",
        headers=HEADERS,
    )
    if res.status_code == 200:
        return res.json()
    return []


def autentica(username, password):
    """
    Verifica le credenziali.
    Ritorna True se valido (incluso admin master hardcoded), False altrimenti.
    """
    username = (username or "").strip()
    password = password or ""

    # Admin master di fallback (sempre disponibile)
    if username == "admin" and password == PASSWORD_MASTER:
        return True

    res = requests.get(
        f"{URL_REST}/operatori?username=eq.{username}&select=password_hash,salt",
        headers=HEADERS,
    )
    if res.status_code == 200:
        dati = res.json()
        if dati:
            row = dati[0]
            return verifica_password(password, row.get("password_hash"), row.get("salt"))
    return False