import importlib
import streamlit as st
import pandas as pd
import requests
import os
import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from ricevute_condivise import (
    inserisci_intestazione_marconi,
    inserisci_anagrafica_cliente,
    inserisci_qrcode_marconi,
    pubblica_ricevuta_online,
)
from gestore_etichette import genera_griglia_a4, stampa_etichette_tm_l90, genera_preview_etichette


# --- FUNZIONI CON CACHE PER VELOCIZZARE LE RICERCHE ---
@st.cache_data(show_spinner=False, ttl=60)
def _carica_clienti_ritiro():
    r = requests.get(f"{URL_REST}/clienti?select=id,codice_personale,nome,cognome,telefono,email", headers=HEADERS)
    return r.json() if r.status_code == 200 else []


@st.cache_data(show_spinner=False, ttl=30)
def _cerca_isbn_ritiro(frammento):
    r = requests.get(f"{URL_REST}/catalogo_libri?isbn=ilike.*{frammento}*&select=*", headers=HEADERS)
    return r.json() if r.status_code == 200 else []


@st.cache_data(show_spinner=False, ttl=30)
def _cerca_testo_ritiro(testo):
    r = requests.get(f"{URL_REST}/catalogo_libri?or=(titolo.ilike.*{testo}*,autore.ilike.*{testo}*)&select=*", headers=HEADERS)
    return r.json() if r.status_code == 200 else []


@st.cache_data(show_spinner=False, ttl=30)
def _cerca_classe_ritiro(classe):
    r = requests.get(f"{URL_REST}/catalogo_libri?classi=ilike.*{classe}*&select=*", headers=HEADERS)
    return r.json() if r.status_code == 200 else []


@st.cache_data(show_spinner=False, ttl=30)
def _cerca_area_ritiro(filtro_area):
    r = requests.get(f"{URL_REST}/catalogo_libri?or=({filtro_area})&select=isbn,titolo,classi,prezzo_copertina", headers=HEADERS)
    return r.json() if r.status_code == 200 else []

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def aggiorna_carrello_ritiro(carrello, libro_selezionato, quantita=1):
    chiave = (libro_selezionato.get("isbn"), libro_selezionato.get("titolo"))
    for item in carrello:
        if (item.get("isbn"), item.get("titolo")) == chiave:
            item["prezzo"] = float(item.get("prezzo", 0.0) or 0.0)
            item["quantita"] = int(item.get("quantita", 1) or 1) + int(quantita or 1)
            return carrello

    carrello.append({
        "isbn": libro_selezionato.get("isbn"),
        "titolo": libro_selezionato.get("titolo"),
        "prezzo": float(libro_selezionato.get("prezzo", 0.0) or 0.0),
        "quantita": int(quantita or 1),
    })
    return carrello


def prossimo_numero_ricevuta(tipo):
    """Calcola il prossimo numero progressivo per tipo ('R' ritiro, 'V' vendita)."""
    try:
        r = requests.get(
            f"{URL_REST}/ricevute?tipo=eq.{tipo}&select=numero_progressivo&order=numero_progressivo.desc&limit=1",
            headers=HEADERS,
        )
        if r.status_code == 200 and r.json():
            return (r.json()[0].get("numero_progressivo") or 0) + 1
    except Exception:
        pass
    key = f"num_ricevute_{tipo}"
    if key not in st.session_state:
        st.session_state[key] = 0
    st.session_state[key] += 1
    return st.session_state[key]


def genera_pdf_ricevuta(dati_cliente, libri_ritirati, numero_ricevuta=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    inserisci_intestazione_marconi(story)
    story.append(Paragraph("<b>RICEVUTA DI RITIRO IN CONTO VENDITA</b>", styles['Title']))
    # Numero ricevuta grande e in alto a destra
    stile_num_r = ParagraphStyle('NumRicevutaR', parent=styles['Title'], alignment=2, spaceAfter=2)
    if numero_ricevuta is None:
        numero_ricevuta = "N/D"
    story.append(Paragraph(f"N. RICEVUTA: <b>{numero_ricevuta}</b>", stile_num_r))
    # Data e ora in piccolo, sempre a destra
    stile_data = ParagraphStyle('DataOra', parent=styles['Normal'], alignment=2, fontSize=9, textColor=colors.grey)
    story.append(Paragraph(f"Data: {datetime.date.today().strftime('%d/%m/%Y')}  Ora: {datetime.datetime.now().strftime('%H:%M')}", stile_data))
    story.append(Spacer(1, 10))
    
    inserisci_anagrafica_cliente(story, "VENDITORE / CONFERENTE", dati_cliente)
    
    stile_cella = ParagraphStyle('CellaTab', parent=styles['Normal'], fontSize=8, leading=10)
    stile_cella_b = ParagraphStyle('CellaTabB', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')
    
    dati_tabella = [[
        Paragraph("<b>Cod. Etichetta</b>", stile_cella_b), 
        Paragraph("<b>ISBN</b>", stile_cella_b), 
        Paragraph("<b>Titolo Libro Scolastico</b>", stile_cella_b), 
        Paragraph("<b>Prezzo Cop.</b>", stile_cella_b), 
        Paragraph("<b>Tua Liq.</b>", stile_cella_b)
    ]]
    
    for l in libri_ritirati:
        # La liquidazione è il 50% del prezzo di copertina MENO 0,50 € di commissione
        # negozio (voce a sé stante): il venditore riceve 50 cent in meno a libro venduto.
        prezzo_liquidazione = (float(l['prezzo']) / 2) - 0.50
        dati_tabella.append([
            Paragraph(l['etichetta'], stile_cella),
            Paragraph(l['isbn'], stile_cella),
            Paragraph(l['titolo'].upper(), stile_cella),
            Paragraph(f"{l['prezzo']:.2f} €", stile_cella),
            Paragraph(f"{prezzo_liquidazione:.2f} €", stile_cella)
        ])
        
    col_etichetta = 95
    col_isbn = 95
    col_prezzo_cop = 65
    col_prezzo_liq = 65
    col_titolo = 540 - col_etichetta - col_isbn - col_prezzo_cop - col_prezzo_liq
    
    tabella = Table(dati_tabella, colWidths=[col_etichetta, col_isbn, col_titolo, col_prezzo_cop, col_prezzo_liq])
    tabella.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(tabella)
    
    from ricevute_condivise import inserisci_clausole_legali_ritiro
    inserisci_clausole_legali_ritiro(story)
    
    inserisci_qrcode_marconi(story)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def genera_pdf_rotolo_etichette(libri_ritirati):
    buffer = BytesIO()
    larghezza_etichetta = 226
    altezza_etichetta = 108
    doc = SimpleDocTemplate(buffer, pagesize=(larghezza_etichetta, altezza_etichetta), rightMargin=5, leftMargin=5, topMargin=5, bottomMargin=5)
    story = []
    styles = getSampleStyleSheet()
    
    stile_codice = ParagraphStyle('TermicoCodice', parent=styles['Normal'], fontSize=15, fontName='Helvetica-Bold', alignment=1, leading=17)
    stile_titolo = ParagraphStyle('TermicoTitolo', parent=styles['Normal'], fontSize=8, alignment=1, leading=10, textColor=colors.HexColor("#333333"))
    stile_info = ParagraphStyle('TermicoInfo', parent=styles['Normal'], fontSize=7, alignment=1, leading=9)

    for i, l in enumerate(libri_ritirati):
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"<b>{l['etichetta']}</b>", stile_codice))
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"{l['titolo'][:42].upper()}", stile_titolo))
        story.append(Spacer(1, 1))
        story.append(Paragraph(f"ISBN: {l['isbn']}", stile_info))
        story.append(Paragraph("Mercatino Marconi Verona", stile_info))
        
        if i < len(libri_ritirati) - 1:
            from reportlab.platypus import PageBreak
            story.append(PageBreak())
            
            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()

def genera_pdf_inventario_materia(df_totale):
    """Genera un PDF dell'inventario dei libri 'disponibile' (in carico), raggruppati per materia."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    inserisci_intestazione_marconi(story)
    story.append(Paragraph("<b>INVENTARIO LIBRI IN CARICO (per Materia)</b>", styles['Title']))
    story.append(Paragraph(f"Data: {datetime.date.today().strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 10))

    df_disp = df_totale[df_totale['Stato'] == 'disponibile'].copy()
    if df_disp.empty:
        story.append(Paragraph("Nessun libro in carico (disponibile) al momento.", styles['Normal']))
    else:
        materie = sorted([m for m in df_disp['Materia'].dropna().astype(str) if m and m.lower() != 'nan']) + ['(senza materia)']
        stile_cella = ParagraphStyle('CellaInv', parent=styles['Normal'], fontSize=8, leading=10)
        stile_cella_b = ParagraphStyle('CellaInvB', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')
        for mat in materie:
            if mat == '(senza materia)':
                sub = df_disp[df_disp['Materia'].isna() | (df_disp['Materia'].astype(str).str.lower() == 'nan') | (df_disp['Materia'].astype(str) == '')]
            else:
                sub = df_disp[df_disp['Materia'].astype(str) == mat]
            if sub.empty:
                continue
            story.append(Paragraph(f"<b>{str(mat).upper()}  —  n. {len(sub)}</b>", styles['Heading3']))
            dati = [[
                Paragraph("<b>Cod. Copertina</b>", stile_cella_b),
                Paragraph("<b>Titolo</b>", stile_cella_b),
                Paragraph("<b>ISBN</b>", stile_cella_b),
                Paragraph("<b>Prezzo Cop.</b>", stile_cella_b),
            ]]
            for _, r in sub.iterrows():
                dati.append([
                    Paragraph(str(r.get('Codice Copertina', '')), stile_cella),
                    Paragraph(str(r.get('Titolo', r.get('ISBN', ''))).upper(), stile_cella),
                    Paragraph(str(r.get('ISBN', '')), stile_cella),
                    Paragraph(f"{float(r.get('Prezzo Copertina (€)', 0.0) or 0.0):.2f} €", stile_cella),
                ])
            t = Table(dati, colWidths=[100, 300, 100, 80])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def mostra_pagina():
    st.header("📥 Presa in Carico e Ritiro Libri Usati")
    tab_ritiro, tab_inventario = st.tabs(["Prendi in Carico Libri", "📋 Inventario Generale Magazzino"])
    
    if "carrello_ritiro" not in st.session_state:
        st.session_state["carrello_ritiro"] = []
    if "libri_appena_salvati" not in st.session_state:
        st.session_state["libri_appena_salvati"] = []
        
    with tab_ritiro:
        clienti_list = _carica_clienti_ritiro()
        
        if not clienti_list:
            st.warning("⚠️ Registra almeno un cliente prima di fare un ritiro.")
            return
            
        opzioni_clienti = {f"{c['id']} - {c['cognome']} {c['nome']} ({c['codice_personale']})": c for c in clienti_list}
        chiavi_clienti = list(opzioni_clienti.keys())

        # Mantiene in memoria l'ultimo venditore selezionato tra un rerun e l'altro
        if "id_venditore_corrente" not in st.session_state:
            st.session_state["id_venditore_corrente"] = None
        index_venditore = 0
        if st.session_state["id_venditore_corrente"] is not None:
            for i, k in enumerate(chiavi_clienti):
                if opzioni_clienti[k]["id"] == st.session_state["id_venditore_corrente"]:
                    index_venditore = i
                    break

        cliente_selezionato = st.selectbox(
            "Seleziona il Cliente / Venditore",
            chiavi_clienti,
            index=index_venditore,
            help="Puoi digitare per filtrare l'elenco. La selezione resta memorizzata tra un'operazione e l'altra.",
        )
        dati_cliente = opzioni_clienti[cliente_selezionato]
        st.session_state["id_venditore_corrente"] = dati_cliente["id"]

        # Mostra subito i dati del venditore selezionato (leggibili senza cliccare di nuovo)
        st.info(
            f"👤 **Venditore selezionato:** {dati_cliente['cognome']} {dati_cliente['nome']}  \n"
            f"🆔 Codice: `{dati_cliente['codice_personale']}`  \n"
            f"📞 Tel: {dati_cliente.get('telefono', 'N.D.')}  \n"
            f"✉️ Email: {dati_cliente.get('email', 'N.D.')}"
        )
        
        st.markdown("---")
        modalita_ricerca = st.radio(
            "Come vuoi cercare il libro nel catalogo adozioni?", 
            ["🔍 Scansione o Inserimento ISBN (Anche Parziale)", "📖 Cerca per Titolo o Autore", "🏫 Filtra per Classe / Sezione (es. 1AI, 2BE)"], 
            horizontal=True
        )
        
        libri_trovati = []
        
        if modalita_ricerca == "🔍 Scansione o Inserimento ISBN (Anche Parziale)":
            isbn_input = st.text_input("Digita o scansiona il codice ISBN (Bastano anche poche cifre):").strip()
            if isbn_input:
                libri_trovati = _cerca_isbn_ritiro(isbn_input)
                if not libri_trovati: st.error("❌ Nessun libro trovato con questo frammento di ISBN.")
                
        elif modalita_ricerca == "📖 Cerca per Titolo o Autore":
            testo_ricerca = st.text_input("Digita una parte del titolo o del nome autore:").strip().lower()
            if len(testo_ricerca) >= 3:
                libri_trovati = _cerca_testo_ritiro(testo_ricerca)
                if not libri_trovati: st.error("❌ Nessun volume trovato nel catalogo adozioni.")
                
        else:
            classe_input = st.text_input("Digita la classe e sezione (es. '1AI', '2BE', '3CL'):").strip().upper()
            
            if classe_input.startswith("1"):
                with st.expander("📋 VEDI ELENCO LIBRI IN COMUNE PER MACRO-AREE (CLASSI PRIME)"):
                    st.write("Seleziona la macro-area per estrarre tutti i libri adottati contemporaneamente dalle sezioni con due lettere:")
                    area_scelta = st.selectbox("Scegli l'area dei corsi:", ["-- Seleziona Area --", "Area Liceo (1CL, 1DL)", "Area Tecnico (1AI, 1BE, 1CM)", "Area Professionale (1PR, 1MA)"])
                    
                    filtro_area = ""
                    if "Liceo" in area_scelta: filtro_area = "classi=ilike.*1CL*,classi=ilike.*1DL*"
                    elif "Tecnico" in area_scelta: filtro_area = "classi=ilike.*1AI*,classi=ilike.*1BE*,classi=ilike.*1CM*"
                    elif "Professionale" in area_scelta: filtro_area = "classi=ilike.*1PR*,classi=ilike.*1MA*"
                    
                    if filtro_area:
                        libri_area_list = _cerca_area_ritiro(filtro_area)
                        if libri_area_list:
                            df_area = pd.DataFrame(libri_area_list)
                            df_area.columns = ['ISBN', 'Titolo Volume Scolastico', 'Classi Adottanti', 'Prezzo (€)']
                            st.dataframe(df_area, use_container_width=True, hide_index=True)
                        else: st.info("Nessun libro inserito nel database per questa macro-area.")

            if classe_input:
                libri_trovati = _cerca_classe_ritiro(classe_input)
                if not libri_trovati: st.warning(f"Nessun libro censito specificamente per la classe {classe_input}.")

        # --- SELEZIONE DEL LIBRO E AGGIUNTA AL CARRELLO ---
        libro_selezionato_dati = None
        if libri_trovati:
            st.write("")
            mappa_scelte = {f"ISBN: {x['isbn']} | {x['titolo']} - Vol.{x.get('volume','ND')} ({x.get('classi','ND')})": x for x in libri_trovati}
            scelta_finale = st.selectbox(f"📚 Trovati {len(libri_trovati)} volumi corrispondenti. Seleziona quello corretto:", list(mappa_scelte.keys()))
            libro_selezionato_dati = mappa_scelte[scelta_finale]
            
        if libro_selezionato_dati is not None:
            st.markdown("---")
        if libro_selezionato_dati is not None:
            st.markdown("---")
            st.info(f"📖 **Volume Identificato:** {libro_selezionato_dati['titolo']} | 🆔 **ISBN:** {libro_selezionato_dati['isbn']}")
            
            prezzo_proposto = float(libro_selezionato_dati.get('prezzo_copertina', 0.0))
            prezzo_inserito = st.number_input("Inserisci o correggi il Prezzo di Copertina (€)", min_value=0.0, value=prezzo_proposto, step=0.50)
            quantita = st.number_input("Quante copie di questo libro stai prendendo in carico?", min_value=1, value=1)
            
            if st.button("➕ INSERISCI QUESTO TITOLO NEL CARRELLO DI RITIRO", use_container_width=True):
                aggiorna_carrello_ritiro(
                    st.session_state["carrello_ritiro"],
                    {
                        "isbn": libro_selezionato_dati['isbn'],
                        "titolo": libro_selezionato_dati['titolo'],
                        "prezzo": prezzo_inserito,
                    },
                    quantita=quantita,
                )
                st.success("Aggiunto al carrello provvisorio!")
                st.rerun()
                
        # --- TABELLA RIASSUNTIVA E SALVATAGGIO ---
        if st.session_state["carrello_ritiro"]:
            st.markdown("---")
            st.subheader("📦 Elenco Libri pronti per il salvataggio:")
            df_carrello = pd.DataFrame(st.session_state["carrello_ritiro"])
            if 'quantita' in df_carrello.columns:
                st.dataframe(df_carrello[['isbn', 'titolo', 'prezzo', 'quantita']], use_container_width=True)
            else:
                st.dataframe(df_carrello[['isbn', 'titolo', 'prezzo']], use_container_width=True)
            
            col_storno, _ = st.columns(2)
            with col_storno:
                indice_da_stornare = st.selectbox("🎯 Rimuovi riga errata:", range(len(st.session_state["carrello_ritiro"])), format_func=lambda x: f"Riga {x+1}: {st.session_state['carrello_ritiro'][x]['titolo'][:30]}")
                if st.button("❌ Rimuovi dal ritiro"):
                    st.session_state["carrello_ritiro"].pop(indice_da_stornare)
                    st.rerun()
            
            st.write("")
            col_salva, col_svuota = st.columns(2)
            with col_salva:
                if st.button("💾 CONFERMA IL RITIRO E SALVA TUTTO ONLINE", use_container_width=True):
                    with st.spinner("Salvataggio..."):
                        libri_per_ricevuta = []
                        for item in st.session_state["carrello_ritiro"]:
                            dati_invio = {
                                "isbn": item['isbn'], 
                                "id_venditore": dati_cliente['id'], 
                                "stato": "disponibile", 
                                "prezzo_inserito_mano": item['prezzo'],
                                "operatore": st.session_state.get("operatore", "Sconosciuto"),
                            }
                            res_ins = requests.post(f"{URL_REST}/copie_libri", headers=HEADERS, json=dati_invio)
                            # Se la colonna 'operatore' non esiste ancora su copie_libri,
                            # riprova senza di essa cosi il ritiro continua a funzionare.
                            if res_ins.status_code >= 400:
                                dati_invio.pop("operatore", None)
                                res_ins = requests.post(f"{URL_REST}/copie_libri", headers=HEADERS, json=dati_invio)
                            if res_ins.status_code < 400:
                                risposta_server = res_ins.json()
                                
                                # BLINDATURA INDICE: Estrazione protetta dell'elemento 0 per evitare il bug list indices
                                if isinstance(risposta_server, list) and len(risposta_server) > 0:
                                    dati_copia = risposta_server[0]
                                else:
                                    dati_copia = risposta_server
                                    
                                id_generato = dati_copia['id_libro']
                                # Barcode NUMERICO e corto (scansione affidabile): <id_venditore>-<id_libro>
                                # es. 123-31. L'id_libro e' univoco, quindi la cassa trova il libro
                                # anche se il prefisso alfabetico non viene letto dallo scanner.
                                barcode_val = f"{dati_cliente.get('id')}-{id_generato}"
                                libri_per_ricevuta.append({
                                    "etichetta": barcode_val,
                                    "isbn": item['isbn'], 
                                    "titolo": item['titolo'], 
                                    "prezzo": item['prezzo'],
                                    "codice_personale": dati_cliente['codice_personale'],
                                    "id_venditore": dati_cliente.get('id'),
                                    "barcode": barcode_val
                                })
                                # Salva anche il barcode su DB cosi' la scansione in cassa lo trova direttamente
                                try:
                                    requests.patch(
                                        f"{URL_REST}/copie_libri?id_libro=eq.{id_generato}",
                                        headers=HEADERS,
                                        json={"barcode": barcode_val}
                                    )
                                except Exception:
                                    pass
                        
                        if libri_per_ricevuta:
                            # Numero progressivo per tipo ritiro: N/R
                            n_ricevuta = prossimo_numero_ricevuta("R")
                            numero_ricevuta = f"{n_ricevuta}/R"
                            try:
                                requests.post(
                                    f"{URL_REST}/ricevute",
                                    headers=HEADERS,
                                    json={
                                        "tipo": "R",
                                        "numero_progressivo": n_ricevuta,
                                        "id_acquirente": dati_cliente['id'],
                                        "metodo_pagamento": "ritiro",
                                        "totale_libri": float(sum(float(l.get('prezzo', 0.0) or 0.0) for l in libri_per_ricevuta)),
                                        "rimborso_spese": 0.0,
                                        "totale_complessivo": float(sum(float(l.get('prezzo', 0.0) or 0.0) for l in libri_per_ricevuta)),
                                        "numero_articoli": len(libri_per_ricevuta),
                                        "operatore": st.session_state.get("operatore", "Sconosciuto"),
                                    },
                                )
                            except Exception:
                                pass
                            st.session_state["libri_appena_salvati"] = libri_per_ricevuta
                            st.session_state["numero_ricevuta_ritiro_corrente"] = numero_ricevuta
                            st.session_state["carrello_ritiro"] = []
                            st.success("🎉 Salvato online!")
                            st.rerun()
            with col_svuota:
                if st.button("🗑️ Annulla intero carrello", use_container_width=True):
                    st.session_state["carrello_ritiro"] = []
                    st.session_state["libri_appena_salvati"] = []
                    st.rerun()

        if st.session_state["libri_appena_salvati"]:
            st.markdown("---")
            st.subheader("🖨️ Pannello di Stampa Documenti:")
            
            col_pdf_f, col_pdf_et = st.columns(2)
            with col_pdf_f:
                pdf_f_data = genera_pdf_ricevuta(dati_cliente, st.session_state["libri_appena_salvati"], st.session_state.get("numero_ricevuta_ritiro_corrente"))
                st.download_button(label="📄 SCARICA RICEVUTA COMPLETA A4", data=pdf_f_data, file_name="ricevuta_marconi.pdf", mime="application/pdf", use_container_width=True)
                op_nome = st.session_state.get("operatore", "anon").lower()
                pubblica_ricevuta_online(
                    st,
                    pdf_f_data,
                    "ritiro",
                    dati_cliente,
                    data_riferimento=datetime.date.today().strftime("%Y-%m-%d"),
                    suffisso=f"op-{op_nome}-{len(st.session_state['libri_appena_salvati'])}-libri"
                )
                
            with col_pdf_et:
                pdf_et_data = genera_pdf_rotolo_etichette(st.session_state["libri_appena_salvati"])
                st.download_button(label="🖨️ SCARICA ETICHETTE ADESIVE (TM-L90)", data=pdf_et_data, file_name="rotolo_etichette_marconi.pdf", mime="application/pdf", use_container_width=True)

            st.markdown("---")
            st.write("Stampa subito le etichette con uno dei due metodi disponibili:")
            st.caption("A4: genera un PDF da inviare al foglio adesivo. TM-L90: invia direttamente alla stampante termica Epson.")

            preview_testo = genera_preview_etichette(st.session_state["libri_appena_salvati"])
            if preview_testo:
                with st.expander("👀 Anteprima etichette sullo schermo"):
                    for riga in preview_testo:
                        st.write(riga)

            col_a4, col_tm = st.columns(2)
            with col_a4:
                layout_scelto = st.selectbox(
                    "Seleziona il layout delle etichette A4:",
                    ["Standard (3x8)", "A5 compatibile (2x4)", "Risparmio 10 etichette (2x5)"],
                    index=0,
                    help="Se la tua stampante non trova le etichette, prova il layout compatibile A5 o modifica le misure. Il layout 'Risparmio 10' usa solo 10 etichette per foglio.",
                )
                
                # Soluzione antispreco: posizione di partenza
                max_etichette = 24 if layout_scelto == "Standard (3x8)" else (8 if layout_scelto == "A5 compatibile (2x4)" else 10)
                etichetta_partenza = st.number_input(
                    "♻️ Posizione di partenza (Soluzione Antispreco):",
                    min_value=1,
                    max_value=max_etichette,
                    value=1,
                    help="Se hai un foglio parzialmente usato, inserisci il numero dell'etichetta libera da cui vuoi far partire la stampa (es. se le prime 10 sono già state staccate, inserisci 11). Le etichette precedenti sul foglio verranno lasciate vuote."
                )
                start_idx = etichetta_partenza - 1

                # Pulsante per scaricare il PDF (genera bytes in memoria)
                if st.button("⬇️ SCARICA PDF ETICHETTE (PER STAMPA MANUALE)", use_container_width=True):
                    if layout_scelto == "Standard (3x8)":
                        layout = None
                    elif layout_scelto == "A5 compatibile (2x4)":
                        layout = "a5"
                    else:
                        layout = "10"
                    pdf_bytes = None
                    try:
                        import gestore_etichette as ge
                        importlib.reload(ge)
                        genera_bytes = getattr(ge, "genera_griglia_a4_bytes", None)
                        if genera_bytes is None:
                            raise ImportError("genera_griglia_a4_bytes not found in gestore_etichette")
                        pdf_bytes = genera_bytes(st.session_state["libri_appena_salvati"], layout=layout, start_index=start_idx)
                    except Exception as e:
                        st.error(f"Errore generazione PDF in memoria: {e}")

                    if pdf_bytes:
                        st.download_button(label="⬇️ Scarica PDF etichette", data=pdf_bytes, file_name="etichette_a4_marconi.pdf", mime="application/pdf", use_container_width=True)
                    else:
                        st.warning("Impossibile generare il PDF in memoria; prova a usare il pulsante di stampa per creare il file sul server.")

            with col_tm:
                if st.button("🖨️ STAMPA SULL'ETICHETTRICE TM-L90", use_container_width=True):
                    esito = stampa_etichette_tm_l90(st.session_state["libri_appena_salvati"])
                    if esito:
                        st.success("Etichette inviate alla TM-L90.")
                    else:
                        st.warning("Impossibile inviare le etichette alla TM-L90. Verifica la connessione o il driver.")

    with tab_inventario:
        st.subheader("📚 Elenco Totale delle Copie Fisiche in Magazzino")
        res_copie = requests.get(f"{URL_REST}/copie_libri?select=*", headers=HEADERS)
        res_cat = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo,materia,autore,classi", headers=HEADERS)
        if res_copie.status_code == 200 and res_cat.status_code == 200:
            copie_dati = res_copie.json()
            cat_dati = res_cat.json()
            if len(copie_dati) > 0:
                df_copie = pd.DataFrame(copie_dati)
                df_cat = pd.DataFrame(cat_dati)
                df_totale = pd.merge(df_copie, df_cat, on="isbn", how="left")

                res_cl_all = requests.get(f"{URL_REST}/clienti?select=id,codice_personale", headers=HEADERS)
                if res_cl_all.status_code == 200 and res_cl_all.json():
                    df_cl_all = pd.DataFrame(res_cl_all.json())
                    df_totale = pd.merge(df_totale, df_cl_all, left_on="id_venditore", right_on="id", how="left")
                    df_totale['Codice Etichetta'] = df_totale['codice_personale'].astype(str) + "-" + df_totale['id_libro'].astype(str)
                    df_totale = df_totale[['Codice Etichetta', 'isbn', 'titolo', 'materia', 'prezzo_inserito_mano', 'stato']]
                    df_totale.columns = ['Codice Copertina', 'ISBN', 'Titolo', 'Materia', 'Prezzo Copertina (€)', 'Stato']
                    st.dataframe(df_totale.sort_values(by='Codice Copertina'), use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.subheader("🖨️ Stampa inventario libri in carico (per materia)")
                    st.caption("Genera un PDF dei soli libri 'disponibile' (ancora in carico), raggruppati per materia.")
                    if st.button("🖨️ Genera PDF inventario per materia", use_container_width=True, key="btn_inv_mat"):
                        pdf_inv = genera_pdf_inventario_materia(df_totale)
                        st.download_button(
                            label="⬇️ Scarica PDF Inventario per Materia",
                            data=pdf_inv,
                            file_name="inventario_per_materia.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
            else: 
                st.info("Nessun libro usato presente in magazzino al momento.")
        else: 
            st.error("Errore di sincronizzazione con il server cloud.")

        st.markdown("---")
        st.subheader("🖨️ Ristampa Etichette (filtra e rigenera)")
        st.caption("Usa i filtri per ristampare le etichette, ad esempio se devi rifarle: per singolo venditore, per ISBN o per materia.")
        filtro_tipo = st.radio(
            "Filtra le etichette da ristampare per:",
            ["Tutte le disponibili", "Singolo Venditore (Codice Personale)", "ISBN", "Materia"],
            horizontal=True,
        )
        filtro_val = None
        if filtro_tipo == "Singolo Venditore (Codice Personale)":
            res_v_for = requests.get(f"{URL_REST}/clienti?select=codice_personale", headers=HEADERS)
            lista_cod = [c['codice_personale'] for c in res_v_for.json()] if res_v_for.status_code == 200 else []
            filtro_val = st.selectbox("Scegli il venditore:", [""] + sorted(set(lista_cod)))
        elif filtro_tipo == "ISBN":
            filtro_val = st.text_input("Digita l'ISBN (anche parziale):").strip()
        elif filtro_tipo == "Materia":
            res_m_for = requests.get(f"{URL_REST}/catalogo_libri?select=materia", headers=HEADERS)
            lista_mat = [m['materia'] for m in res_m_for.json() if m.get('materia')] if res_m_for.status_code == 200 else []
            filtro_val = st.selectbox("Scegli la materia:", [""] + sorted(set(lista_mat)))

        if st.button("🖨️ GENERA PDF ETICHETTE FILTRATE", use_container_width=True):
            with st.spinner("Estrazione copie..."):
                query = f"{URL_REST}/copie_libri?select=*"
                if filtro_tipo == "Singolo Venditore (Codice Personale)" and filtro_val:
                    res_v_id = requests.get(f"{URL_REST}/clienti?codice_personale=eq.{filtro_val}&select=id", headers=HEADERS)
                    if res_v_id.status_code == 200 and res_v_id.json():
                        vid = res_v_id.json()[0]['id']
                        query = f"{URL_REST}/copie_libri?id_venditore=eq.{vid}"
                elif filtro_tipo == "ISBN" and filtro_val:
                    query = f"{URL_REST}/copie_libri?isbn=ilike.*{filtro_val}*"
                elif filtro_tipo == "Materia" and filtro_val:
                    res_isbn_m = requests.get(f"{URL_REST}/catalogo_libri?materia=eq.{filtro_val}&select=isbn", headers=HEADERS)
                    isbn_list = [r['isbn'] for r in res_isbn_m.json()] if res_isbn_m.status_code == 200 else []
                    if isbn_list:
                        isbn_filt = ",".join([f"isbn.eq.{i}" for i in isbn_list])
                        query = f"{URL_REST}/copie_libri?or=({isbn_filt})"
                res_copie_f = requests.get(query, headers=HEADERS)
                copie_f = res_copie_f.json() if res_copie_f.status_code == 200 else []
                if not copie_f:
                    st.warning("Nessuna copia corrispondente ai filtri.")
                else:
                    res_cat_f = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo,materia", headers=HEADERS)
                    df_cat_f = pd.DataFrame(res_cat_f.json()) if res_cat_f.status_code == 200 else pd.DataFrame()
                    res_cl_f = requests.get(f"{URL_REST}/clienti?select=id,codice_personale", headers=HEADERS)
                    df_cl_f = pd.DataFrame(res_cl_f.json()) if res_cl_f.status_code == 200 else pd.DataFrame()
                    df_f = pd.DataFrame(copie_f)
                    if not df_cat_f.empty:
                        df_f = df_f.merge(df_cat_f, on="isbn", how="left")
                    if not df_cl_f.empty:
                        df_f = df_f.merge(df_cl_f, left_on="id_venditore", right_on="id", how="left")
                    libri_per_etichette = []
                    for _, r in df_f.iterrows():
                        codice_p = r.get('codice_personale', '')
                        id_l = r.get('id_libro')
                        libri_per_etichette.append({
                            "etichetta": f"{r.get('id_venditore')}-{id_l}",
                            "isbn": r.get('isbn', ''),
                            "titolo": r.get('titolo', r.get('isbn', '')),
                            "prezzo": float(r.get('prezzo_inserito_mano', 0.0) or 0.0),
                            "codice_personale": codice_p,
                            "id_venditore": r.get('id_venditore'),
                            "barcode": f"{r.get('id_venditore')}-{id_l}",
                        })
                    pdf_bytes = None
                    try:
                        import gestore_etichette as ge
                        importlib.reload(ge)
                        genera_bytes = getattr(ge, "genera_griglia_a4_bytes", None)
                        if genera_bytes is None:
                            raise ImportError("genera_griglia_a4_bytes non trovata in gestore_etichette")
                        pdf_bytes = genera_bytes(libri_per_etichette, layout=None, start_index=0)
                    except Exception as e:
                        st.error(f"Errore generazione PDF etichette: {e}")
                    if pdf_bytes:
                        st.download_button(
                            label=f"⬇️ SCARICA PDF ETICHETTE ({len(libri_per_etichette)} etichette)",
                            data=pdf_bytes,
                            file_name="etichette_ristampa.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    else:
                        st.warning("Impossibile generare il PDF delle etichette.")
