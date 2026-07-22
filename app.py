"""Main app: Gestionale Mercatino dei Libri Usati - Marconi Verona."""
import streamlit as st
import pandas as pd
import requests
import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from ricevute_condivise import inserisci_intestazione_marconi, inserisci_anagrafica_cliente, list_receipts, build_public_storage_url
from macro_aree import mostra_selector_macro_aree
from pagine_home import mostra_home
from pagine_archivio import mostra_archivio

st.set_page_config(page_title="Mercatino Libri Usati", layout="wide", initial_sidebar_state="expanded")

try:
    st.set_option("client.caching", False)
    st.set_option("runner.fastReruns", True)
except Exception:
    pass

if "sidebar_aperta" not in st.session_state:
    st.session_state["sidebar_aperta"] = False

# --- STILE GRAFICO ---
st.markdown("""
<style>
    :root {
        --libro-marrone: #6b4423;
        --libro-verde: #2e7d32;
        --libro-blu: #1565c0;
        --libro-rosso: #b33939;
    }
    .stApp {
        background-color: #fcfbf7;
        background-image:
            linear-gradient(rgba(253, 251, 247, 0.90), rgba(253, 251, 247, 0.90)),
            url('https://images.unsplash.com/photo-1523986371872-9d3be1d93d92?auto=format&fit=crop&q=80&w=1600');
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    h1, h2, h3 {
        color: var(--libro-marrone) !important;
        font-family: 'Georgia', serif;
    }
    .header-operatore {
        background: var(--libro-marrone);
        color: #fff;
        padding: 10px 18px;
        border-radius: 10px;
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left;
        padding: 18px 20px !important;
        margin-bottom: 10px !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        border: 3px solid #8d6e63 !important;
        background: linear-gradient(135deg, #fbf6ec, #f5ebe0) !important;
        color: #4e342e !important;
        transition: all 0.15s ease;
        box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: linear-gradient(135deg, #f0e6d2, #e8d5b7) !important;
        border-color: #5d4037 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        transform: translateY(-1px);
    }
    .st-key-btn_apri_menu {
        position: fixed;
        top: 12px;
        left: 12px;
        z-index: 999999;
    }
    .st-key-btn_apri_menu button {
        min-width: 112px;
        height: 42px;
        padding: 0 16px;
        border-radius: 10px;
        border: 2px solid #c9b79c;
        background: var(--libro-marrone);
        color: #fff;
        box-shadow: 0 2px 8px rgba(0,0,0,0.22);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0;
    }
    .st-key-btn_apri_menu button:hover {
        background: #5a371b;
        border-color: #5a371b;
        color: #fff;
    }
    .st-key-btn_chiudi_menu button {
        margin-bottom: 12px;
        justify-content: center !important;
        text-align: center !important;
        background: var(--libro-marrone) !important;
        color: #fff !important;
        border-color: var(--libro-marrone) !important;
    }
    section[data-testid="stSidebar"] button[aria-label*="sidebar" i],
    section[data-testid="stSidebar"] button[title*="sidebar" i] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

if not st.session_state["sidebar_aperta"]:
    st.markdown("""
    <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if "logged_in" not in st.session_state:
    if "session" in st.query_params:
        st.session_state["logged_in"] = True
        st.session_state["operatore"] = st.query_params["session"]
        st.session_state["pagina"] = "__HOME__"
    else:
        st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("## Accesso Operatore Marconi Verona")
    st.markdown("Inserisci le tue credenziali per accedere al sistema gestionale.")
    username = st.text_input("Nome Utente", key="login_user", value=st.session_state.get("login_user_tmp", "")).strip()
    password = st.text_input("Password", type="password", key="login_pass").strip()
    rimani = st.checkbox("Rimani collegato (salva sessione attiva sull'URL)", value=True, key="rimani_collegato")
    if st.button("Accedi al Sistema", use_container_width=True):
        import gestione_operatori
        if gestione_operatori.autentica(username, password):
            st.session_state["logged_in"] = True
            st.session_state["operatore"] = username
            st.session_state["login_user_tmp"] = username
            if rimani:
                st.query_params["session"] = username
            st.session_state["pagina"] = "__HOME__"
            st.session_state["flusso_iniziale"] = None
            
            # Verifica se l'operatore ha ruolo admin
            if username == "admin":
                st.session_state["admin_ok"] = True
            else:
                # Controlla il ruolo dal database
                try:
                    r = requests.get(
                        f"https://{st.secrets['supabase']['project_id']}.supabase.co/rest/v1/operatori?username=eq.{username}&select=ruolo",
                        headers={
                            "apikey": st.secrets["supabase"]["api_key"],
                            "Authorization": f"Bearer {st.secrets['supabase']['api_key']}"
                        }
                    )
                    if r.status_code == 200 and r.json():
                        ruolo = r.json()[0].get("ruolo", "operatore")
                        if ruolo == "admin":
                            st.session_state["admin_ok"] = True
                except Exception:
                    pass
            
            st.success("Accesso consentito!")
            st.rerun()
        else:
            st.error("Credenziali non corrette!")
            import logger_supabase
            logger_supabase.log_errore(
                tipo="login_fallito",
                messaggio="Tentativo di login fallito",
                dettaglio=f"Utente: '{username}'",
                operatore=username,
                pagina="Login",
            )
    st.stop()

if not st.session_state["sidebar_aperta"]:
    if st.button("MENU", key="btn_apri_menu", width="content"):
        st.session_state["sidebar_aperta"] = True
        st.rerun()

st.title("Gestionale Mercatino dei Libri Usati")

operatore_corrente = st.session_state.get("operatore", "--")
st.markdown(
    f'<div class="header-operatore">Operatore connesso: <b>{operatore_corrente}</b></div>',
    unsafe_allow_html=True,
)

# --- CONFIGURAZIONE SUPABASE (da st.secrets) ---
PROJECT_ID = st.secrets["supabase"]["project_id"]
CHIAVE_SUPABASE = st.secrets["supabase"]["api_key"]
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json"
}
st.session_state["HEADERS"] = HEADERS
st.session_state["URL_REST"] = URL_REST

PASSWORD_AMMINISTRATORE = st.secrets.get("password_admin", "Marconi2026")

# --- SIDEBAR: NAVIGAZIONE ---
st.sidebar.markdown("---")
st.sidebar.caption("Mercatino Libri Usati · Marconi Verona")

# Pulsanti navigazione principali
if st.sidebar.button("🏠 Home", key="nav_home", use_container_width=True):
    st.session_state["pagina"] = "__HOME__"
    st.rerun()
if st.sidebar.button("💰 Vendita Rapida", key="nav_vendita", use_container_width=True):
    st.session_state["flusso_iniziale"] = "vendita"
    st.session_state["pagina"] = "Cassa e Vendita Rapida"
    st.rerun()
if st.sidebar.button("📦 Ritiro Libri", key="nav_ritiro", use_container_width=True):
    st.session_state["flusso_iniziale"] = "ritiro"
    st.session_state["pagina"] = "Ritiro Libri (Venditori)"
    st.rerun()
if st.sidebar.button("📋 Menu Operazioni", key="nav_menu", use_container_width=True):
    st.session_state["pagina"] = "Menu Operazioni"
    st.rerun()
if st.sidebar.button("🧾 Conto Clienti", key="nav_conto_clienti", use_container_width=True):
    st.session_state["pagina"] = "Conto Clienti"
    st.rerun()

st.sidebar.markdown("---")

# --- LIBRI IN MIO POSSESSO (caricamento lazy) ---
with st.sidebar.expander("📚 Libri in mio possesso", expanded=False):
    if st.button("Carica elenco", key="sidebar_carica_possesso", use_container_width=True):
        with st.spinner("Caricamento..."):
            try:
                r = requests.get(
                    f"{URL_REST}/copie_libri?stato=neq.venduto&order=id_libro.desc&limit=500",
                    headers=HEADERS, timeout=30
                )
                copie = r.json() if r.status_code == 200 else []
                if copie:
                    r2 = requests.get(
                        f"{URL_REST}/catalogo_libri?select=isbn,titolo,autore,prezzo_copertina",
                        headers=HEADERS, timeout=30
                    )
                    cat = r2.json() if r2.status_code == 200 else []
                    df_p = pd.merge(pd.DataFrame(copie), pd.DataFrame(cat), on="isbn", how="left")
                    df_p = df_p[['id_libro', 'isbn', 'titolo', 'autore', 'prezzo_copertina', 'id_venditore']]
                    df_p.columns = ['Cod.', 'ISBN', 'Titolo', 'Autore', 'Prezzo', 'ID Vend.']
                    st.dataframe(df_p, use_container_width=True, hide_index=True)
                    st.caption(f"Totale: {len(df_p)} libri")
                else:
                    st.info("Nessun libro in possesso.")
            except Exception as e:
                st.error(f"Errore: {e}")

# --- MACRO-AREE ---
with st.sidebar.expander("📐 Macro-aree (Classi 1a)", expanded=False):
    mostra_selector_macro_aree("1", URL_REST, HEADERS)
with st.sidebar.expander("📐 Macro-aree (Classi 3a)", expanded=False):
    mostra_selector_macro_aree("3", URL_REST, HEADERS)

# --- LOGOUT ---
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Esci (Logout)", key="sidebar_logout", use_container_width=True):
    for k in ["logged_in", "operatore", "pagina", "flusso_iniziale", "sidebar_aperta"]:
        if k in st.session_state:
            del st.session_state[k]
    st.query_params.clear()
    st.rerun()

# --- ROUTING PAGINE ---
pagina = st.session_state.get("pagina", "__HOME__")

if pagina == "__HOME__":
    mostra_home()

elif pagina == "Cassa e Vendita Rapida":
    import cassa
    cassa.mostra_pagina()

elif pagina == "Ritiro Libri (Venditori)":
    import ritiro
    ritiro.mostra_pagina()

elif pagina == "Menu Operazioni":
    st.markdown("## Menu Operazioni")
    st.markdown("Seleziona una delle seguenti operazioni:")
    col_a, col_b = st.columns(2)
    # Controllo admin
    admin_ok = st.session_state.get("admin_ok", False)
    if not admin_ok:
        admin_pwd = st.secrets.get("password_admin", "")
        if admin_pwd:
            with st.expander("🔐 Accesso Admin", expanded=False):
                pwd_input = st.text_input("Password Admin", type="password", key="admin_pwd_input")
                if st.button("Conferma", key="admin_btn"):
                    if pwd_input == admin_pwd:
                        st.session_state["admin_ok"] = True
                        st.rerun()
                    else:
                        st.error("Password errata")

    with col_a:
        if st.button("Archivio (Ricevute, Clienti, Ristampa)", key="menu_archivio", use_container_width=True):
            st.session_state["pagina"] = "Archivio"
            st.rerun()
        if st.button("🔍 Cerca Libro", key="menu_cerca", use_container_width=True):
            st.session_state["pagina"] = "Cerca Libro"
            st.rerun()
        if st.button("🏠 Torna alla Home", key="menu_home", use_container_width=True):
            st.session_state["pagina"] = "__HOME__"
            st.rerun()
    with col_b:
        if st.button("🧾 Conto Clienti", key="menu_conto_clienti", use_container_width=True):
            st.session_state["pagina"] = "Conto Clienti"
            st.rerun()
        if st.button("📋 Menu Operazioni", key="menu_menu_op", use_container_width=True):
            st.session_state["pagina"] = "Menu Operazioni"
            st.rerun()
    
    # --- SEZIONE ADMIN (solo se autenticato) ---
    if admin_ok:
        st.markdown("---")
        st.markdown("### 🔐 Pannello Amministratore")
        st.caption("Tutte le funzioni amministrative:")
        
        col_admin1, col_admin2, col_admin3 = st.columns(3)
        
        with col_admin1:
            if st.button("📁 Fascicoli", key="menu_admin_fascicoli", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 0
                st.rerun()
            if st.button("📥 Import CSV", key="menu_admin_csv", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 1
                st.rerun()
            if st.button("📅 Chiusura Fine Anno", key="menu_admin_fineanno", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 2
                st.rerun()
            if st.button("👥 Gestione Operatori", key="menu_admin_operatori", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 3
                st.rerun()
        
        with col_admin2:
            if st.button("🗑️ Cancellazione Utenti", key="menu_admin_utenti", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 4
                st.rerun()
            if st.button("💰 Conteggi Giornalieri", key="menu_admin_conteggi", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 5
                st.rerun()
            if st.button("💵 Progressivo Soldi", key="menu_admin_progressivo", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 6
                st.rerun()
            if st.button("📄 Restituzioni Libri", key="menu_admin_restituzioni", use_container_width=True):
                st.session_state["pagina"] = "Admin"
                st.session_state["admin_tab"] = 7
                st.rerun()
        
        with col_admin3:
            if st.button("📊 Gestione Conti", key="menu_admin_conti", use_container_width=True):
                st.session_state["pagina"] = "Gestione Conti"
                st.rerun()
            if st.button("📚 Catalogo Libri", key="menu_admin_catalogo", use_container_width=True):
                st.session_state["pagina"] = "Catalogo"
                st.rerun()
            if st.button("💰 Report / Bilancio", key="menu_admin_report", use_container_width=True):
                st.session_state["pagina"] = "Report"
                st.rerun()
            if st.button("👥 Gestione Operatori (Legacy)", key="menu_admin_op_legacy", use_container_width=True):
                st.session_state["pagina"] = "Gestione Operatori"
                st.rerun()

elif pagina == "Archivio":
    mostra_archivio(URL_REST, HEADERS)

elif pagina == "Conto Clienti":
    import gestione_conti
    gestione_conti.mostra_pagina()
    st.sidebar.markdown("---")
    if st.sidebar.button("🔙 Torna alla Home", key="conto_back_home", use_container_width=True):
        st.session_state["pagina"] = "__HOME__"
        st.rerun()

elif pagina == "Catalogo":
    if not st.session_state.get("admin_ok", False):
        st.error("Accesso negato. Solo admin.")
        st.stop()
    import catalogo
    catalogo.mostra_pagina_interna()

elif pagina == "Cerca Libro":
    import cerca_libro
    cerca_libro.mostra_pagina()

elif pagina == "Gestione Operatori":
    if not st.session_state.get("admin_ok", False):
        st.error("Accesso negato. Solo admin.")
        st.stop()
    import gestione_operatori
    st.markdown("## Gestione Operatori (Admin)")
    st.caption("Funzioni amministrative: creazione, modifica ed eliminazione operatori.")
    from gestione_operatori import lista_operatori, crea_operatore, elimina_operatore, cambia_ruolo
    st.markdown("### Elenco Operatori")
    operatori = lista_operatori()
    if operatori:
        for op in operatori:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"**{op['username']}** - Ruolo: {op.get('ruolo', 'operatore')}")
            with c2:
                if st.button(f"Elimina {op['username']}", key=f"del_{op['username']}"):
                    elimina_operatore(op['username'])
                    st.rerun()
            with c3:
                nuovo_ruolo = "admin" if op.get("ruolo") != "admin" else "operatore"
                if st.button(f"Rendi {nuovo_ruolo}", key=f"role_{op['username']}"):
                    cambia_ruolo(op['username'], nuovo_ruolo)
                    st.rerun()
    else:
        st.info("Nessun operatore trovato.")
    st.markdown("---")
    st.markdown("### Crea Nuovo Operatore")
    nuovo_user = st.text_input("Username", key="nuovo_op_user")
    nuovo_pass = st.text_input("Password", type="password", key="nuovo_op_pass")
    if st.button("Crea Operatore", use_container_width=True):
        if nuovo_user and nuovo_pass:
            crea_operatore(nuovo_user, nuovo_pass)
            st.success(f"Operatore '{nuovo_user}' creato!")
            st.rerun()
        else:
            st.warning("Inserisci username e password.")

elif pagina == "Admin":
    if not st.session_state.get("admin_ok", False):
        st.error("Accesso negato. Solo admin.")
        st.stop()
    from pagine_admin import mostra_admin
    mostra_admin(URL_REST, HEADERS)

elif pagina == "Report":
    if not st.session_state.get("admin_ok", False):
        st.error("Accesso negato. Solo admin.")
        st.stop()
    import report
    report.mostra_pagina()

else:
    st.warning(f"Pagina '{pagina}' non riconosciuta. Torno alla Home.")
    st.session_state["pagina"] = "__HOME__"
    st.rerun()
