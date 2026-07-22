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
from macro_aree import mostra_selector_macro_aree



@st.cache_resource
def get_global_fascicoli():
    """Ritorna un dizionario condiviso in memoria tra tutte le sessioni/utenti."""
    return {}


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


from ricevute_condivise import PROJECT_ID, CHIAVE_SUPABASE
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def _carica_indirizzi_da_secrets():
    """Carica la mappa degli indirizzi di studio da secrets.toml.
    
    Ogni indirizzo (es. 'Logistica_e_Trasporti') contiene la lettera (es. 'L') 
    che identifica le classi di quell'indirizzo (es. 1AL, 1BL, 3AL, 3BL...).
    Se non configurato, restituisce una mappa di default.
    """
    try:
        indirizzi = st.secrets.get("indirizzi", None)
        if indirizzi:
            return dict(indirizzi)
    except Exception:
        pass
    # Fallback di default se non configurato in secrets.toml
    return {
        "Logistica_e_Trasporti": "L",
        "Informatica_e_Telecomunicazioni": "I",
        "Elettronica": "E",
        "Costruzione_del_Mezzo": "C",
        "Costruzione_del_Mezzo_Aereo": "R",
    }



def _costruisci_filtro_area_per_indirizzo(nome_indirizzo):
    """Costruisce il filtro per Supabase a partire dal nome dell'indirizzo.
    
    Ogni indirizzo ha una lettera chiave (es. 'L' per Logistica).
    Cerca tutte le classi che contengono quella lettera, a prescindere dall'anno e dalla sezione.
    Esempio: 'L' trova 1AL, 1BL, 3AL, 3BL...
    """
    indirizzi = _carica_indirizzi_da_secrets()
    chiave = indirizzi.get(nome_indirizzo, "")
    if not chiave:
        return ""
    # Cerca la lettera/chiave all'interno del nome della classe
    return f"classi=ilike.*{chiave}*"



def aggiorna_carrello_ritiro(carrello, libro_selezionato, quantita=1):
    isbn = libro_selezionato.get("isbn")
    titolo = libro_selezionato.get("titolo")
    prevede = libro_selezionato.get("prevede_fascicoli", False)
    totale = libro_selezionato.get("totale_fascicoli", 0)
    consegnati = libro_selezionato.get("fascicoli_consegnati", 0)
    
    for item in carrello:
        if (item.get("isbn") == isbn and 
            item.get("titolo") == titolo and 
            item.get("prevede_fascicoli", False) == prevede and 
            item.get("totale_fascicoli", 0) == totale and 
            item.get("fascicoli_consegnati", 0) == consegnati):
            item["prezzo"] = float(item.get("prezzo", 0.0) or 0.0)
            item["quantita"] = int(item.get("quantita", 1) or 1) + int(quantita or 1)
            return carrello

    carrello.append({
        "isbn": isbn,
        "titolo": titolo,
        "prezzo": float(libro_selezionato.get("prezzo", 0.0) or 0.0),
        "quantita": int(quantita or 1),
        "prevede_fascicoli": prevede,
        "totale_fascicoli": totale,
        "fascicoli_consegnati": consegnati,
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
        titolo_riga = l['titolo'].upper()
        if l.get("prevede_fascicoli", False):
            totale_f = l.get("totale_fascicoli", 0) or 0
            consegnati_f = l.get("fascicoli_consegnati", 0) or 0
            titolo_riga += f" (FASCICOLI: {consegnati_f}/{totale_f})"
        dati_tabella.append([
            Paragraph(l['etichetta'], stile_cella),
            Paragraph(l['isbn'], stile_cella),
            Paragraph(titolo_riga, stile_cella),
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

    from reportlab.platypus import PageBreak

    stile_codice = ParagraphStyle('TermicoCodice', parent=styles['Normal'], fontSize=15, fontName='Helvetica-Bold', alignment=1, leading=17)
    stile_titolo = ParagraphStyle('TermicoTitolo', parent=styles['Normal'], fontSize=8, alignment=1, leading=10, textColor=colors.HexColor("#333333"))
    stile_info = ParagraphStyle('TermicoInfo', parent=styles['Normal'], fontSize=7, alignment=1, leading=9)
    stile_fascicoli = ParagraphStyle('TermicoFascicoli', parent=styles['Normal'], fontSize=7, alignment=1, leading=9, fontName='Helvetica-Bold', textColor=colors.HexColor("#B00000"))

    for i, l in enumerate(libri_ritirati):
        # Inserisce un'interruzione di pagina PRIMA di ogni etichetta successiva alla prima
        if i > 0:
            story.append(PageBreak())
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"<b>{l['etichetta']}</b>", stile_codice))
        story.append(Spacer(1, 2))
        # Codice identificativo della persona (venditore) — richiesto in stampa
        cod_persona = l.get('codice_personale', '')
        if cod_persona:
            story.append(Paragraph(f"Vend: {cod_persona}", stile_info))
        story.append(Paragraph(f"{l['titolo'][:42].upper()}", stile_titolo))
        story.append(Spacer(1, 1))
        story.append(Paragraph(f"ISBN: {l['isbn']}", stile_info))
        # Nuova riga per la colonna fascicoli (se il libro prevede fascicoli)
        if l.get("prevede_fascicoli", False):
            totale = l.get("totale_fascicoli", 0) or 0
            consegnati = l.get("fascicoli_consegnati", 0) or 0
            story.append(Paragraph(f"FASCICOLI: {consegnati}/{totale}", stile_fascicoli))
        story.append(Paragraph("Mercatino Marconi Verona", stile_info))

    if not libri_ritirati:
        # Evita di restituire None in caso di lista vuota
        story.append(Paragraph("Nessun libro", stile_info))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def genera_pdf_inventario_materia(df_totale):
    """Genera un PDF dell'inventario dei libri 'disponibile' (in carico), raggruppati per materia e classe."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    inserisci_intestazione_marconi(story)
    story.append(Paragraph("<b>INVENTARIO LIBRI IN CARICO (per Materia e Classe)</b>", styles['Title']))
    story.append(Paragraph(f"Data: {datetime.date.today().strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 10))

    df_disp = df_totale[df_totale['Stato'] == 'disponibile'].copy()
    if df_disp.empty:
        story.append(Paragraph("Nessun libro in carico (disponibile) al momento.", styles['Normal']))
    else:
        stile_cella = ParagraphStyle('CellaInv', parent=styles['Normal'], fontSize=8, leading=10)
        stile_cella_b = ParagraphStyle('CellaInvB', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')
        
        # Raggruppa per materia
        materie = sorted([m for m in df_disp['Materia'].dropna().astype(str) if m and m.lower() != 'nan']) + ['(senza materia)']
        for mat in materie:
            if mat == '(senza materia)':
                sub_mat = df_disp[df_disp['Materia'].isna() | (df_disp['Materia'].astype(str).str.lower() == 'nan') | (df_disp['Materia'].astype(str) == '')]
            else:
                sub_mat = df_disp[df_disp['Materia'].astype(str) == mat]
            if sub_mat.empty:
                continue
            
            story.append(Paragraph(f"<b>{str(mat).upper()}  —  n. {len(sub_mat)}</b>", styles['Heading3']))
            
            # All'interno della materia, raggruppa per classe
            classi = sorted([c for c in sub_mat['Classe'].dropna().astype(str) if c and c.lower() != 'nan']) + ['(senza classe)']
            for cls in classi:
                if cls == '(senza classe)':
                    sub = sub_mat[sub_mat['Classe'].isna() | (sub_mat['Classe'].astype(str).str.lower() == 'nan') | (sub_mat['Classe'].astype(str) == '')]
                else:
                    sub = sub_mat[sub_mat['Classe'].astype(str) == cls]
                if sub.empty:
                    continue
                
                story.append(Paragraph(f"<i>Classe {cls}  —  n. {len(sub)}</i>", styles['Normal']))
                dati = [[
                    Paragraph("<b>Cod. Copertina</b>", stile_cella_b),
                    Paragraph("<b>Titolo</b>", stile_cella_b),
                    Paragraph("<b>ISBN</b>", stile_cella_b),
                    Paragraph("<b>Prezzo Cop.</b>", stile_cella_b),
                ]]
                for _, r in sub.iterrows():
                    titolo_riga = str(r.get('Titolo', r.get('ISBN', ''))).upper()
                    if r.get('prevede_fascicoli', False):
                        totale_f = int(r.get('totale_fascicoli', 0) or 0)
                        consegnati_f = int(r.get('fascicoli_consegnati', 0) or 0)
                        titolo_riga += f" (FASCICOLI: {consegnati_f}/{totale_f})"
                    dati.append([
                        Paragraph(str(r.get('Codice Copertina', '')), stile_cella),
                        Paragraph(titolo_riga, stile_cella),
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
                story.append(Spacer(1, 6))
            story.append(Spacer(1, 10))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def genera_pdf_inventario_venditore(df_totale):
    """Genera un PDF dell'inventario dei libri 'disponibile' (in carico), raggruppati per venditore (persona)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    inserisci_intestazione_marconi(story)
    story.append(Paragraph("<b>INVENTARIO LIBRI IN CARICO (per Venditore)</b>", styles['Title']))
    story.append(Paragraph(f"Data: {datetime.date.today().strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 10))

    df_disp = df_totale[df_totale['Stato'] == 'disponibile'].copy()
    if df_disp.empty:
        story.append(Paragraph("Nessun libro in carico (disponibile) al momento.", styles['Normal']))
    else:
        stile_cella = ParagraphStyle('CellaInv', parent=styles['Normal'], fontSize=8, leading=10)
        stile_cella_b = ParagraphStyle('CellaInvB', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')
        
        # Raggruppa per codice copertina (che contiene il codice venditore)
        # Estraiamo il codice venditore dalla prima parte del Codice Copertina
        df_disp['Codice Venditore'] = df_disp['Codice Copertina'].astype(str).str.split('-').str[0]
        venditori = sorted(df_disp['Codice Venditore'].dropna().unique())
        
        for cod_vend in venditori:
            sub = df_disp[df_disp['Codice Venditore'] == cod_vend]
            if sub.empty:
                continue
            
            story.append(Paragraph(f"<b>VENDITORE: {cod_vend}  —  n. {len(sub)} libri</b>", styles['Heading3']))
            
            # All'interno del venditore, raggruppa per materia
            materie = sorted([m for m in sub['Materia'].dropna().astype(str) if m and m.lower() != 'nan']) + ['(senza materia)']
            for mat in materie:
                if mat == '(senza materia)':
                    sub_mat = sub[sub['Materia'].isna() | (sub['Materia'].astype(str).str.lower() == 'nan') | (sub['Materia'].astype(str) == '')]
                else:
                    sub_mat = sub[sub['Materia'].astype(str) == mat]
                if sub_mat.empty:
                    continue
                
                story.append(Paragraph(f"<i>{mat}  —  n. {len(sub_mat)}</i>", styles['Normal']))
                dati = [[
                    Paragraph("<b>Cod. Copertina</b>", stile_cella_b),
                    Paragraph("<b>Titolo</b>", stile_cella_b),
                    Paragraph("<b>ISBN</b>", stile_cella_b),
                    Paragraph("<b>Prezzo Cop.</b>", stile_cella_b),
                ]]
                for _, r in sub_mat.iterrows():
                    titolo_riga = str(r.get('Titolo', r.get('ISBN', ''))).upper()
                    if r.get('prevede_fascicoli', False):
                        totale_f = int(r.get('totale_fascicoli', 0) or 0)
                        consegnati_f = int(r.get('fascicoli_consegnati', 0) or 0)
                        titolo_riga += f" (FASCICOLI: {consegnati_f}/{totale_f})"
                    dati.append([
                        Paragraph(str(r.get('Codice Copertina', '')), stile_cella),
                        Paragraph(titolo_riga, stile_cella),
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
                story.append(Spacer(1, 6))
            story.append(Spacer(1, 10))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _selettore_venditore_inline(url_rest, headers):

    """Mostra un selettore venditori con possibilità di crearne uno nuovo inline.
    
    Restituisce il dict del venditore selezionato/creato, oppure None.
    """
    res_clienti = requests.get(f"{url_rest}/clienti?select=id,cognome,nome,codice_personale,telefono,email", headers=headers)
    clienti_list = res_clienti.json() if res_clienti.status_code == 200 else []

    opzioni_clienti = {}
    chiavi_clienti = []

    for c in clienti_list:
        label = f"{c['cognome']} {c['nome']} ({c.get('codice_personale', 'N/D')})"
        opzioni_clienti[label] = c
        chiavi_clienti.append(label)

    if not chiavi_clienti:
        st.warning("⚠️ Nessun cliente presente. Registra un nuovo cliente per procedere.")
        with st.expander("➕ Registra Nuovo Cliente", expanded=True):
            return _form_nuovo_venditore(url_rest, headers)

    opzioni_con_crea = ["➕ Crea nuovo cliente..."] + chiavi_clienti

    index_venditore = 0
    if "id_venditore_corrente" in st.session_state:
        for idx, key in enumerate(chiavi_clienti):
            if opzioni_clienti.get(key, {}).get("id") == st.session_state["id_venditore_corrente"]:
                index_venditore = idx + 1
                break

    scelta = st.selectbox(
        "Seleziona il Cliente / Venditore (o creane uno nuovo)",
        opzioni_con_crea,
        index=index_venditore,
        key="select_venditore_ritiro",
        help="Scegli un cliente esistente o seleziona 'Crea nuovo cliente...' per registrarne uno.",
    )

    if scelta == "➕ Crea nuovo cliente...":
        with st.expander("➕ Registra Nuovo Cliente", expanded=True):
            return _form_nuovo_venditore(url_rest, headers)
    else:
        cliente = opzioni_clienti[scelta]
        st.session_state["id_venditore_corrente"] = cliente["id"]
        return cliente


def _form_nuovo_venditore(url_rest, headers):
    """Mostra un form per registrare un nuovo venditore e lo salva su Supabase."""
    import random, string
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome *", key="nuovo_nome_ritiro").strip()
        cognome = st.text_input("Cognome *", key="nuovo_cognome_ritiro").strip()
    with col2:
        telefono = st.text_input("Telefono *", key="nuovo_tel_ritiro").strip()
        email = st.text_input("Email", key="nuovo_email_ritiro").strip().lower()

    if st.button("💾 Salva e seleziona questo cliente", key="salva_nuovo_cliente_ritiro"):
        if not nome or not cognome or not telefono:
            st.error("Nome, Cognome e Telefono sono obbligatori.")
            return None
        lettere = ''.join(random.choices(string.ascii_uppercase, k=2))
        codice = f"{cognome[:3].upper()}{nome[:2].upper()}{lettere}"
        payload = {
            "codice_personale": codice,
            "nome": nome,
            "cognome": cognome,
            "telefono": telefono,
            "email": email,
        }
        try:
            r = requests.post(f"{url_rest}/clienti", headers=headers, json=payload)
            if r.status_code < 400:
                nuovo = r.json()
                if isinstance(nuovo, list) and len(nuovo) > 0:
                    nuovo = nuovo[0]
                st.success(f"✅ Cliente {cognome} {nome} registrato con codice {codice}!")
                st.session_state["id_venditore_corrente"] = nuovo["id"]
                st.rerun()
                return nuovo
            else:
                st.error(f"Errore salvataggio: {r.text}")
        except Exception as e:
            st.error(f"Errore: {e}")
        return None
    return None


def mostra_pagina():
    st.header("📥 Presa in Carico e Ritiro Libri Usati")
    tab_ritiro, tab_inventario, tab_ristampa = st.tabs(["Prendi in Carico Libri", "📋 Inventario Generale Magazzino", "🖨️ Ristampa Etichette"])



    
    if "carrello_ritiro" not in st.session_state:
        st.session_state["carrello_ritiro"] = []
    if "libri_appena_salvati" not in st.session_state:
        st.session_state["libri_appena_salvati"] = []
        
    with tab_ritiro:
        # Selezione venditore (con possibilità di crearne uno nuovo inline)
        dati_cliente = _selettore_venditore_inline(URL_REST, HEADERS)
        if dati_cliente is None:
            st.info("Seleziona o registra un cliente per iniziare il ritiro.")
            return

        st.session_state["id_venditore_corrente"] = dati_cliente["id"]

        # Mostra i dati del venditore selezionato
        st.info(
            f"👤 **Venditore selezionato:** {dati_cliente['cognome']} {dati_cliente['nome']}  \n"
            f"🆔 Codice: `{dati_cliente['codice_personale']}`  \n"
            f"📞 Tel: {dati_cliente.get('telefono', 'N.D.')}  \n"
            f"✉️ Email: {dati_cliente.get('email', 'N.D.')}"
        )

        
        st.markdown("---")
        st.caption("🔍 Scrivi qui sotto: riconosco da solo se e' un ISBN, un titolo/autore o una classe (es. 1AI). Nessun pallino da cliccare.")
        ricerca_unica = st.text_input(
            "Cerca per ISBN, Titolo/Autore o Classe (es. 978880... , 'Matematica 1', '1AI'):",
            key="ricerca_unica_ritiro",
        ).strip()

        libri_trovati = []
        if ricerca_unica:
            # Riconoscimento automatico del tipo di ricerca
            solo_cifre = ricerca_unica.replace("-", "").replace(" ", "").isdigit()
            sembra_classe = (
                len(ricerca_unica) <= 6
                and any(ch.isdigit() for ch in ricerca_unica)
                and any(ch.isalpha() for ch in ricerca_unica)
            )
            if solo_cifre or (len(ricerca_unica) >= 8 and ricerca_unica.replace("-", "").replace(" ", "").isdigit()):
                # ISBN / codice numerico
                libri_trovati = _cerca_isbn_ritiro(ricerca_unica)
                if not libri_trovati:
                    st.error("❌ Nessun libro trovato con questo frammento di ISBN.")
            elif sembra_classe:
                classe_input = ricerca_unica.upper()
                # Estrae il numero dell'anno (prima cifra) dalla classe, es. "1AI" → "1", "3CL" → "3"
                anno_classe = classe_input[0] if classe_input and classe_input[0].isdigit() else ""
                if anno_classe in ("1", "3"):
                    mostra_selector_macro_aree(anno_classe, URL_REST, HEADERS)



                libri_trovati = _cerca_classe_ritiro(classe_input)
                if not libri_trovati: st.warning(f"Nessun libro censito specificamente per la classe {classe_input}.")
            else:
                # Titolo o autore
                testo = ricerca_unica.lower()
                if len(testo) >= 3:
                    libri_trovati = _cerca_testo_ritiro(testo)
                    if not libri_trovati: st.error("❌ Nessun volume trovato nel catalogo adozioni.")
                else:
                    st.info("Digita almeno 3 caratteri per la ricerca per titolo/autore.")

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
            
            # --- SEZIONE GESTIONE FASCICOLI ---
            isbn_corrente = libro_selezionato_dati.get('isbn')
            
            # Recupera memoria globale dei fascicoli condivisa tra tutte le sessioni/utenti
            global_fasc = get_global_fascicoli()
            mem_fasc = global_fasc.get(isbn_corrente, {})

            st.markdown("##### 📁 Gestione Fascicoli Allegati")
            
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

            is_admin_user = _is_admin()
            
            if is_admin_user:
                prevede_fascicoli = st.checkbox(
                    "Questo testo prevede dei fascicoli allegati? (Abilitato solo per Admin)",
                    value=mem_fasc.get("prevede", False),
                    key=f"input_prevede_fascicoli_{isbn_corrente}",
                )
                totale_fascicoli = 0
                fascicoli_consegnati = 0
                if prevede_fascicoli:
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        totale_fascicoli = st.number_input(
                            "Numero totale di fascicoli previsti:",
                            min_value=1,
                            value=mem_fasc.get("totale", 1) or 1,
                            step=1,
                            key=f"input_totale_fascicoli_{isbn_corrente}",
                        )
                    with col_f2:
                        # L'utente/operatore inserisce solo i fascicoli portati al momento
                        fascicoli_consegnati = st.number_input(
                            "Numero di fascicoli CONSEGNATI al momento:",
                            min_value=0,
                            max_value=totale_fascicoli,
                            value=0,
                            step=1,
                            key=f"input_fascicoli_consegnati_{isbn_corrente}",
                        )
                
                # Salviamo sempre in memoria globale la definizione
                global_fasc[isbn_corrente] = {
                    "prevede": prevede_fascicoli,
                    "totale": totale_fascicoli,
                }
            else:
                # Per utenti non-admin, visualizziamo la scelta pre-inserita in sola lettura
                prevede_fascicoli = mem_fasc.get("prevede", False)
                totale_fascicoli = mem_fasc.get("totale", 0)
                fascicoli_consegnati = 0
                
                if prevede_fascicoli:
                    st.warning(f"📋 Questo testo prevede **{totale_fascicoli}** fascicoli allegati in totale (definito dall'Amministratore).")
                    fascicoli_consegnati = st.number_input(
                        "Numero di fascicoli CONSEGNATI al momento:",
                        min_value=0,
                        max_value=totale_fascicoli,
                        value=0,
                        step=1,
                        key=f"input_fascicoli_consegnati_{isbn_corrente}",
                    )
                else:
                    st.info("ℹ️ Nessun fascicolo allegato previsto per questo testo dall'Amministratore.")
            
            if st.button("➕ INSERISCI QUESTO TITOLO NEL CARRELLO DI RITIRO", use_container_width=True):
                # Salviamo sempre in memoria globale se admin
                if is_admin_user:
                    global_fasc[isbn_corrente] = {
                        "prevede": prevede_fascicoli,
                        "totale": totale_fascicoli,
                    }
                aggiorna_carrello_ritiro(
                    st.session_state["carrello_ritiro"],
                    {
                        "isbn": libro_selezionato_dati['isbn'],
                        "titolo": libro_selezionato_dati['titolo'],
                        "prezzo": prezzo_inserito,
                        "prevede_fascicoli": prevede_fascicoli,
                        "totale_fascicoli": totale_fascicoli,
                        "fascicoli_consegnati": fascicoli_consegnati,
                        "volume": libro_selezionato_dati.get("volume") or libro_selezionato_dati.get("classi", ""),
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
                            # Supporto quantità reale: esegue l'inserimento per il numero di copie richiesto
                            for _ in range(int(item.get("quantita", 1))):
                                dati_invio = {
                                    "isbn": item['isbn'], 
                                    "id_venditore": dati_cliente['id'], 
                                    "stato": "disponibile", 
                                    "prezzo_inserito_mano": item['prezzo'],
                                    "operatore": st.session_state.get("operatore", "Sconosciuto"),
                                    "prevede_fascicoli": item.get("prevede_fascicoli", False),
                                    "totale_fascicoli": int(item.get("totale_fascicoli", 0)),
                                    "fascicoli_consegnati": int(item.get("fascicoli_consegnati", 0)),
                                }
                                res_ins = requests.post(f"{URL_REST}/copie_libri", headers=HEADERS, json=dati_invio)
                                
                                # Robustezza Fallback: se la colonna operatore o i campi fascicoli non esistono ancora su DB, riprova escludendoli
                                if res_ins.status_code >= 400:
                                    # Rimuoviamo i campi opzionali se il server ha rifiutato la richiesta
                                    dati_invio.pop("operatore", None)
                                    dati_invio.pop("prevede_fascicoli", None)
                                    dati_invio.pop("totale_fascicoli", None)
                                    dati_invio.pop("fascicoli_consegnati", None)
                                    res_ins = requests.post(f"{URL_REST}/copie_libri", headers=HEADERS, json=dati_invio)
                                
                                if res_ins.status_code < 400:
                                    risposta_server = res_ins.json()
                                    
                                    if isinstance(risposta_server, list) and len(risposta_server) > 0:
                                        dati_copia = risposta_server[0]
                                    else:
                                        dati_copia = risposta_server
                                        
                                    id_generato = dati_copia['id_libro']
                                    barcode_val = f"{dati_cliente.get('codice_personale')}-{id_generato}"

                                    
                                    # Annotazione dei dettagli dei fascicoli nel titolo per la ricevuta cartacea/PDF
                                    titolo_completo = item['titolo']
                                    if item.get("prevede_fascicoli", False):
                                        titolo_completo += f" (Fascicoli: {item.get('fascicoli_consegnati', 0)}/{item.get('totale_fascicoli', 0)})"
                                        
                                    libri_per_ricevuta.append({
                                        "etichetta": barcode_val,
                                        "isbn": item['isbn'], 
                                        "titolo": titolo_completo, 
                                        "prezzo": item['prezzo'],
                                        "codice_personale": dati_cliente['codice_personale'],
                                        "id_venditore": dati_cliente.get('id'),
                                        "barcode": barcode_val,
                                        "prevede_fascicoli": item.get("prevede_fascicoli", False),
                                        "totale_fascicoli": item.get("totale_fascicoli", 0),
                                        "fascicoli_consegnati": item.get("fascicoli_consegnati", 0),
                                        "volume": item.get("volume", ""),
                                    })


                                    
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
                if pdf_f_data is None:
                    st.error("⚠️ Impossibile generare il PDF della ricevuta.")
                else:
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
                if pdf_et_data is None:
                    st.error("⚠️ Impossibile generare il PDF delle etichette.")
                else:
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
                st.markdown("**Layout etichette A4 (per stampa manuale su un'altra stampante)**")
                layout_scelto = st.selectbox(
                    "Scegli il layout:",
                    ["Standard (3x8)", "A5 compatibile (2x4)", "Risparmio 10 etichette (2x5)", "Personalizzato (dimensioni foglio + n. etichette)"],
                    index=0,
                    help="Se la tua stampante non trova le etichette, prova il layout compatibile A5, il risparmio 10 o il layout personalizzato inserendo le misure del tuo foglio.",
                )

                layout = None
                max_etichette = 24
                if layout_scelto == "Standard (3x8)":
                    layout = None
                    max_etichette = 24
                elif layout_scelto == "A5 compatibile (2x4)":
                    layout = "a5"
                    max_etichette = 8
                elif layout_scelto == "Risparmio 10 etichette (2x5)":
                    layout = "10"
                    max_etichette = 10
                else:
                    # Layout personalizzato: l'utente inserisce foglio + totale etichette
                    c_f1, c_f2 = st.columns(2)
                    with c_f1:
                        foglio_l = st.number_input("Larghezza foglio (mm)", min_value=50.0, max_value=500.0, value=210.0, step=1.0)
                        foglio_h = st.number_input("Altezza foglio (mm)", min_value=50.0, max_value=500.0, value=297.0, step=1.0)
                    with c_f2:
                        tot_etichette = st.number_input("Numero TOTALE etichette sul foglio", min_value=1, max_value=400, value=24, step=1)
                    # Calcola automaticamente colonne/righe e dimensione etichetta
                    try:
                        import gestore_etichette as ge
                        importlib.reload(ge)
                        layout = ge.calcola_layout_personalizzato(foglio_l, foglio_h, tot_etichette)
                        max_etichette = tot_etichette
                        st.caption(f"Calcolato: {layout['colonne']} colonne x {layout['righe']} righe | etichetta {layout['larghezza_etichetta_mm']:.0f}x{layout['altezza_etichetta_mm']:.0f} mm")
                    except Exception as e:
                        st.error(f"Errore calcolo layout: {e}")
                        layout = None

                # Soluzione antispreco: posizione di partenza
                etichetta_partenza = st.number_input(
                    "♫️ Posizione di partenza (Soluzione Antispreco):",
                    min_value=1,
                    max_value=max_etichette,
                    value=1,
                    help="Se hai un foglio parzialmente usato, inserisci il numero dell'etichetta libera da cui vuoi far partire la stampa (es. se le prime 10 sono gia' state staccate, inserisci 11). Le etichette precedenti sul foglio verranno lasciate vuote."
                )
                start_idx = etichetta_partenza - 1

                # Pulsante per scaricare il PDF (genera bytes in memoria)
                if st.button("⬇️ SCARICA PDF ETICHETTE (PER STAMPA MANUALE)", use_container_width=True):
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
                        st.session_state["pdf_etichette_a4"] = pdf_bytes
                    else:
                        st.session_state["pdf_etichette_a4"] = None
                        st.warning("Impossibile generare il PDF in memoria; prova a usare il pulsante di stampa per creare il file sul server.")

                # Il download button vive fuori dal blocco del button per non scomparire al rerun
                if st.session_state.get("pdf_etichette_a4"):
                    st.download_button(label="⬇️ Scarica PDF etichette", data=st.session_state["pdf_etichette_a4"], file_name="etichette_a4_marconi.pdf", mime="application/pdf", use_container_width=True)

            with col_tm:
                if st.button("🖨️ STAMPA SULL'ETICHETTRICE TM-L90", use_container_width=True):
                    esito = stampa_etichette_tm_l90(st.session_state["libri_appena_salvati"])
                    if esito:
                        st.success("Etichette inviate alla TM-L90.")
                    else:
                        st.warning("Impossibile inviare le etichette alla TM-L90. Verifica la connessione o il driver.")

    with tab_inventario:
        st.subheader("📚 Elenco Totale delle Copie Fisiche in Magazzino")
        st.caption("Clicca il pulsante per caricare l'inventario dal database (solo quando ti serve).")
        
        if st.button("📥 CARICA INVENTARIO", use_container_width=True, key="btn_carica_inventario"):
            with st.spinner("Caricamento inventario in corso..."):
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
                            df_totale = df_totale[['Codice Etichetta', 'isbn', 'titolo', 'materia', 'classi', 'prezzo_inserito_mano', 'stato']]
                            df_totale.columns = ['Codice Copertina', 'ISBN', 'Titolo', 'Materia', 'Classe', 'Prezzo Copertina (€)', 'Stato']
                            st.session_state["df_inventario"] = df_totale
                            st.success(f"✅ Inventario caricato: {len(df_totale)} copie totali.")
                        else:
                            st.warning("Impossibile caricare i dati dei clienti.")
                    else: 
                        st.info("Nessun libro usato presente in magazzino al momento.")
                else: 
                    st.error("Errore di sincronizzazione con il server cloud.")
        
        # Mostra l'inventario se già caricato in sessione
        if "df_inventario" in st.session_state and st.session_state["df_inventario"] is not None:
            df_totale = st.session_state["df_inventario"]
            st.dataframe(df_totale.sort_values(by='Codice Copertina'), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🖨️ Stampa inventario")
            st.caption("Genera un PDF dei soli libri 'disponibile' (ancora in carico).")
            
            # Selettore per scegliere una singola materia
            materie_disponibili = sorted([m for m in df_totale['Materia'].dropna().astype(str) if m and m.lower() != 'nan'])
            materia_scelta = st.selectbox(
                "Filtra per materia (opzionale - seleziona 'Tutte' per includerle tutte):",
                ["Tutte"] + materie_disponibili,
                key="sel_materia_inventario"
            )
            
            if materia_scelta != "Tutte":
                df_filtrato = df_totale[df_totale['Materia'].astype(str) == materia_scelta].copy()
            else:
                df_filtrato = df_totale.copy()
            
            col_pdf1, col_pdf2 = st.columns(2)
            with col_pdf1:
                if st.button("📚 PDF per MATERIA e CLASSE (1°, 2°, 3°...)", use_container_width=True, key="btn_inv_mat_classe"):
                    pdf_inv = genera_pdf_inventario_materia(df_filtrato)
                    st.download_button(
                        label="⬇️ Scarica PDF per Materia e Classe",
                        data=pdf_inv,
                        file_name="inventario_per_materia_classe.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            with col_pdf2:
                if st.button("👤 PDF per VENDITORE (persona)", use_container_width=True, key="btn_inv_venditore"):
                    pdf_inv = genera_pdf_inventario_venditore(df_filtrato)
                    st.download_button(
                        label="⬇️ Scarica PDF per Venditore",
                        data=pdf_inv,
                        file_name="inventario_per_venditore.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )




    with tab_ristampa:
        st.subheader("🖨️ Ristampa Etichette (filtra e rigenera)")
        st.caption("Usa i filtri per ristampare le etichette, ad esempio se devi rifarle: per singolo venditore, per ISBN o per materia.")
        
        filtro_tipo = st.radio(
            "Filtra le etichette da ristampare per:",
            ["Tutte le disponibili", "Singolo Venditore (Codice Personale)", "ISBN", "Materia"],
            horizontal=True,
            key="filtro_tipo_ristampa"
        )
        
        filtro_val = None
        if filtro_tipo == "Singolo Venditore (Codice Personale)":
            filtro_val = st.text_input("Inserisci il Codice Personale del venditore (es. MAR10):", key="txt_cod_vend_ristampa").strip()
        elif filtro_tipo == "ISBN":
            filtro_val = st.text_input("Digita l'ISBN (anche parziale):", key="txt_isbn_ristampa").strip()
        elif filtro_tipo == "Materia":
            filtro_val = st.text_input("Inserisci il nome della materia (es. Matematica):", key="txt_mat_ristampa").strip()

        if st.button("🖨️ GENERA PDF ETICHETTE FILTRATE", use_container_width=True, key="btn_gen_ristampa"):
            with st.spinner("Estrazione copie..."):
                try:
                    query = f"{URL_REST}/copie_libri?select=*"
                    if filtro_tipo == "Singolo Venditore (Codice Personale)" and filtro_val:
                        res_v_id = requests.get(f"{URL_REST}/clienti?codice_personale=eq.{filtro_val}&select=id", headers=HEADERS, timeout=10)
                        if res_v_id.status_code == 200 and res_v_id.json():
                            vid = res_v_id.json()[0]['id']
                            query = f"{URL_REST}/copie_libri?id_venditore=eq.{vid}"
                    elif filtro_tipo == "ISBN" and filtro_val:
                        query = f"{URL_REST}/copie_libri?isbn=ilike.*{filtro_val}*"
                    elif filtro_tipo == "Materia" and filtro_val:
                        res_isbn_m = requests.get(f"{URL_REST}/catalogo_libri?materia=ilike.*{filtro_val}*&select=isbn", headers=HEADERS, timeout=10)
                        isbn_list = [r['isbn'] for r in res_isbn_m.json()] if res_isbn_m.status_code == 200 else []
                        if isbn_list:
                            isbn_filt = ",".join([f"isbn.eq.{i}" for i in isbn_list])
                            query = f"{URL_REST}/copie_libri?or=({isbn_filt})"
                    
                    res_copie_f = requests.get(query, headers=HEADERS, timeout=15)
                    copie_f = res_copie_f.json() if res_copie_f.status_code == 200 else []
                    
                    if not copie_f:
                        st.warning("Nessuna copia corrispondente ai filtri.")
                    else:
                        res_cat_f = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo,materia", headers=HEADERS, timeout=10)
                        df_cat_f = pd.DataFrame(res_cat_f.json()) if res_cat_f.status_code == 200 else pd.DataFrame()
                        res_cl_f = requests.get(f"{URL_REST}/clienti?select=id,codice_personale", headers=HEADERS, timeout=10)
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
                            barcode_val = f"{codice_p}-{id_l}" if codice_p else str(id_l)
                            libri_per_etichette.append({
                                "etichetta": barcode_val,
                                "isbn": r.get('isbn', ''),
                                "titolo": r.get('titolo', r.get('isbn', '')),
                                "prezzo": float(r.get('prezzo_inserito_mano', 0.0) or 0.0),
                                "codice_personale": codice_p,
                                "id_venditore": r.get('id_venditore'),
                                "barcode": barcode_val,
                                "prevede_fascicoli": bool(r.get('prevede_fascicoli', False)),
                                "totale_fascicoli": int(r.get('totale_fascicoli', 0) or 0),
                                "fascicoli_consegnati": int(r.get('fascicoli_consegnati', 0) or 0),
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
                            st.session_state["pdf_etichette_ristampa"] = pdf_bytes
                            st.download_button(
                                label=f"⬇️ SCARICA PDF ETICHETTE ({len(libri_per_etichette)} etichette)",
                                data=pdf_bytes,
                                file_name="etichette_ristampa.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key="dl_ristampa"
                            )
                        else:
                            st.warning("Impossibile generare il PDF delle etichette.")
                except Exception as e:
                    st.error(f"Errore durante l'estrazione delle copie: {e}")






