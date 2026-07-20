import importlib
import streamlit as st
import pandas as pd
import requests
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
# ==========================================
# 🆕 AGGIUNGI QUESTI IMPORT PER I CODICI A BARRE
# ==========================================
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def format_date_for_db(data):
    if not data:
        return ""
    if isinstance(data, datetime.date):
        return data.strftime("%Y-%m-%d")
    if isinstance(data, str):
        testo = data.strip()
        if not testo:
            return ""
        if len(testo) == 10 and testo[4] == "-" and testo[7] == "-":
            return testo
        if len(testo) == 10 and testo[2] == "/" and testo[5] == "/":
            return datetime.datetime.strptime(testo, "%d/%m/%Y").strftime("%Y-%m-%d")
        try:
            return datetime.datetime.fromisoformat(testo).strftime("%Y-%m-%d")
        except ValueError:
            return testo
    return str(data)


# --- FUNZIONI CON CACHE PER VELOCIZZARE LA CASSA ---
@st.cache_data(show_spinner=False, ttl=30)
def _carica_clienti_cassa():
    r = requests.get(f"{URL_REST}/clienti?select=id,codice_personale,nome,cognome,telefono,email", headers=HEADERS)
    return r.json() if r.status_code == 200 else []


@st.cache_data(show_spinner=False, ttl=15)
def _carica_copie_cassa():
    r = requests.get(f"{URL_REST}/copie_libri?select=*", headers=HEADERS)
    return r.json() if r.status_code == 200 else []


@st.cache_data(show_spinner=False, ttl=60)
def _carica_catalogo_cassa():
    r = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo,prezzo_copertina", headers=HEADERS)
    return r.json() if r.status_code == 200 else []


def format_date_for_display(data):
    if not data:
        return ""
    if isinstance(data, datetime.date):
        return data.strftime("%d/%m/%Y")
    if isinstance(data, str):
        testo = data.strip()
        if not testo:
            return ""
        if len(testo) == 10 and testo[2] == "/" and testo[5] == "/":
            return testo
        if len(testo) == 10 and testo[4] == "-" and testo[7] == "-":
            return datetime.datetime.strptime(testo, "%Y-%m-%d").strftime("%d/%m/%Y")
        try:
            return datetime.datetime.fromisoformat(testo).strftime("%d/%m/%Y")
        except ValueError:
            return testo
    return str(data)


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
    # Fallback: contatore di sessione per tipo
    key = f"num_ricevute_{tipo}"
    if key not in st.session_state:
        st.session_state[key] = 0
    st.session_state[key] += 1
    return st.session_state[key]


def calcola_prezzo_vendita_scontato(prezzo_base, sconto_fascicoli=0.0):
    """Prezzo di vendita = (prezzo_base - sconto_fascicoli) / 2.
    Il rimborso spese di 0,50 € è una voce a parte nella ricevuta."""
    prezzo_base_scontato = max(float(prezzo_base) - float(sconto_fascicoli), 0.0)
    return prezzo_base_scontato / 2


def genera_pdf_vendita_multipla(dati_acquirente, libri_venduti, totale_complessivo, modalita_paga, numero_ricevuta=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    inserisci_intestazione_marconi(story)
    story.append(Paragraph(f"<b>RICEVUTA DI ACQUISTO LIBRI USATI</b>", styles['Title']))
    # Numero ricevuta grande e in alto a destra
    stile_num = ParagraphStyle('NumRicevuta', parent=styles['Title'], alignment=2, spaceAfter=2)
    if numero_ricevuta is None:
        numero_ricevuta = "N/D"
    story.append(Paragraph(f"N. RICEVUTA: <b>{numero_ricevuta}</b>", stile_num))
    # Data e ora in piccolo, sempre a destra
    stile_data = ParagraphStyle('DataOra', parent=styles['Normal'], alignment=2, fontSize=9, textColor=colors.grey)
    story.append(Paragraph(f"Data: {datetime.date.today().strftime('%d/%m/%Y')}  Ora: {datetime.datetime.now().strftime('%H:%M')}", stile_data))
    story.append(Spacer(1, 10))
    
    inserisci_anagrafica_cliente(story, "ACQUIRENTE / COMPRATORE", dati_acquirente)
    
    story.append(Paragraph(f"<b>Modalità di Pagamento:</b> {modalita_paga.upper()}", styles['Normal']))
    story.append(Spacer(1, 10))
    
    stile_tabella_bold = ParagraphStyle('TabellaBold', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')
    stile_cella = ParagraphStyle('CellaCassa', parent=styles['Normal'], fontSize=9, leading=11)
    stile_cella_b = ParagraphStyle('CellaCassaB', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold')
    
    dati_tabella = [[
        Paragraph("<b>Codice Copertina (Copie - Venditore)</b>", stile_cella_b), 
        Paragraph("<b>Descrizione Articolo Usato (ISBN)</b>", stile_cella_b), 
        Paragraph("<b>Prezzo Pagato</b>", stile_cella_b)
    ]]
    
    for item in libri_venduti:
        # Codice ufficiale: <codice_personale_venditore>-<id_libro> (es. BOR85RW0001-26)
        codice_copertina = f"{item.get('codice_venditore', '')}-{item['id_libro']}"
            
        dati_tabella.append([
            Paragraph(codice_copertina, stile_cella), 
            Paragraph(item['titolo'].upper(), stile_cella), 
            Paragraph(f"{item['prezzo_v']:.2f} €", stile_cella)
        ])
    
    # Totale libri scolastici usati
    dati_tabella.append([
        "", 
        Paragraph("<b>TOTALE SOLO LIBRI</b>", stile_tabella_bold), 
        Paragraph(f"<b>{totale_complessivo:.2f} €</b>", stile_tabella_bold)
    ])
    
    # Aggiungi la linea per il rimborso spese (0.50 € per libro)
    rimborso_totale = len(libri_venduti) * 0.50
    dati_tabella.append([
        "", 
        Paragraph("<b>RIMBORSO SPESE</b>", stile_tabella_bold), 
        Paragraph(f"<b>{rimborso_totale:.2f} €</b>", stile_tabella_bold)
    ])

    # Totale complessivo comprensivo di rimborso spese
    totale_con_rimborso = totale_complessivo + rimborso_totale
    dati_tabella.append([
        "", 
        Paragraph("<b>TOTALE COMPLESSIVO RICEVUTO</b>", stile_tabella_bold), 
        Paragraph(f"<b>{totale_con_rimborso:.2f} €</b>", stile_tabella_bold)
    ])
    
    col_cod, col_prz = 140, 100
    col_tit = 540 - col_cod - col_prz
    
    tabella = Table(dati_tabella, colWidths=[col_cod, col_tit, col_prz])
    tabella.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-2), 0.5, colors.black),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(tabella)
    
    inserisci_qrcode_marconi(story)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def genera_pdf_chiusura_giornaliera(data_str, c_tot, b_tot, t_tot, lista_pezzi):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    inserisci_intestazione_marconi(story)
    story.append(Paragraph(f"<b>REPORT CHIUSURA GIORNALIERA</b>", styles['Title']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Data Registro:</b> {data_str}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    dati_fin = [
        ["Metodo Incasso", "Volume Totale Movimentato"],
        ["Cassetto Contanti (Contante Fisico)", f"{c_tot:.2f} €"],
        ["Terminale POS (Bancomat / Carte)", f"{b_tot:.2f} €"],
        ["TOTALE GENERALE INCASSATO", f"{t_tot:.2f} €"]
    ]
    t_fin = Table(dati_fin, colWidths=[270, 270])
    t_fin.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_fin)
    story.append(Spacer(1, 25))
    
    story.append(Paragraph("<b>Dettaglio Articoli Venduti in Giornata:</b>", styles['Heading3']))
    story.append(Spacer(1, 5))
    
    dati_art = [["N. Libro", "Titolo Libro", "Incasso"]]
    for art in lista_pezzi:
        dati_art.append([str(art['id_libro']), art['titolo'][:50], f"{art['Prezzo Vendita']:.2f} €"])
        
    t_art = Table(dati_art, colWidths=[80, 360, 100])
    t_art.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_art)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def mostra_pagina():
    st.header("🛒 Cassa e Vendita Rapida")
    
    # Se c'è una ricevuta completata in session_state, mostriamo il download e blocchiamo il resto finché non si va avanti
    if "vendita_completata_pdf" in st.session_state:
        st.success("🎉 Vendita registrata con successo e archiviata!")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="🖨️ SCARICA ORA LA RICEVUTA ACQUISTO (PDF)",
                data=st.session_state["vendita_completata_pdf"],
                file_name="ricevuta_acquisto.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            if st.button("🆕 Inizia una nuova vendita", use_container_width=True):
                del st.session_state["vendita_completata_pdf"]
                st.session_state["carrello_cassa"] = []
                st.rerun()
        st.markdown("---")
        return

    copie_all = _carica_copie_cassa()
    cat_all = _carica_catalogo_cassa()
    
    df_master = pd.DataFrame()
    if copie_all and cat_all:
        df_c_all = pd.DataFrame(copie_all)
        df_ct_all = pd.DataFrame(cat_all)
        df_master = pd.merge(df_c_all, df_ct_all, on="isbn", how="left")
        df_master['prezzo_copertina'] = df_master['prezzo_copertina'].astype(float)
        df_master['Prezzo Reale Base'] = df_master['prezzo_inserito_mano'].astype(float).fillna(0.0)
        df_master.loc[df_master['Prezzo Reale Base'] == 0.0, 'Prezzo Reale Base'] = df_master['prezzo_copertina']
        df_master['Prezzo Vendita'] = (df_master['Prezzo Reale Base'] / 2) + 0.50

    st.markdown("### 🔍 Pannello Rapido di Monitoraggio")
    scelta_rapida = st.radio(
        "Cosa desideri monitorare in questo momento?",
        ["📈 Vedi Totale Giornaliero e Chiusura", "📦 Vedi Libri ancora in nostro Possesso (Residui)"],
        horizontal=True
    )
    
    if scelta_rapida == "📈 Vedi Totale Giornaliero e Chiusura":
        data_selezionata = st.date_input("📅 Seleziona il giorno di cui vuoi stampare il Report:", datetime.date.today())
        data_selezionata_str = data_selezionata.strftime("%d/%m/%Y")
        
        if not df_master.empty:
            if 'data_vendita' in df_master.columns:
                df_master['data_vendita_norm'] = df_master['data_vendita'].apply(lambda v: format_date_for_db(v) if pd.notna(v) else '')
                df_master['data_vendita_display'] = df_master['data_vendita_norm'].apply(lambda v: format_date_for_display(v) if v else '')
                df_venduti = df_master[(df_master['stato'] == 'venduto') & (df_master['data_vendita_norm'] == format_date_for_db(data_selezionata_str))]
            else:
                df_venduti = pd.DataFrame()
            
            tot_contanti = df_venduti[df_venduti['metodo_pagamento'].str.lower() == 'contanti']['Prezzo Vendita'].sum() if not df_venduti.empty and 'metodo_pagamento' in df_venduti.columns else 0.0
            tot_bancomat = df_venduti[df_venduti['metodo_pagamento'].str.lower().str.contains('bancomat', na=False)]['Prezzo Vendita'].sum() if not df_venduti.empty and 'metodo_pagamento' in df_venduti.columns else 0.0
            tot_giornata = tot_contanti + tot_bancomat
            
            st.write(f"📝 **Riepilogo contabile della data:** {data_selezionata_str}")
            c1, col2, col3 = st.columns(3)
            with c1: st.metric("💵 Cassetto CONTANTI", f"{tot_contanti:.2f} €")
            with col2: st.metric("💳 POS BANCOMAT", f"{tot_bancomat:.2f} €")
            with col3: st.metric("💰 INCASSO TOTALI", f"{tot_giornata:.2f} €")
            
            st.write("")
            lista_pezzi_giorno = df_venduti[['id_libro', 'titolo', 'Prezzo Vendita']].to_dict('records') if not df_venduti.empty else []
            pdf_giorno_data = genera_pdf_chiusura_giornaliera(data_selezionata_str, tot_contanti, tot_bancomat, tot_giornata, lista_pezzi_giorno)
            
            st.download_button(
                label=f"🖨️ STAMPA REPORT CASSA DEL {data_selezionata_str} (PDF CUMULATIVO)",
                data=pdf_giorno_data,
                file_name=f"chiusura_cassa_{data_selezionata.strftime('%Y_%m_%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else: st.info("Nessun dato presente.")
            
    else:
        if not df_master.empty:
            df_residui = df_master[df_master['stato'] == 'disponibile']
            if not df_residui.empty:
                res_cl_all = requests.get(f"{URL_REST}/clienti?select=id,codice_personale", headers=HEADERS)
                if res_cl_all.status_code == 200 and res_cl_all.json():
                    df_cl_all = pd.DataFrame(res_cl_all.json())
                    df_residui = pd.merge(df_residui, df_cl_all, left_on="id_venditore", right_on="id", how="left")
                    df_residui['Codice Etichetta'] = df_residui['codice_personale'].astype(str) + "-" + df_residui['id_libro'].astype(str)
                
                df_res_vis = df_residui[['Codice Etichetta', 'isbn', 'titolo', 'Prezzo Vendita']]
                df_res_vis.columns = ['Codice Copertina', 'ISBN', 'Titolo Libro', 'Prezzo da Riscuotere (€)']
                st.dataframe(df_res_vis.sort_values(by='Codice Copertina'), use_container_width=True, hide_index=True)
            else: st.info("Nessun libro residuo invenduto. Tutto esaurito!")
        else: st.info("Magazzino vuoto.")

    st.markdown("---")
    st.subheader("🛒 Operazioni di Cassa e Vendita")
    
    if "carrello_cassa" not in st.session_state:
        st.session_state["carrello_cassa"] = []
        
    clienti_list = _carica_clienti_cassa()
        
    opzioni_clienti = {f"{c['id']} - {c['codice_personale']} ({c['cognome']} {c['nome']})": c for c in clienti_list}
    chiavi_clienti = list(opzioni_clienti.keys())
    
    if not opzioni_clienti:
        st.warning("⚠️ Registra un cliente prima di fare vendite.")
        return
        
    # Mantiene in memoria l'ultimo acquirente selezionato tra un rerun e l'altro
    if "id_acquirente_corrente" not in st.session_state:
        st.session_state["id_acquirente_corrente"] = None

    # Pre-seleziona il widget con l'ultimo acquirente memorizzato (solo se presente nella lista)
    index_acquirente = 0
    if st.session_state["id_acquirente_corrente"] is not None:
        for i, k in enumerate(chiavi_clienti):
            if opzioni_clienti[k]["id"] == st.session_state["id_acquirente_corrente"]:
                index_acquirente = i
                break

    cliente_acquirente = st.selectbox(
        "Seleziona il Cliente Acquirente (Chi Compra)",
        chiavi_clienti,
        index=index_acquirente,
        key="acquirente_select",
        help="Puoi digitare per filtrare l'elenco. La selezione resta memorizzata tra un'operazione e l'altra.",
    )
    dati_acquirente = opzioni_clienti[cliente_acquirente]
    st.session_state["id_acquirente_corrente"] = dati_acquirente["id"]
    
    if "id_libro_selezionato_cassa" not in st.session_state:
        st.session_state["id_libro_selezionato_cassa"] = None
    id_libro_selezionato = None
    st.session_state["id_libro_selezionato_cassa"] = None

    st.caption("\U0001F50D Scrivi qui sotto: riconosco da solo se e' il NUMERO sulla copertina, il CODICE del venditore o un CODICE A BARRE. Nessun pallino da cliccare.")
    ricerca_cassa = st.text_input(
        "Cerca per Numero copertina, Codice venditore o Codice a barre:",
        key="ricerca_unica_cassa",
    ).strip()

    if ricerca_cassa:
        import re as _re
        # Normalizza separatori non alfanumerici in "-"
        clean = _re.sub(r"[^A-Za-z0-9]", "-", ricerca_cassa)
        parts = [pp.strip() for pp in clean.split("-") if pp.strip()]
        token = None
        if parts:
            if parts[-1].isdigit():
                token = parts[-1]
            elif parts[0].isdigit():
                token = parts[0]
            else:
                runs = _re.findall(r"\d+", clean)
                if runs:
                    token = runs[-1]

        found_copy = None
        if token:
            res_copy_any = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{token}", headers=HEADERS)
            if res_copy_any.status_code == 200 and res_copy_any.json():
                copia_any = res_copy_any.json()[0]
                if copia_any.get('stato') == 'disponibile':
                    found_copy = copia_any
                else:
                    st.warning(f"\u274c Libro {token} trovato ma NON disponibile (stato: {copia_any.get('stato')}).")
            if not found_copy:
                res_copy = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{token}&stato=eq.disponibile", headers=HEADERS)
                if res_copy.status_code == 200 and res_copy.json():
                    found_copy = res_copy.json()[0]

        # Se non trovato per numero, prova per codice venditore (es. BOR85RW0001)
        if not found_copy and not ricerca_cassa.isdigit():
            res_vend = requests.get(f"{URL_REST}/clienti?codice_personale=ilike.*{ricerca_cassa}*", headers=HEADERS)
            vend_list = res_vend.json() if res_vend.status_code == 200 else []
            if vend_list:
                id_v = vend_list[0]['id']
                res_libri_v = requests.get(f"{URL_REST}/copie_libri?id_venditore=eq.{id_v}&stato=eq.disponibile", headers=HEADERS)
                libri_v_list = res_libri_v.json() if res_libri_v.status_code == 200 else []
                if libri_v_list:
                    res_cat_all = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo", headers=HEADERS)
                    df_cat_all = pd.DataFrame(res_cat_all.json()) if res_cat_all.status_code == 200 else pd.DataFrame()
                    mappa_libri_v = {}
                    for cp in libri_v_list:
                        titolo_trovato = "Titolo Sconosciuto"
                        if not df_cat_all.empty and cp['isbn'] in df_cat_all['isbn'].values:
                            titolo_trovato = df_cat_all[df_cat_all['isbn'] == cp['isbn']]['titolo'].values[0]
                        mappa_libri_v[f"Numero Libro: {cp['id_libro']} - {titolo_trovato}"] = cp['id_libro']
                    scelta_cp = st.selectbox("Seleziona quale vendere:", list(mappa_libri_v.keys()), key="libro_vend_unico")
                    id_libro_selezionato = mappa_libri_v[scelta_cp]
                else:
                    st.warning("\u2753 Questo venditore non ha libri disponibili.")

        if not found_copy and ricerca_cassa and not ricerca_cassa.isdigit():
            try:
                res_by_bar = requests.get(f"{URL_REST}/copie_libri?barcode=eq.{ricerca_cassa}&stato=eq.disponibile", headers=HEADERS)
                if res_by_bar.status_code == 200 and res_by_bar.json():
                    found_copy = res_by_bar.json()[0]
            except Exception:
                found_copy = None

        if found_copy:
            id_libro_selezionato = found_copy.get('id_libro') or found_copy.get('id')
            st.session_state["id_libro_selezionato_cassa"] = id_libro_selezionato
            st.success(f"\U0001F3AF Trovata copia per codice: aggiungi libro {id_libro_selezionato}")
        elif token is None and not ricerca_cassa.isdigit() and not found_copy:
            st.warning(
                "\u274c Codice non valido: non contiene un numero di libro riconoscibile. "
                f"(Ricevuto: {ricerca_cassa!r})"
            )

    if id_libro_selezionato is not None:
        gia_inserito = any(x['id_libro'] == id_libro_selezionato for x in st.session_state["carrello_cassa"])
        if gia_inserito: 
            st.warning("⚠️ Già nel carrello.")
        else:
            res_copie_singola = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{id_libro_selezionato}", headers=HEADERS)
            copie_res = res_copie_singola.json() if res_copie_singola.status_code == 200 else []
            
            if len(copie_res) > 0:
                copia = copie_res[0] if isinstance(copie_res, list) and len(copie_res) > 0 else copie_res
                
                if copia['stato'] != 'disponibile': 
                    st.error("❌ Libro non disponibile.")
                else:
                    res_d = requests.get(f"{URL_REST}/catalogo_libri?isbn=eq.{copia['isbn']}", headers=HEADERS)
                    d_list = res_d.json() if res_d.status_code == 200 else []
                    
                    if len(d_list) > 0:
                        libro_dati = d_list[0] if isinstance(d_list, list) and len(d_list) > 0 else d_list
                        prezzo_base = float(copia.get('prezzo_inserito_mano', 0.0) or 0.0)
                        if prezzo_base == 0.0: 
                            prezzo_base = float(libro_dati.get('prezzo_copertina', 0.0) or 0.0)
                        prezzo_base_metà = prezzo_base / 2
                        prezzo_vendita = prezzo_base_metà + 0.50
                        
                        # Recuperiamo il codice personale (completo) del venditore
                        res_vendor_info = requests.get(f"{URL_REST}/clienti?id=eq.{copia['id_venditore']}", headers=HEADERS)
                        vendor_info_list = res_vendor_info.json() if res_vendor_info.status_code == 200 else []
                        codice_venditore_completo = vendor_info_list[0]['codice_personale'] if vendor_info_list else ""
                        
                        st.success(f"🎯 Libro Rilevato: {libro_dati['titolo']} (ISBN: {copia['isbn']})")
                        st.write(f"👤 **Codice Venditore Copia:** {codice_venditore_completo}")
                        
                        # Visualizzazione fascicoli allegati se presenti
                        prevede_f = copia.get("prevede_fascicoli", False)
                        totale_f = copia.get("totale_fascicoli", 0)
                        consegnati_f = copia.get("fascicoli_consegnati", 0)

                        sconto_fascicoli = 0.0
                        if prevede_f:
                            if consegnati_f >= totale_f:
                                st.info(f"📁 **Fascicoli allegati:** COMPLETO ({consegnati_f}/{totale_f} consegnati)")
                            else:
                                # Il testo è sprovvisto (in tutto o in parte) dei fascicoli
                                st.warning(f"⚠️ **Fascicoli allegati:** MANCANTI/INCOMPLETI ({consegnati_f}/{totale_f} consegnati)")
                                st.warning(
                                    "⚠️ Il testo risulta sprovvisto di tutti i fascicoli. "
                                    "Se il cliente accetta di acquistarlo incompleto, saranno scalati "
                                    "**4,00 € dal prezzo di copertina**."
                                )
                                accetta_sconto = st.checkbox(
                                    "Il cliente accetta lo sconto di 4,00 € per i fascicoli mancanti",
                                    key=f"accetta_fasc_{id_libro_selezionato}",
                                )
                                if accetta_sconto:
                                    sconto_fascicoli = 4.0

                        prezzo_v_finale = calcola_prezzo_vendita_scontato(prezzo_base, sconto_fascicoli)
                        st.metric(
                            label="💰 PREZZO VENDITA (50% COPERTINA)",
                            value=f"{prezzo_v_finale:.2f} €",
                            delta="+0.50 € rimborso spese (voce a parte)" + (f" | -{sconto_fascicoli:.2f} € fascicoli" if sconto_fascicoli > 0 else ""),
                        )

                        if st.button("➕ CONFERMA E INSERISCI QUESTO TITOLO NEL CARRELLO SPESA", use_container_width=True):
                            # Blocco: fascicoli incompleti e sconto non accettato dal cliente
                            if prevede_f and consegnati_f < totale_f and sconto_fascicoli == 0.0:
                                st.error(
                                    "❌ Vendita bloccata: il testo è sprovvisto di fascicoli. "
                                    "Completa i fascicoli oppure applica lo sconto di 4,00 € "
                                    "accettato dal cliente."
                                )
                            else:
                                titolo_cart = f"{libro_dati['titolo']} (ISBN: {copia['isbn']})"
                                if prevede_f:
                                    titolo_cart += f" (Fascicoli: {consegnati_f}/{totale_f})"
                                    if sconto_fascicoli > 0:
                                        titolo_cart += " [SCONTO 4€ FASCICOLI]"

                                st.session_state["carrello_cassa"].append({
                                    "id_libro": id_libro_selezionato,
                                    "titolo": titolo_cart,
                                    "prezzo_v": prezzo_v_finale,  # Prezzo vendita = 50% copertina scontata (il rimborso spese è voce a sé stante)
                                    "codice_venditore": codice_venditore_completo
                                })
                                st.session_state["id_libro_selezionato_cassa"] = None
                                st.rerun()

    if st.session_state["carrello_cassa"]:
        st.markdown("---")
        st.subheader("🛒 Riepilogo Spesa Attuale:")
        df_c = pd.DataFrame(st.session_state["carrello_cassa"])
        st.dataframe(df_c, use_container_width=True)

        st.caption("✏️ Puoi variare il prezzo di un singolo libro qui sotto (utile per sconti o correzioni):")
        for i, art in enumerate(st.session_state["carrello_cassa"]):
            c_edit_a, c_edit_b = st.columns([4, 1])
            with c_edit_a:
                st.write(f"{i+1}. {art['titolo'][:55]}")
            with c_edit_b:
                nuovo = st.number_input(
                    "Prezzo (€)",
                    min_value=0.0,
                    value=float(art["prezzo_v"]),
                    step=0.10,
                    key=f"prezzo_cart_{i}",
                    label_visibility="collapsed",
                )
                st.session_state["carrello_cassa"][i]["prezzo_v"] = float(nuovo)
        
        col_storno_c, _ = st.columns(2)
        with col_storno_c:
            idx_storno_c = st.selectbox("🎯 Rimuovi riga errata:", range(len(st.session_state["carrello_cassa"])), format_func=lambda x: f"Riga {x+1}: {st.session_state['carrello_cassa'][x]['titolo'][:30]}")
            if st.button("❌ Rimuovi dal carrello"):
                st.session_state["carrello_cassa"].pop(idx_storno_c)
                st.rerun()
                
        st.write("")
        totale_spesa = df_c['prezzo_v'].sum()
        rimborso_totale = len(df_c) * 0.50
        totale_con_rimborso = totale_spesa + rimborso_totale
        
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.metric(label="📚 TOTALE SOLO LIBRI", value=f"{totale_spesa:.2f} €")
        with c_m2:
            st.metric(label="🎟️ RIMBORSO SPESE GESTIONE", value=f"{rimborso_totale:.2f} €")
        with c_m3:
            st.metric(label="💰 TOTALE COMPLESSIVO PAGATO", value=f"{totale_con_rimborso:.2f} €")
        
        st.subheader("💳 Scegli il Metodo di Pagamento:")
        metodo_paga = st.radio("Seleziona come paga il cliente:", ["-- Seleziona --", "Contanti", "Bancomat / Carta"], horizontal=True)
        
        col_conferma, col_annulla = st.columns(2)
        with col_conferma:
            if metodo_paga == "-- Seleziona --":
                st.warning("⚠️ Seleziona la modalità di pagamento (Contanti o Bancomat) per sbloccare la vendita.")
            else:
                if st.button(f"🚀 REGISTRA VENDITA IN {metodo_paga.upper()} E PRODUCI PDF RICEVUTA", use_container_width=True):
                    successo = True
                    messaggio_errore = ""
                    data_oggi_fissa = format_date_for_db(datetime.date.today())
                    
                    for art in st.session_state["carrello_cassa"]:
                        url_up = f"{URL_REST}/copie_libri?id_libro=eq.{art['id_libro']}"
                        dati_aggiornamento_vendita = {
                            "id_acquirente": dati_acquirente['id'],
                            "stato": "venduto",
                            "metodo_pagamento": metodo_paga,
                            "data_vendita": data_oggi_fissa
                        }
                        res_v = requests.patch(url_up, headers=HEADERS, json=dati_aggiornamento_vendita)
                        if res_v.status_code >= 400:
                            successo = False
                            messaggio_errore = res_v.text or "Errore salvataggio."
                            break
                            
                    if successo:
                        # Numero progressivo per tipo vendita: N/V
                        n_ricevuta = prossimo_numero_ricevuta("V")
                        numero_ricevuta = f"{n_ricevuta}/V"
                        # Registra la ricevuta su DB (se la tabella ha le nuove colonne tipo/numero_progressivo)
                        try:
                            requests.post(
                                f"{URL_REST}/ricevute",
                                headers=HEADERS,
                                json={
                                    "tipo": "V",
                                    "numero_progressivo": n_ricevuta,
                                    "id_acquirente": dati_acquirente['id'],
                                    "metodo_pagamento": metodo_paga,
                                    "totale_libri": float(totale_spesa),
                                    "rimborso_spese": float(rimborso_totale),
                                    "totale_complessivo": float(totale_con_rimborso),
                                    "numero_articoli": len(st.session_state["carrello_cassa"]),
                                    "operatore": st.session_state.get("operatore", "Sconosciuto"),
                                },
                            )
                        except Exception:
                            pass

                        pdf_data = genera_pdf_vendita_multipla(dati_acquirente, st.session_state["carrello_cassa"], totale_spesa, metodo_paga, numero_ricevuta)
                        
                        # Salviamo il PDF generato in session state in modo che possa essere scaricato
                        st.session_state["vendita_completata_pdf"] = pdf_data
                        
                        op_nome = st.session_state.get("operatore", "anon").lower()
                        pubblica_ricevuta_online(
                            st,
                            pdf_data,
                            "vendita",
                            dati_acquirente,
                            data_riferimento=data_oggi_fissa,
                            suffisso=f"op-{op_nome}-{metodo_paga.lower().replace(' ', '-')}-{len(st.session_state['carrello_cassa'])}-articoli"
                        )
                        st.session_state["carrello_cassa"] = []
                        # Invalida la cache dei dati (copie/catalogo/clienti) per ricaricare i dati freschi
                        st.cache_data.clear()
                        st.rerun()
                    else: 
                        st.error(messaggio_errore or "Errore salvataggio.")
                        
        with col_annulla:
            if st.button("🗑️ Cancella Spesa"):
                st.session_state["carrello_cassa"] = []
                st.rerun()