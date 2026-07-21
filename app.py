import streamlit as st
import importlib
import pandas as pd
import requests
import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Importiamo la grafica centralizzata
from ricevute_condivise import inserisci_intestazione_marconi, inserisci_anagrafica_cliente, list_receipts, build_public_storage_url

st.set_page_config(page_title="Mercatino Libri Usati", layout="wide", initial_sidebar_state="expanded")

# Disattiva la cache-busting UI di Streamlit (popup "Clear cache") e accelera i rerun
try:
    st.set_option("client.caching", False)
    st.set_option("runner.fastReruns", True)
except Exception:
    pass

if "sidebar_aperta" not in st.session_state:
    st.session_state["sidebar_aperta"] = False

# --- STILE GRAFICO (sfondo bianco, bottoni con icone) ---
st.markdown("""
<style>
    :root {
        --libro-marrone: #6b4423;
        --libro-verde: #2e7d32;
        --libro-blu: #1565c0;
        --libro-rosso: #b33939;
    }
    /* Sfondo "pieno di libri": immagine ad alta risoluzione sfocata di libri con velo bianco/crema per una perfetta leggibilità */
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
    /* Header operatore in alto */
    .header-operatore {
        background: var(--libro-marrone);
        color: #fff;
        padding: 10px 18px;
        border-radius: 10px;
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 12px;
        box-shadow:0 2px 6px rgba(0,0,0,0.2);
    }
    /* Bottoni di navigazione laterali grandi, colori tenui */
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left;
        padding: 14px 16px;
        margin-bottom: 8px;
        font-size: 15px;
        font-weight: 600;
        border-radius: 10px;
        border: 2px solid #c9b79c;
        background: #fbf6ec;
        color: #5d4037;
        transition: all 0.15s ease;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: #f0e6d2;
        border-color: var(--libro-marrone);
    }
    /* Bottone attivo (evidenziato) */
    section[data-testid="stSidebar"] .stButton > button[data-active="true"] {
        background: #efe0c8;
        color: #4e342e;
        border-color: var(--libro-marrone);
    }
    /* Bottoni HOME: colori tenui e facilmente identificabili */
    button[key="home_vendita"] {
        background: #d8f0e0; color: #1b5e20; border: 2px solid #81c784;
    }
    button[key="home_vendita"]:hover { background: #bce9cd; }
    button[key="home_ritiro"] {
        background: #d6e8fb; color: #0d47a1; border: 2px solid #64b5f6;
    }
    button[key="home_ritiro"]:hover { background: #bcdcf7; }
    button[key="home_altro"] {
        background: #fdeecb; color: #8d6e00; border: 2px solid #ffd54f;
    }
    button[key="home_altro"]:hover { background: #fbe3a8; }
    /* Pulsanti personalizzati per aprire/chiudere il menu laterale. */
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

# --- SISTEMA DI LOGIN OPERATORE ---
# Login persistente con auto-login basato su URL Query Parameters nativo (funziona sempre, anche al refresh!)
if "logged_in" not in st.session_state:
    if "session" in st.query_params:
        st.session_state["logged_in"] = True
        st.session_state["operatore"] = st.query_params["session"]
        st.session_state["pagina"] = "__HOME__"
    else:
        st.session_state["logged_in"] = False

# Gestione della visualizzazione della pagina di Login
if not st.session_state["logged_in"]:
    st.markdown("## 🔐 Accesso Operatore Marconi Verona")
    st.markdown("Inserisci le tue credenziali per accedere al sistema gestionale.")

    # Usa gli input con chiave fissa per non perdere il focus ad ogni rerun
    username = st.text_input("Nome Utente", key="login_user", value=st.session_state.get("login_user_tmp", "")).strip()
    password = st.text_input("Password", type="password", key="login_pass").strip()
    rimani = st.checkbox("🔒 Rimani collegato (salva sessione attiva sull'URL per non richiedere più il login)", value=True, key="rimani_collegato")

    if st.button("🔑 Accedi al Sistema", use_container_width=True):
        import gestione_operatori
        if gestione_operatori.autentica(username, password):
            st.session_state["logged_in"] = True
            st.session_state["operatore"] = username
            st.session_state["login_user_tmp"] = username
            # Se ha scelto di rimanere collegato, salviamo la sessione nei query_params URL del browser
            if rimani:
                st.query_params["session"] = username
            # All'accesso andiamo alla Home con i 3 bottoni
            st.session_state["pagina"] = "__HOME__"
            st.session_state["flusso_iniziale"] = None
            st.success("🔓 Accesso consentito!")
            st.rerun()
        else:
            st.error("❌ Credenziali non corrette!")
            # Log centralizzato su Supabase (visibile online, non sui PC utente)
            import logger_supabase
            logger_supabase.log_errore(
                tipo="login_fallito",
                messaggio="Tentativo di login fallito",
                dettaglio=f"Utente: '{username}'",
                operatore=username,
                pagina="Login",
            )
    st.stop() # Blocca l'esecuzione del resto dell'app se non si è loggati

if not st.session_state["sidebar_aperta"]:
    if st.button("☰ MENU", key="btn_apri_menu", width="content"):
        st.session_state["sidebar_aperta"] = True
        st.rerun()

st.title("📚 Gestionale Mercatino dei Libri Usati")

# Header operatore sempre visibile in alto
operatore_corrente = st.session_state.get("operatore", "—")
st.markdown(
    f'<div class="header-operatore">👤 Operatore connesso: <b>{operatore_corrente}</b></div>',
    unsafe_allow_html=True,
)

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json"
}
# ⬇️ INSERISCI QUESTE DUE RIGHE PROPRIO QUI! ⬇️
st.session_state["HEADERS"] = HEADERS
st.session_state["URL_REST"] = URL_REST


PASSWORD_AMMINISTRATORE = st.secrets.get("password_admin", "Marconi2026")

# Menu laterale con pulsanti grandi e leggibili (senza pallino) + icona per ciascuno
if st.sidebar.button("☰ Chiudi menu", key="btn_chiudi_menu", width="stretch"):
    st.session_state["sidebar_aperta"] = False
    st.rerun()

st.sidebar.markdown("### 🧭 Navigazione")

# Pulsante HOME: torna alla schermata con i 3 bottoni di scelta
if st.sidebar.button("🏠 HOME (scelta operazione)", use_container_width=True, key="nav_home"):
    st.session_state["pagina"] = "__HOME__"
    st.session_state["flusso_iniziale"] = None
    st.session_state["destinazione_dopo_cliente"] = None
    st.rerun()

# Voci del menu laterale: NON ripetiamo quelle già presenti nella Home
# (Registrazione Clienti, Ritiro, Cassa sono raggiungibili dai 3 bottoni Home).
# Qui mettiamo solo le funzioni "ALTRO" non coperte dalla Home.
voci_nav = [
    ("📒", "Gestione Conti Cliente"),
    ("🔍", "🔍 Cerca Libro"),
    ("📁", " Archivio"),
]

menu_options = [v[1] for v in voci_nav]

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "__HOME__"

for icona, opt in voci_nav:
    classe = ' data-active="true"' if st.session_state["pagina"] == opt else ""
    st.sidebar.markdown(
        f'<style>div[data-testid="stSidebar"] button[key="nav_{opt.replace(" ", "_")}"]{classe}</style>',
        unsafe_allow_html=True,
    )
    etichetta = f"{icona}  {opt.strip()}"
    if st.sidebar.button(etichetta, key=f"nav_{opt.replace(' ', '_')}", use_container_width=True):
        st.session_state["pagina"] = opt
        # Se l'utente usa il menu completo, il flusso iniziale diventa "altro"
        st.session_state["flusso_iniziale"] = "altro"

menu = st.session_state["pagina"]

# --- HOME: schermata principale con 3 bottoni (Vendita / Ritiro / Altro) ---
if menu == "__HOME__":
    st.markdown("## 🏠 Benvenuto nel Gestionale")
    st.markdown("Scegli l'operazione da eseguire:")
    hc1, hc2, hc3 = st.columns(3)
    with hc1:
        if st.button("🛒 VENDITA", use_container_width=True, key="home_vendita"):
            # Flusso guidato: prima registra/cerca cliente, poi vai in cassa
            st.session_state["flusso_iniziale"] = "vendita"
            st.session_state["pagina"] = "Registrazione Clienti"
            st.session_state["destinazione_dopo_cliente"] = "Cassa e Vendita Rapida"
            st.rerun()
    with hc2:
        if st.button("📥 RITIRO", use_container_width=True, key="home_ritiro"):
            # Flusso guidato: prima registra/cerca cliente, poi vai al ritiro
            st.session_state["flusso_iniziale"] = "ritiro"
            st.session_state["pagina"] = "Registrazione Clienti"
            st.session_state["destinazione_dopo_cliente"] = "Ritiro Libri (Venditori)"
            st.rerun()
    with hc3:
        if st.button("⚙️ ALTRO", use_container_width=True, key="home_altro"):
            st.session_state["flusso_iniziale"] = "altro"
            st.session_state["pagina"] = "Registrazione Clienti"
            st.session_state["destinazione_dopo_cliente"] = None
            st.rerun()
    st.stop()

# Logout button
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state["logged_in"] = False
    if "session" in st.query_params:
        del st.query_params["session"]
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Mercatino Libri Usati · Marconi Verona")


# --- CONTROLLO RUOLO ADMIN ---
def _is_admin():
    """True solo se l'operatore connesso e' admin (master o ruolo admin sulla tabella)."""
    op = st.session_state.get("operatore", "")
    if op == "admin":
        return True
    try:
        import gestione_operatori as go
        for o in go.lista_operatori():
            if o.get("username") == op and o.get("ruolo") == "admin":
                return True
    except Exception:
        pass
    return False


# --- GUIDE IN LINEA PER PAGINA (chiare e sintetiche) ---
GUIDE = {
    "Registrazione Clienti": "📌 **Guida:** Inserisci Nome, Cognome, Telefono ed Email (tutti obbligatori). Il codice cliente si genera da solo. Usa la tab 'Modifica' per correggere o eliminare un cliente esistente.",
    "Ritiro Libri (Venditori)": "📌 **Guida:** Seleziona il venditore (resta in memoria), cerca il libro per ISBN/Titolo/Classe, imposta il prezzo e aggiungilo al carrello. Alla fine conferma per salvare e stampare ricevuta + etichette.",
    "Cassa e Vendita Rapida": "📌 **Guida:** Seleziona l'acquirente, individua il libro (numero copertina, codice venditore o barcode), aggiungilo al carrello, scegli Contanti/Bancomat e registra la vendita per emettere la ricevuta.",
    "Gestione Conti Cliente": "📌 **Guida:** Cerca un cliente per codice o nominativo per vedere i suoi libri consegnati, quelli venduti e l'importo ancora da liquidare.",
    "🔍 Cerca Libro": "📌 **Guida:** Filtra per ISBN, Titolo, Numero copia o Codice cliente per vedere lo stato, la cronologia e le ricevute collegate di ogni copia.",
    " Archivio": "📌 **Guida:** Consulta gli archivi divisi in Ricevute (PDF online), Clienti, Libri in possesso e Libri venduti. Dati in sola lettura.",
}

st.caption(GUIDE.get(menu, ""))

def genera_pdf_tutte_liquidazioni(cli_list, df_movimenti):
    """Genera un unico PDF cumulativo con una ricevuta di liquidazione per ogni cliente"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    stile_bold = ParagraphStyle('TabBold', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')
    
    clienti_con_vendite = 0
    for c in cli_list:
        libri_venduti_c = df_movimenti[(df_movimenti['id_venditore'] == c['id']) & (df_movimenti['stato'] == 'venduto')]
        
        if not libri_venduti_c.empty:
            clienti_con_vendite += 1
            if clienti_con_vendite > 1:
                from reportlab.platypus import PageBreak
                story.append(PageBreak())
                
            inserisci_intestazione_marconi(story)
            story.append(Paragraph("<b>RENDICONTO E LIQUIDAZIONE FINALE DI FINE ANNO</b>", styles['Title']))
            story.append(Spacer(1, 10))
            
            inserisci_anagrafica_cliente(story, "SPETT.LE VENDITORE", c)
            
            dati_tab = [["Cod. Copertina", "Titolo Libro Venduto", "Prezzo Spettante"]]
            for _, riga in libri_venduti_c.iterrows():
                dati_tab.append([str(riga['id_libro']), riga['titolo'][:45], f"{riga['Prezzo Liquidazione']:.2f} €"])
                
            somma_da_dare = libri_venduti_c['Prezzo Liquidazione'].sum()
            dati_tab.append(["", Paragraph("<b>TOTALE DA LIQUIDARE IN CONTANTI</b>", stile_bold), Paragraph(f"<b>{somma_da_dare:.2f} €</b>", stile_bold)])
            
            t = Table(dati_tab, colWidths=[100, 340, 100])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-2), 0.5, colors.black),
                ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.black),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(t)
            story.append(Spacer(1, 20))
            story.append(Paragraph("Firma per ricevuta del denaro: __________________________________________________", styles['Normal']))
            
    if clienti_con_vendite == 0:
        story.append(Paragraph("Nessun cliente ha libri venduti da liquidare al momento.", styles['Normal']))
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue(), clienti_con_vendite

@st.cache_data(show_spinner=False, ttl=60)
def _dati_admin():
    """Carica in parallelo i dati necessari alle azioni admin (cache 60s)."""
    def _get(url):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_c = ex.submit(_get, f"{URL_REST}/copie_libri?select=*")
        f_k = ex.submit(_get, f"{URL_REST}/catalogo_libri?select=isbn,titolo,prezzo_copertina")
        f_l = ex.submit(_get, f"{URL_REST}/clienti?select=*")
        return f_c.result(), f_k.result(), f_l.result()


@st.cache_data(show_spinner=False, ttl=60)
def _archivio_clienti():
    try:
        r = requests.get(f"{URL_REST}/clienti?select=*&order=id.desc", headers=HEADERS, timeout=30)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=60)
def _archivio_copie(stato_filtro):
    """Carica copie filtrate lato server (stato) + catalogo, in parallelo."""
    def _get(url):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []
    from concurrent.futures import ThreadPoolExecutor
    q = "eq.venduto" if stato_filtro == "venduto" else "neq.venduto"
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_c = ex.submit(_get, f"{URL_REST}/copie_libri?stato={q}&order=id_libro.desc")
        f_k = ex.submit(_get, f"{URL_REST}/catalogo_libri?select=isbn,titolo,autore,prezzo_copertina")
        return f_c.result(), f_k.result()


@st.cache_data(show_spinner=False, ttl=60)
def _archivio_ricevute():
    return list_receipts(bucket_name="ricevute", project_id=PROJECT_ID, api_key=CHIAVE_SUPABASE, limit=200)


# --- PANNELLO ADMIN: visibile e utilizzabile SOLO dagli admin ---
if _is_admin():
    st.sidebar.write("<br/><br/><br/><br/>", unsafe_allow_html=True)
    with st.sidebar.expander("🔧 AREA ADMIN: Report, Reset & CSV", expanded=True):
        scelta_admin = st.radio("Seleziona Azione Admin:", ["📈 Vedi Contabilità Totale", "📂 Importa Nuovo CSV", "👥 Gestione Operatori", "🧾 Genera Ricevute Fine Anno", "🚨 Reset Database", "📜 Log Errori"])
        st.markdown("---")

        if scelta_admin in ("📈 Vedi Contabilità Totale", "🧾 Genera Ricevute Fine Anno", "🚨 Reset Database"):
            copie, cat, cli = _dati_admin()
            df_m = pd.DataFrame()
            if copie and cat:
                df_m = pd.merge(pd.DataFrame(copie), pd.DataFrame(cat), on="isbn", how="left")
                df_m['prezzo_copertina'] = df_m['prezzo_copertina'].astype(float)
                df_m['Prezzo Vendita'] = (df_m['prezzo_copertina'] / 2) + 0.50
                df_m['Prezzo Liquidazione'] = (df_m['prezzo_copertina'] / 2) - 0.50

        if scelta_admin == "📈 Vedi Contabilità Totale":
            if not df_m.empty:
                venduti = df_m[df_m['stato'] == 'venduto']
                contanti = venduti[venduti['metodo_pagamento'].str.lower() == 'contanti']['Prezzo Vendita'].sum()
                bancomat = venduti[venduti['metodo_pagamento'].str.lower().str.contains('bancomat', na=False)]['Prezzo Vendita'].sum()
                
                st.metric("💵 Totale CONTANTI Accumulato", f"{contanti:.2f} €")
                st.metric("💳 Totale BANCOMAT Accumulato", f"{bancomat:.2f} €")
                st.metric("📈 Guadagno Netto Trattenuto (Quota 1€)", f"{len(venduti)*1.00:.2f} €")
            else:
                st.info("Nessun movimento memorizzato nel magazzino.")
                
        elif scelta_admin == "📂 Importa Nuovo CSV":
            import catalogo
            importlib.reload(catalogo)
            catalogo.mostra_pagina_interna()
            
        elif scelta_admin == "👥 Gestione Operatori":
            import gestione_operatori as go
            st.markdown("Crea e gestisci gli account degli operatori. Spunta ✅ per rendere un operatore admin; selezionalo per eliminarlo.")

            with st.form("nuovo_operatore", clear_on_submit=True):
                st.markdown("**➕ Crea nuovo operatore**")
                n_u = st.text_input("Username", key="nuovo_user")
                n_p = st.text_input("Password", type="password", key="nuovo_pwd")
                n_p2 = st.text_input("Ripeti Password", type="password", key="nuovo_pwd2")
                n_r = st.selectbox("Ruolo", ["operatore", "admin"], key="nuovo_ruolo")
                submitted = st.form_submit_button("✅ Crea Operatore")
                if submitted:
                    if n_p != n_p2:
                        st.error("Le password non coincidono.")
                    else:
                        ok, msg = go.crea_operatore(n_u, n_p, n_r)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

            st.markdown("---")
            st.markdown("**📋 Operatori esistenti** (✅ = admin · ☐ = operatore)")
            ops = go.lista_operatori()
            if not ops:
                st.info("Nessun operatore registrato (oltre all'admin master).")
            else:
                selezionati_elimina = []
                for o in ops:
                    username_o = o.get('username')
                    is_admin_o = o.get('ruolo', 'operatore') == 'admin'
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.checkbox(
                            f"🗑️ {username_o}",
                            key=f"sel_del_{username_o}",
                            help="Seleziona per eliminare questo operatore",
                        )
                    with c2:
                        st.caption("admin")
                        nuovo_admin = st.checkbox(
                            "",
                            value=is_admin_o,
                            key=f"flag_admin_{username_o}",
                            label_visibility="collapsed",
                            help="Spunta per rendere admin, togli per operatore",
                        )
                        if nuovo_admin != is_admin_o:
                            ok, msg = go.cambia_ruolo(username_o, "admin" if nuovo_admin else "operatore")
                            st.success(msg) if ok else st.error(msg)
                            st.rerun()
                    with c3:
                        if st.session_state.get(f"sel_del_{username_o}", False):
                            selezionati_elimina.append(username_o)

                if selezionati_elimina:
                    if st.button("🗑️ Elimina selezionati", use_container_width=True):
                        for u in selezionati_elimina:
                            ok, msg = go.elimina_operatore(u)
                            st.success(msg) if ok else st.error(msg)
                        st.rerun()
                else:
                    st.caption("Nessun operatore selezionato per l'eliminazione.")

        elif scelta_admin == "🧾 Genera Ricevute Fine Anno":
            st.info("🧾 Genera in automatico tutte le ricevute di liquidazione dei clienti che hanno venduto.")
            # Esportazione resoconto JSON
            import export_fine_anno
            try:
                testo_json, nome_file = export_fine_anno.genera_resoconto_fine_anno()
                st.download_button(
                    label="📦 SCARICA RESOCONTO COMPLETO FINE ANNO (JSON)",
                    data=testo_json,
                    file_name=nome_file,
                    mime="application/json",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update({"resoconto_scaricato": True}),
                )
                st.caption("💡 Contiene clienti, copie, vendite, liquidazioni e totali di cassa.")
            except Exception as e:
                st.error(f"Errore nella generazione del resoconto: {e}")

            if not df_m.empty and cli:
                pdf_data, qta_c = genera_pdf_tutte_liquidazioni(cli, df_m)
                st.write(f"ℹ️ Trovati **{qta_c}** clienti con soldi da riscuotere.")
                st.download_button(
                    label="🖨️ GENERA E SCARICA TUTTE LE RICEVUTE DI LIQUIDAZIONE (PDF)",
                    data=pdf_data,
                    file_name="ricevute_liquidazione_fine_anno.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update({"ricevute_scaricate": True}),
                )

                # Anteprima riepilogo: quanto devi dare a ogni singolo utente
                st.markdown("---")
                st.subheader("💶 Quanta liquidazione spetta a ogni cliente")
                righe_liq = []
                for c in cli:
                    libri_v = df_m[(df_m['id_venditore'] == c['id']) & (df_m['stato'] == 'venduto')]
                    libri_r = df_m[(df_m['id_venditore'] == c['id']) & (df_m['stato'] == 'disponibile')]
                    if libri_v.empty and libri_r.empty:
                        continue
                    da_liq = libri_v['Prezzo Liquidazione'].sum() if not libri_v.empty else 0.0
                    # 'Prezzo Liquidazione' è già 50% - 0,50 € a libro: i 0,50 € sono il
                    # rimborso spese di gestione trattenuto dal negozio (voce a sé stante), NON vanno ri-sommati.
                    rimborso_spese = len(libri_v) * 0.50
                    tot_dare = da_liq
                    righe_liq.append({
                        "Codice": c.get('codice_personale', ''),
                        "Cliente": f"{c.get('cognome','')} {c.get('nome','')}",
                        "Libri venduti": len(libri_v),
                        "Rimborso Spese Gest. (€)": round(rimborso_spese, 2),
                        "Liquidazione (€)": round(da_liq, 2),
                        "TOTALE DA DARE (€)": round(tot_dare, 2),
                        "Libri da restituire": len(libri_r),
                    })
                if righe_liq:
                    df_liq = pd.DataFrame(righe_liq)
                    st.dataframe(df_liq, use_container_width=True, hide_index=True)
                    st.caption("💡 'Liquidazione' = 50% del prezzo di copertina MENO 0,50 € di rimborso spese di gestione a libro. 'TOTALE DA DARE' è la somma delle liquidazioni. I 0,50 €/libro sono il rimborso spese trattenuto dal negozio (voce a sé stante). I libri da restituire sono quelli non venduti da ridare al cliente.")
                else:
                    st.info("Nessun cliente con libri da liquidare/restituire.")
            else:
                st.info("Nessun dato da liquidare nei report.")

            if st.session_state.get("ricevute_scaricate") and st.session_state.get("resoconto_scaricato"):
                st.success("✅ Ricevute e resoconto scaricati: ora puoi procedere al reset del database.")
            else:
                st.warning("⚠️ Scarica sia il PDF delle ricevute che il resoconto JSON prima di azzerare il database.")

        elif scelta_admin == "🚨 Reset Database":
            # Blocco: il reset e' consentito SOLO dopo aver scaricato ricevute e resoconto
            ricevute_ok = st.session_state.get("ricevute_scaricate", False)
            resoconto_ok = st.session_state.get("resoconto_scaricato", False)

            if not (ricevute_ok and resoconto_ok):
                st.error("🚫 Impossibile azzerare il database. Devi prima scaricare il PDF delle ricevute E il resoconto JSON nella sezione '🧾 Genera Ricevute Fine Anno'.")
                st.markdown("👉 Vai su **🧾 Genera Ricevute Fine Anno**, scarica entrambi i file, poi torna qui.")
            else:
                st.success("✅ Hai scaricato ricevute e resoconto: puoi ora azzerare il database in sicurezza.")

                st.markdown("**📥 Recupera / Reimporta da file JSON** (ripristina i dati salvati a fine anno)")
                file_json = st.file_uploader("Carica il resoconto JSON esportato", type=["json"])
                if file_json is not None:
                    import json as _json
                    try:
                        dati = _json.loads(file_json.getvalue().decode("utf-8"))
                        if st.button("♻️ Reimporta dati dal JSON nel database"):
                            with st.spinner("Reimportazione in corso..."):
                                # Catalogo
                                for x in dati.get("catalogo_libri", []):
                                    requests.post(f"{URL_REST}/catalogo_libri", headers=HEADERS, json=x)
                                # Clienti
                                for x in dati.get("clienti", []):
                                    requests.post(f"{URL_REST}/clienti", headers=HEADERS, json=x)
                                # Copie
                                for x in dati.get("copie_libri", []):
                                    requests.post(f"{URL_REST}/copie_libri", headers=HEADERS, json=x)
                            st.success("♻️ Dati reimportati (i duplicati potrebbero generare nuovi ID).")
                            st.rerun()
                    except Exception as e:
                        st.error(f"File non valido: {e}")

                st.markdown("---")
                chk_r = st.checkbox("Confermo: voglio cancellare il magazzino copie usate")
                if chk_r and st.button("🚨 ESEGUI CANCELLAZIONE COPIE FISICHE"):
                    requests.delete(f"{URL_REST}/copie_libri?id_libro=gt.0", headers=HEADERS)
                    # Azzeramento contatore ricevute: lo storico resta nel JSON di fine anno
                    # e nei PDF gia' caricati su Storage, ma il numero riparte da 1/V, 1/R.
                    try:
                        requests.delete(f"{URL_REST}/ricevute?id=gt.0", headers=HEADERS)
                    except Exception:
                        pass
                    st.success("🧼 Magazzino copie svuotato e contatore ricevute azzerato!")
                    st.session_state["ricevute_scaricate"] = False
                    st.session_state["resoconto_scaricato"] = False
                    st.rerun()

                st.markdown("---")
                chk_l = st.checkbox("Confermo: voglio azzerare anche il catalogo dei 740 libri (Caricamento Anno Nuovo)")
                if chk_l and st.button("🚨 CANCELLA CATALOGO LIBRI ADOZIONI"):
                    requests.delete(f"{URL_REST}/copie_libri?id_libro=gt.0", headers=HEADERS)
                    requests.delete(f"{URL_REST}/catalogo_libri?isbn=not.is.null", headers=HEADERS)
                    # Azzeramento contatore ricevute (storico preservato su JSON + Storage)
                    try:
                        requests.delete(f"{URL_REST}/ricevute?id=gt.0", headers=HEADERS)
                    except Exception:
                        pass
                    st.success("🧼 Catalogo libri svuotato e contatore ricevute azzerato!")
                    st.session_state["ricevute_scaricate"] = False
                    st.session_state["resoconto_scaricato"] = False
                    st.rerun()

        elif scelta_admin == "📜 Log Errori":
            st.info("📜 Log centralizzato degli errori (su Supabase). Visibile online, non sui PC degli utenti.")
            import logger_supabase
            log_rows = logger_supabase.leggi_log_errori(limite=300)
            if not log_rows:
                st.info("Nessun errore registrato finora.")
            else:
                df_log = pd.DataFrame(log_rows)
                df_log['creato_il'] = pd.to_datetime(df_log['creato_il']).dt.strftime("%Y-%m-%d %H:%M:%S")
                df_log = df_log[['creato_il', 'tipo', 'messaggio', 'dettaglio', 'operatore', 'pagina']]
                df_log.columns = ['Data/Ora', 'Tipo', 'Messaggio', 'Dettaglio', 'Operatore', 'Pagina']
                st.dataframe(df_log, use_container_width=True, hide_index=True)
                st.caption(f"Totale errori registrati: {len(df_log)} (ultimi 300)")
else:
    st.sidebar.caption("🔒 Funzioni di amministrazione riservate all'admin.")

# --- ARCHIVI CENTRALIZZATI ---
if menu == "Registrazione Clienti":
    import clienti
    clienti.mostra_pagina()
elif menu == "Ritiro Libri (Venditori)":
    import ritiro
    ritiro.mostra_pagina()
elif menu == "Cassa e Vendita Rapida":
    import cassa
    cassa.mostra_pagina()
elif menu == "Gestione Conti Cliente":
    import gestione_conti
    gestione_conti.mostra_pagina()
elif menu == "🔍 Cerca Libro":
    import cerca_libro
    cerca_libro.mostra_pagina()
elif menu == " Archivio":
    st.header("📁 Archivio")
    tab_ricevute, tab_clienti, tab_possesso, tab_venduti = st.tabs([
        "📄 Ricevute", "👤 Clienti", "📦 Libri in mio possesso", "💰 Libri venduti"
    ])

    with tab_ricevute:
        st.subheader("📂 Archivio Ricevute Organizzato")
        risultato = _archivio_ricevute()
        if not risultato.get("ok"):
            st.info("Nessuna ricevuta caricata online finora.")
        else:
            objs = risultato.get("objects", [])
            if not objs:
                st.info("Nessuna ricevuta caricata online finora.")
            else:
                # Parsing dei file ricevuti per estrarre informazioni strutturate
                rows = []
                for o in objs:
                    name = o.get('name') or o.get('Key') or o.get('id')
                    if not name or name.startswith('.'):
                        continue
                    updated = o.get('updated_at') or o.get('created_at') or o.get('last_modified')
                    # Gestiamo la formattazione della data di modifica
                    if updated:
                        try:
                            dt = datetime.datetime.fromisoformat(updated.replace('Z', '+00:00'))
                            updated_formatted = dt.strftime("%d/%m/%Y %H:%M")
                        except Exception:
                            updated_formatted = str(updated)
                    else:
                        updated_formatted = "N.D."
                        
                    public_url = build_public_storage_url(PROJECT_ID, 'ricevute', name)
                    
                    # Splittiamo il nome del file per estrarre tipo, data e codice cliente
                    # Formato standard: tipo-YYYY-MM-DD-codice_cliente-suffisso.pdf
                    parts = name.replace('.pdf', '').split('-')
                    tipo = "Altro 📄"
                    data_str = "N.D."
                    codice_cliente = "N.D."
                    dettagli = ""
                    operatore_estratto = "N.D."
                    
                    # Estraiamo l'operatore se presente nel nome del file nel formato '-op-nomeoperatore-'
                    if "-op-" in name:
                        try:
                            sub_parts = name.split("-op-")
                            if len(sub_parts) > 1:
                                operatore_estratto = sub_parts[1].split("-")[0].upper()
                        except Exception:
                            pass

                    if parts:
                        if parts[0] == "vendita":
                            tipo = "Vendita 🛒"
                        elif parts[0] == "ritiro":
                            tipo = "Ritiro 📥"
                        elif parts[0] == "resoconto":
                            tipo = "Rendiconto 📊"
                            
                        # Controlla se abbiamo la data nei segmenti 1, 2, 3 (es. 2026-07-18)
                        if len(parts) >= 4 and parts[1].isdigit() and len(parts[1]) == 4:
                            data_str = f"{parts[3]}/{parts[2]}/{parts[1]}" # DD/MM/YYYY
                            rem = parts[4:]
                        else:
                            rem = parts[1:]
                            
                        if rem:
                            codice_cliente = rem[0].upper()
                            # Togliamo la parte dell'operatore dai dettagli per pulizia
                            raw_details = "-".join(rem[1:])
                            if f"op-{operatore_estratto.lower()}-" in raw_details:
                                raw_details = raw_details.replace(f"op-{operatore_estratto.lower()}-", "")
                            elif f"op-{operatore_estratto.lower()}" in raw_details:
                                raw_details = raw_details.replace(f"op-{operatore_estratto.lower()}", "")
                            dettagli = raw_details.replace('-', ' ')
                    
                    rows.append({
                        'Nome file': name,
                        'Tipo': tipo,
                        'Data': data_str,
                        'Cliente': codice_cliente,
                        'Dettagli': dettagli,
                        'Operatore': operatore_estratto,
                        'Aggiornato': updated_formatted,
                        'URL': public_url
                    })
                
                df_r = pd.DataFrame(rows)
                
                # Sezione di ricerca e suddivisione
                st.markdown("#### Filtra e Cerca Ricevute")
                c1, c2 = st.columns([1, 2])
                with c1:
                    categoria = st.selectbox(
                        "Suddividi per categoria:", 
                        ["Tutte", "Vendite 🛒", "Ritiri 📥", "Rendiconto 📊", "Altro 📄"]
                    )
                with c2:
                    search_term = st.text_input(
                        "🔍 Cerca per Codice Cliente, Operatore, Data (es. 18/07/2026) o dettagli:", 
                        ""
                    ).strip().lower()
                
                # Applica filtri
                df_filtered = df_r.copy()
                if categoria != "Tutte":
                    df_filtered = df_filtered[df_filtered['Tipo'] == categoria]
                    
                if search_term:
                    df_filtered = df_filtered[
                        df_filtered['Nome file'].str.lower().str.contains(search_term) |
                        df_filtered['Tipo'].str.lower().str.contains(search_term) |
                        df_filtered['Data'].str.lower().str.contains(search_term) |
                        df_filtered['Cliente'].str.lower().str.contains(search_term) |
                        df_filtered['Operatore'].str.lower().str.contains(search_term) |
                        df_filtered['Dettagli'].str.lower().str.contains(search_term)
                    ]
                
                if df_filtered.empty:
                    st.info("Nessuna ricevuta trovata con i filtri inseriti.")
                else:
                    st.write(f"Trovate **{len(df_filtered)}** ricevute:")
                    
                    # Mostra un elenco pulito e ordinato con bottoni dedicati
                    # Ordiniamo per data/nome decrescente così le più recenti sono in alto
                    df_filtered = df_filtered.sort_values(by=['Aggiornato', 'Nome file'], ascending=False)
                    
                    for idx, row in df_filtered.head(50).iterrows():
                        col_info, col_btn = st.columns([4, 1])
                        with col_info:
                            st.markdown(f"**{row['Tipo']}** | Data Ricevuta: `{row['Data']}` | Cliente: `{row['Cliente']}` | Operatore: `👤 {row['Operatore']}`")
                            if row['Dettagli']:
                                st.markdown(f"↳ *Dettagli: {row['Dettagli']}*")
                            st.caption(f"Nome file: `{row['Nome file']}` | Ultima modifica: {row['Aggiornato']}")
                        with col_btn:
                            st.link_button("📂 Apri PDF", row['URL'], use_container_width=True)
                        st.markdown("<hr style='margin: 8px 0px; border-color: rgba(49, 51, 63, 0.08);'>", unsafe_allow_html=True)
                        
                    if len(df_filtered) > 50:
                        st.caption("💡 Vengono mostrate solo le prime 50 ricevute più recenti. Utilizza la ricerca per trovare quelle meno recenti.")

    with tab_clienti:
        st.subheader("Archivio anagrafica clienti")
        clienti = _archivio_clienti()
        if not clienti:
            st.info("Nessun cliente registrato.")
        else:
            df_c = pd.DataFrame(clienti)
            df_c = df_c[['id', 'codice_personale', 'nome', 'cognome', 'telefono', 'email']]
            df_c.columns = ['ID', 'Codice', 'Nome', 'Cognome', 'Telefono', 'Email']
            st.dataframe(df_c, use_container_width=True, hide_index=True)

    with tab_possesso:
        st.subheader("Libri attualmente in mio possesso (non ancora venduti)")
        copie, cat = _archivio_copie("possesso")
        if not copie:
            st.info("Nessun libro in possesso al momento.")
        else:
            df_p = pd.merge(pd.DataFrame(copie), pd.DataFrame(cat), on="isbn", how="left")
            df_p = df_p[['id_libro', 'isbn', 'titolo', 'autore', 'prezzo_copertina', 'id_venditore']]
            df_p.columns = ['Cod. Copertina', 'ISBN', 'Titolo', 'Autore', 'Prezzo Copertina', 'ID Venditore']
            st.dataframe(df_p, use_container_width=True, hide_index=True)

    with tab_venduti:
        st.subheader("Libri venduti")
        copie, cat = _archivio_copie("venduto")
        if not copie:
            st.info("Nessun libro venduto al momento.")
        else:
            df_v = pd.merge(pd.DataFrame(copie), pd.DataFrame(cat), on="isbn", how="left")
            df_v['Prezzo Vendita'] = (df_v['prezzo_copertina'].astype(float) / 2) + 0.50
            df_v = df_v[['id_libro', 'isbn', 'titolo', 'autore', 'Prezzo Vendita', 'metodo_pagamento', 'id_venditore']]
            df_v.columns = ['Cod. Copertina', 'ISBN', 'Titolo', 'Autore', 'Prezzo Vendita', 'Pagamento', 'ID Venditore']
            st.dataframe(df_v, use_container_width=True, hide_index=True)
