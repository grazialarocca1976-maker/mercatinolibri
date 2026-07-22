"""Modulo condiviso per la gestione delle macro-aree (indirizzi di studio).

Legge la configurazione da secrets.toml e fornisce funzioni per:
- Caricare la mappa degli indirizzi
- Costruire filtri per Supabase
- Mostrare il selettore delle macro-aree in qualsiasi pagina
- Stampare l'elenco dei libri di un'area in PDF
"""

import streamlit as st
import pandas as pd
import requests
import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm


def carica_indirizzi_da_secrets():
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


def costruisci_filtro_area_per_indirizzo(nome_indirizzo, anno_classe="1"):
    """Costruisce il filtro per Supabase a partire dal nome dell'indirizzo.
    
    Ogni indirizzo ha una lettera chiave (es. 'L' per Logistica).
    Cerca le classi che contengono quella lettera per l'anno specificato.
    Esempio: per 'L' e anno 1 cerca "*1_L*" che matcha "1AL", "1BL", "1CL"...
    Esempio: per 'L' e anno 3 cerca "*3_L*" che matcha "3AL", "3BL", "3CL"...
    
    Args:
        nome_indirizzo: Nome dell'indirizzo (es. "Logistica_e_Trasporti")
        anno_classe: "1" o "3" (anno da cercare)
    
    Returns:
        Lista di tuple (nome_param, valore_param) per fare chiamate separate
    """
    indirizzi = carica_indirizzi_da_secrets()
    chiave = indirizzi.get(nome_indirizzo, "")
    if not chiave:
        return ""
    # Le classi sono nel formato "1AL TRASPORTI E LOGISTICA", "1AI INFORMATICA E TELECOMUNICAZIONI"
    # Cerchiamo pattern come "*1_L*" (numero + underscore + lettera chiave) usando * come wildcard
    # Solo per l'anno specificato (1° o 3°)
    # Esempio: per 'L' e anno 1 cerca "*1_L*" che matcha "1AL", "1BL", "1CL" ecc.
    # Esempio: per 'I' e anno 3 cerca "*3_I*" che matcha "3AI", "3BI", "3CI" ecc.
    return [("classi", f"ilike.*{anno_classe}_{chiave}*")]


def _genera_pdf_macro_area(libri, nome_area, anno_classe):
    """Genera un PDF con l'elenco dei libri di una macro-area."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25)
    story = []
    styles = getSampleStyleSheet()
    
    # Intestazione
    stile_titolo = ParagraphStyle('TitoloArea', parent=styles['Title'], fontSize=16, spaceAfter=4)
    story.append(Paragraph(f"<b>MACRO-AREA: {nome_area}</b>", stile_titolo))
    stile_sottotitolo = ParagraphStyle('SottoTitolo', parent=styles['Normal'], fontSize=10, textColor=colors.grey, spaceAfter=12)
    story.append(Paragraph(f"Classi {anno_classe}ª · Elenco libri adottati · Generato il {datetime.date.today().strftime('%d/%m/%Y')}", stile_sottotitolo))
    
    # Tabella
    stile_cella = ParagraphStyle('Cella', parent=styles['Normal'], fontSize=8, leading=10)
    stile_cella_b = ParagraphStyle('CellaB', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')
    
    dati_tabella = [[
        Paragraph("<b>ISBN</b>", stile_cella_b),
        Paragraph("<b>Titolo</b>", stile_cella_b),
        Paragraph("<b>Classi</b>", stile_cella_b),
        Paragraph("<b>Prezzo (€)</b>", stile_cella_b),
    ]]
    
    for _, libro in libri.iterrows():
        dati_tabella.append([
            Paragraph(str(libro.get('ISBN', '')), stile_cella),
            Paragraph(str(libro.get('Titolo Volume Scolastico', '')).upper(), stile_cella),
            Paragraph(str(libro.get('Classi Adottanti', '')), stile_cella),
            Paragraph(f"€{float(libro.get('Prezzo (€)', 0) or 0):.2f}", stile_cella),
        ])
    
    # Riga totale
    totale = sum(float(libro.get('Prezzo (€)', 0) or 0) for _, libro in libri.iterrows())
    dati_tabella.append([
        Paragraph("<b>TOTALE</b>", stile_cella_b),
        "",
        Paragraph(f"<b>{len(libri)} libri</b>", stile_cella_b),
        Paragraph(f"<b>€{totale:.2f}</b>", stile_cella_b),
    ])
    
    tabella = Table(dati_tabella, colWidths=[100, 280, 80, 70])
    tabella.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6b4423')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#6b4423')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.append(tabella)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def mostra_selector_macro_aree(anno_classe, url_rest, headers):
    """Mostra il selettore delle macro-aree e restituisce i libri trovati (o None).
    
    Cerca nel CATALOGO (non nelle copie in possesso) tutti i libri
    il cui campo 'classi' contiene la lettera chiave dell'indirizzo.
    
    Args:
        anno_classe: "1", "3", ecc. (prima cifra della classe)
        url_rest: URL base di Supabase REST
        headers: Headers per le richieste HTTP
    
    Returns:
        DataFrame con i libri trovati, oppure None
    """
    if anno_classe not in ("1", "3"):
        return None
    
    indirizzi_config = carica_indirizzi_da_secrets()
    opzioni_area = ["-- Seleziona Area --"]
    for nome_indirizzo, chiave in indirizzi_config.items():
        nome_leggibile = nome_indirizzo.replace("_", " ")
        opzioni_area.append(f"Area {nome_leggibile} (chiave: {chiave})")
    
    area_scelta = st.selectbox("Scegli l'area dei corsi:", opzioni_area, key=f"macro_area_{anno_classe}")
    
    # Stato per memorizzare i risultati
    stato_key = f"macro_df_{anno_classe}"
    stato_nome_key = f"macro_nome_{anno_classe}"
    
    if st.button(f"🔍 Cerca libri Classi {anno_classe}ª", key=f"btn_macro_{anno_classe}", use_container_width=True):
        filtro_area = ""
        nome_area_trovata = ""
        for nome_indirizzo in indirizzi_config:
            nome_leggibile = nome_indirizzo.replace("_", " ")
            if nome_leggibile in area_scelta:
                filtro_area = costruisci_filtro_area_per_indirizzo(nome_indirizzo, anno_classe)
                nome_area_trovata = nome_leggibile
                break
        
        if filtro_area:
            try:
                # Cerca nel CATALOGO (non nelle copie) tutti i libri per quell'indirizzo
                # filtro_area è una lista di tuple (nome_param, valore_param)
                # Facciamo una chiamata per il filtro dell'anno specificato
                libri_area_list = []
                isbn_visti = set()
                for nome_param, valore_param in filtro_area:
                    params = {
                        nome_param: valore_param,
                        "select": "isbn,titolo,classi,prezzo_copertina",
                        "order": "titolo.asc",
                    }
                    r = requests.get(
                        f"{url_rest}/catalogo_libri",
                        headers=headers,
                        params=params,
                        timeout=15,
                    )
                    if r.status_code == 200:
                        for libro in r.json():
                            if libro.get("isbn") not in isbn_visti:
                                isbn_visti.add(libro.get("isbn"))
                                libri_area_list.append(libro)
            except Exception:
                libri_area_list = []
            
            if libri_area_list:
                df_area = pd.DataFrame(libri_area_list)
                df_area.columns = ['ISBN', 'Titolo Volume Scolastico', 'Classi Adottanti', 'Prezzo (€)']
                st.session_state[stato_key] = df_area
                st.session_state[stato_nome_key] = nome_area_trovata
            else:
                st.session_state[stato_key] = None
                st.session_state[stato_nome_key] = ""
                st.info("Nessun libro presente nel catalogo per questa macro-area.")
        else:
            st.warning("Seleziona un'area valida.")
    
    # Mostra risultati se presenti in sessione
    if stato_key in st.session_state and st.session_state[stato_key] is not None:
        df_area = st.session_state[stato_key]
        nome_area = st.session_state.get(stato_nome_key, "")
        
        st.markdown(f"**{len(df_area)} libri trovati per {nome_area} (Classi {anno_classe}ª)**")
        st.dataframe(df_area, use_container_width=True, hide_index=True)
        
        # Pulsante per stampare PDF
        if st.button(f"🖨️ Stampa PDF {nome_area} Classi {anno_classe}ª", key=f"btn_pdf_macro_{anno_classe}", use_container_width=True):
            with st.spinner("Generazione PDF..."):
                pdf_bytes = _genera_pdf_macro_area(df_area, nome_area, anno_classe)
                if pdf_bytes:
                    st.download_button(
                        label="📥 Scarica PDF",
                        data=pdf_bytes,
                        file_name=f"macro_area_{nome_area.replace(' ', '_')}_classi_{anno_classe}a.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_macro_{anno_classe}"
                    )
        
        return df_area
    
    return None
