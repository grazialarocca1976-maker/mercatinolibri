import math
import importlib
import requests
import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import datetime

import ricevute_condivise as ricevute_condivise_mod
ricevute_condivise_mod = importlib.reload(ricevute_condivise_mod)
from ricevute_condivise import (
    inserisci_intestazione_marconi,
    inserisci_anagrafica_cliente,
    pubblica_ricevuta_online,
)

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def genera_pdf_riepilogo_conto(dati_cliente, libri_cliente):
    """Genera un PDF riepilogativo di chiusura conto con i libri venduti e da liquidare."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    inserisci_intestazione_marconi(story)
    story.append(Paragraph("<b>CHIUSURA CONTO E LIQUIDAZIONE CLIENTE</b>", styles['Title']))
    story.append(Spacer(1, 10))

    inserisci_anagrafica_cliente(story, "SPETT.LE CLIENTE", dati_cliente)

    stile_cella = ParagraphStyle('CellaTab', parent=styles['Normal'], fontSize=8, leading=10)
    stile_cella_b = ParagraphStyle('CellaTabB', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')
    stile_bold = ParagraphStyle('TabBold', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')

    # Separiamo venduti e disponibili
    venduti = libri_cliente[libri_cliente['stato'] == 'venduto']
    disponibili = libri_cliente[libri_cliente['stato'] == 'disponibile']

    if not venduti.empty:
        story.append(Paragraph("<b>📚 Libri VENDUTI (già riscossi in cassa)</b>", styles['Heading3']))
        dati_tab = [[
            Paragraph("<b>Cod. Copertina</b>", stile_cella_b),
            Paragraph("<b>Titolo</b>", stile_cella_b),
            Paragraph("<b>Prezzo Copertina</b>", stile_cella_b),
        ]]
        for _, riga in venduti.iterrows():
            dati_tab.append([
                Paragraph(str(riga['id_libro']), stile_cella),
                Paragraph(str(riga.get('titolo', riga['isbn'])).upper(), stile_cella),
                Paragraph(f"{float(riga.get('Prezzo Base', riga.get('prezzo_copertina', 0))):.2f} €", stile_cella),
            ])
        t = Table(dati_tab, colWidths=[100, 340, 100])
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

    if not disponibili.empty:
        story.append(Paragraph("<b>📦 Libri IN POSSESSO (non venduti, restituiti al cliente)</b>", styles['Heading3']))
        dati_tab2 = [[
            Paragraph("<b>Cod. Copertina</b>", stile_cella_b),
            Paragraph("<b>Titolo</b>", stile_cella_b),
            Paragraph("<b>Prezzo Copertina</b>", stile_cella_b),
        ]]
        for _, riga in disponibili.iterrows():
            dati_tab2.append([
                Paragraph(str(riga['id_libro']), stile_cella),
                Paragraph(str(riga.get('titolo', riga['isbn'])).upper(), stile_cella),
                Paragraph(f"{float(riga.get('Prezzo Base', riga.get('prezzo_copertina', 0))):.2f} €", stile_cella),
            ])
        t2 = Table(dati_tab2, colWidths=[100, 340, 100])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t2)
        story.append(Spacer(1, 10))

    # --- TOTALI ---
    # 'Prezzo Incassato' = 50% del prezzo di copertina (il rimborso spese di 0,50 €/libro è voce a sé stante)
    if not venduti.empty and 'Prezzo Base' in venduti.columns:
        tot_venduti = float((venduti['Prezzo Base'] / 2).sum())
    elif not venduti.empty:
        tot_venduti = float((venduti['prezzo_copertina'].astype(float) / 2).sum())
    else:
        tot_venduti = 0.0
    liq_venduti = venduti['Liquidazione (€)'].sum() if not venduti.empty else 0.0

    # Totale effettivo da dare al cliente (solo per i libri venduti)
    totale_da_pagare = liq_venduti

    # --- RIEPILOGO CHIARO ---
    dati_totali = [[
        Paragraph("<b>TOTALE INCASSATO (50% PREZZO COPERTINA)</b>", stile_bold),
        Paragraph(f"<b>{tot_venduti:.2f} €</b>", stile_bold),
    ]]
    if totale_da_pagare > 0:
        dati_totali.append([
            Paragraph("<b>TOTALE DA PAGARE AL CLIENTE (50% del prezzo di copertina MENO 0,50 € di rimborso spese gestione a libro)</b>", stile_bold),
            Paragraph(f"<b>{totale_da_pagare:.2f} €</b>", stile_bold),
        ])
    if not disponibili.empty:
        dati_totali.append([
            Paragraph("<b>DA RESTITUIRE AL CLIENTE - Libri NON venduti (n. {0}, NON pagati)</b>".format(len(disponibili)), stile_bold),
            Paragraph("<b>RESTITUZIONE FISICA</b>", stile_bold),
        ])
    t_tot = Table(dati_totali, colWidths=[440, 100])
    t_tot.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 1.5, colors.black),
        ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_tot)
    story.append(Spacer(1, 10))
    # Nota esplicativa per evitare confusione tra "pagare" e "restituire"
    if not disponibili.empty:
        story.append(Paragraph(
            "<i>ℹ️ I libri elencati come 'DA RESTITUIRE' NON sono stati acquistati: vanno riconsegnati "
            "al cliente e non costituiscono un importo da pagare. Il 'TOTALE DA PAGARE' riguarda "
            "esclusivamente i libri effettivamente venduti.</i>",
            styles['Normal'],
        ))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Firma per ricevuta: __________________________________________________", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def payload_chiusura_conto():
    return {"stato": "chiuso_conto"}


def payload_storno_vendita():
    return {
        "stato": "disponibile",
        "id_acquirente": None,
        "metodo_pagamento": None,
        "data_vendita": None,
    }


def payload_storno_ritiro():
    return {"stato": "disponibile"}


def _rigenera_ricevuta_ritiro_completa(cliente_full, libri_cliente):
    """Rigenera la ricevuta di ritiro COMPLETA del cliente con i prezzi aggiornati.
    Usa tutti i libri ancora 'disponibile' (ritirati ma non venduti) del cliente,
    cosi la ricevuta viene ristampata per intero e non solo per il singolo libro corretto."""
    from ritiro import genera_pdf_ricevuta
    disponibili = libri_cliente[libri_cliente['stato'] == 'disponibile']
    if disponibili.empty:
        return None
    libri_ritirati = []
    for _, r in disponibili.iterrows():
        libri_ritirati.append({
            "etichetta": f"{r['id_libro']} - {cliente_full['codice_personale']}",
            "isbn": r['isbn'],
            "titolo": r.get('titolo', r['isbn']),
            "prezzo": float(r.get('prezzo_inserito_mano', 0.0) or r.get('prezzo_copertina', 0.0)),
        })
    return genera_pdf_ricevuta(cliente_full, libri_ritirati)


def mostra_pagina():
    st.header("🧾 Gestione conti cliente")
    st.write("Qui puoi chiudere il conto di un cliente, annullare una vendita o annullare un ritiro.")

    # Se c'è un PDF di chiusura conto completato in session_state, mostriamo il download e blocchiamo/presentiamo il pulsante per andare avanti
    if "riepilogo_conto_pdf" in st.session_state:
        st.success("🎉 Conto chiuso con successo e ricevuta generata!")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📄 SCARICA ORA LA RICEVUTA CHIUSURA CONTO (PDF)",
                data=st.session_state["riepilogo_conto_pdf"],
                file_name=f"ricevuta_chiusura_conto_{st.session_state.get('codice_cliente_chiusura', 'cliente')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            if st.button("🆕 Lavora su un altro cliente", use_container_width=True):
                del st.session_state["riepilogo_conto_pdf"]
                if "codice_cliente_chiusura" in st.session_state:
                    del st.session_state["codice_cliente_chiusura"]
                st.rerun()
        st.markdown("---")
        return

    # Se c'è una ricevuta di ritiro rigenerata (dopo correzione prezzo o storno), mostriamo il download
    if "ricevuta_ritiro_ristampata_pdf" in st.session_state:
        st.success("🎉 Ricevuta di ritiro rigenerata con i prezzi aggiornati!")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📄 SCARICA RICEVUTA RITIRO AGGIORNATA (PDF)",
                data=st.session_state["ricevuta_ritiro_ristampata_pdf"],
                file_name=f"ricevuta_ritiro_{st.session_state.get('codice_cliente_ritiro', 'cliente')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            if st.button("🆕 Chiudi ricevuta e continua", use_container_width=True, key="chiudi_ritiro_rist"):
                del st.session_state["ricevuta_ritiro_ristampata_pdf"]
                if "codice_cliente_ritiro" in st.session_state:
                    del st.session_state["codice_cliente_ritiro"]
                st.rerun()
        st.markdown("---")

    res_clienti = requests.get(f"{URL_REST}/clienti?select=id,codice_personale,nome,cognome", headers=HEADERS)
    clienti = res_clienti.json() if res_clienti.status_code == 200 else []
    if not clienti:
        st.info("Nessun cliente registrato.")
        return

    opzioni_clienti = {f"{c['id']} - {c['cognome']} {c['nome']} ({c['codice_personale']})": c for c in clienti}
    cliente_scelto = st.selectbox("Seleziona il cliente", list(opzioni_clienti.keys()))
    cliente = opzioni_clienti[cliente_scelto]

    # Record cliente completo (telefono/email) per la rigenerazione delle ricevute
    res_cli_full = requests.get(f"{URL_REST}/clienti?id=eq.{cliente['id']}&select=*", headers=HEADERS)
    cliente_full = res_cli_full.json()[0] if (res_cli_full.status_code == 200 and res_cli_full.json()) else cliente

    res_copie = requests.get(f"{URL_REST}/copie_libri?select=*", headers=HEADERS)
    copie = res_copie.json() if res_copie.status_code == 200 else []
    if not copie:
        st.info("Nessuna copia presente nel magazzino.")
        return

    df = pd.DataFrame(copie)
    libri_cliente = df[df['id_venditore'] == cliente['id']]
    if libri_cliente.empty:
        st.info("Questo cliente non ha libri in gestione.")
        return

    # Arricchisce con titolo e prezzi dal catalogo
    res_cat = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo,prezzo_copertina", headers=HEADERS)
    cat = res_cat.json() if res_cat.status_code == 200 else []
    df_cat = pd.DataFrame(cat) if cat else pd.DataFrame(columns=['isbn', 'titolo', 'prezzo_copertina'])

    if not df_cat.empty:
        libri_cliente = libri_cliente.merge(df_cat, on='isbn', how='left')
    else:
        libri_cliente['titolo'] = ''
        libri_cliente['prezzo_copertina'] = 0.0

    libri_cliente['prezzo_copertina'] = libri_cliente['prezzo_copertina'].astype(float)
    libri_cliente['Prezzo Base'] = libri_cliente['prezzo_inserito_mano'].astype(float).fillna(0.0)
    libri_cliente.loc[libri_cliente['Prezzo Base'] == 0.0, 'Prezzo Base'] = libri_cliente['prezzo_copertina']
    # Arrotondamento ai 10 centesimi:
    #  - Vendita (chi acquista in cassa): per eccesso (superiore) + 0,50 € di rimborso spese gestione
    #  - Liquidazione (chi vende/ritira): per difetto (inferiore) - 0,50 € di rimborso spese gestione
    # I 0,50 €/libro sono il RIMBORSO SPESE DI GESTIONE trattenuto dal negozio (voce a sé stante):
    # l'acquirente paga 50% + 0,50 €, il venditore riceve 50% - 0,50 €.
    libri_cliente['Prezzo Vendita (€)'] = libri_cliente['Prezzo Base'].apply(lambda b: math.ceil((b / 2) * 10) / 10 + 0.50)
    libri_cliente['Liquidazione (€)'] = libri_cliente['Prezzo Base'].apply(lambda b: math.floor((b / 2) * 10) / 10 - 0.50)

    st.subheader("Libri del cliente")
    colonne = ['id_libro', 'isbn', 'titolo', 'stato', 'Prezzo Vendita (€)', 'Liquidazione (€)', 'id_acquirente', 'metodo_pagamento', 'data_vendita']
    colonne = [c for c in colonne if c in libri_cliente.columns]
    st.dataframe(libri_cliente[colonne], use_container_width=True, hide_index=True)

    # --- MODIFICA PREZZO (correzione errori di digitazione) ---
    st.markdown("---")
    st.subheader("✏️ Correggi il prezzo di un libro (se digitato male)")
    scelte_prezzo = {f"{r['id_libro']} - {r.get('titolo', r['isbn'])} (ISBN {r['isbn']})": r for _, r in libri_cliente.iterrows()}
    libro_da_mod = st.selectbox("Seleziona il libro da correggere", list(scelte_prezzo.keys()))
    riga_mod = scelte_prezzo[libro_da_mod]
    nuovo_prezzo = st.number_input(
        "Nuovo prezzo di copertina / base (€)",
        min_value=0.0,
        value=float(riga_mod.get('prezzo_inserito_mano', 0.0) or riga_mod.get('prezzo_copertina', 0.0)),
        step=0.10,
    )
    if st.button("💾 Aggiorna prezzo libro", use_container_width=True):
        res_up = requests.patch(
            f"{URL_REST}/copie_libri?id_libro=eq.{riga_mod['id_libro']}",
            headers=HEADERS,
            json={"prezzo_inserito_mano": nuovo_prezzo},
        )
        if res_up.status_code < 400:
            # Rigenera la ricevuta di ritiro COMPLETA (con il prezzo aggiornato) e la
            # ripubblica online, cosi il prezzo aggiornato appare anche sulle ricevute online.
            try:
                pdf_ritiro = _rigenera_ricevuta_ritiro_completa(cliente_full, libri_cliente)
                if pdf_ritiro:
                    st.session_state["ricevuta_ritiro_ristampata_pdf"] = pdf_ritiro
                    st.session_state["codice_cliente_ritiro"] = cliente['codice_personale']
                    pubblica_ricevuta_online(
                        st, pdf_ritiro, "ritiro", cliente_full,
                        data_riferimento=datetime.date.today().strftime("%Y-%m-%d"),
                        suffisso=cliente['codice_personale'],
                    )
            except Exception as e:
                st.warning(f"Prezzo aggiornato, ma impossibile rigenerare/pubblicare la ricevuta: {e}")
            st.success("✅ Prezzo aggiornato. Ricevuta di ritiro rigenerata per intero e aggiornata online.")
            st.rerun()
        else:
            st.error("Errore nell'aggiornamento del prezzo.")

    tab_chiusura, tab_vendita, tab_ritiro = st.tabs(["Chiudi conto", "Storno vendita", "Storno ritiro"])

    # Il conto è già chiuso se non ci sono più libri attivi (venduti o disponibili) per questo cliente
    libri_attivi = libri_cliente[libri_cliente['stato'].isin(['venduto', 'disponibile'])]
    conto_gia_chiuso = libri_attivi.empty

    with tab_chiusura:
         if conto_gia_chiuso:
              st.warning("⚠️ Il conto di questo cliente è già stato chiuso e liquidato (non ci sono libri disponibili o venduti attivi).")
              st.info("💡 Se necessario, puoi ancora scaricare l'ultima ricevuta di chiusura conto dal tab 'Archivio' o eseguire uno storno.")
         else:
              if st.button("🔒 Chiudi conto cliente", use_container_width=True):
                  try:
                      # Genera il PDF riepilogativo prima di chiudere (passiamo solo i libri che erano attivi per questa chiusura)
                      pdf_data = genera_pdf_riepilogo_conto(cliente, libri_attivi.copy())
                      st.session_state["riepilogo_conto_pdf"] = pdf_data
                      st.session_state["codice_cliente_chiusura"] = cliente['codice_personale']
                      
                      pubblica_ricevuta_online(
                          st,
                          pdf_data,
                          "chiusura_conto",
                          cliente,
                          data_riferimento=datetime.date.today().strftime("%Y-%m-%d"),
                          suffisso=cliente['codice_personale'],
                      )

                      # Chiude il conto: i libri venduti diventano 'chiuso_conto' (liquidati), quelli disponibili diventano 'ritirato' (non più in nostro possesso)
                      res_disp = requests.patch(f"{URL_REST}/copie_libri?id_venditore=eq.{cliente['id']}&stato=eq.disponibile", headers=HEADERS, json={"stato": "ritirato"})
                      res_vend = requests.patch(f"{URL_REST}/copie_libri?id_venditore=eq.{cliente['id']}&stato=eq.venduto", headers=HEADERS, json={"stato": "chiuso_conto"})
                      
                      if res_disp.status_code < 400 and res_vend.status_code < 400:
                          st.success("Conto chiuso con successo: libri venduti liquidati e libri disponibili restituiti!")
                          st.rerun()
                      else:
                          st.error("Errore nell'aggiornamento dello stato dei libri su Supabase.")
                  except Exception as e:
                      st.error(f"Errore nella chiusura del conto: {str(e)}")

    with tab_vendita:
        libri_venduti = libri_cliente[libri_cliente['stato'] == 'venduto']
        if libri_venduti.empty:
            st.info("Nessuna vendita da storno per questo cliente.")
        else:
            scelte = {f"{r['id_libro']} - {r['isbn']}": r['id_libro'] for _, r in libri_venduti.iterrows()}
            scelta = st.selectbox("Seleziona il libro da restituire disponibile", list(scelte.keys()))
            if st.button("↩️ Storna vendita", use_container_width=True):
                id_libro = scelte[scelta]
                res = requests.patch(f"{URL_REST}/copie_libri?id_libro=eq.{id_libro}", headers=HEADERS, json=payload_storno_vendita())
                if res.status_code < 400:
                    st.success("Vendita stornata. Il libro è tornato disponibile.")
                else:
                    st.error("Errore nello storno della vendita.")

    with tab_ritiro:
        libri_ritirati = libri_cliente[libri_cliente['stato'] == 'disponibile']
        if libri_ritirati.empty:
            st.info("Nessun ritiro da storno per questo cliente.")
        else:
            scelte = {f"{r['id_libro']} - {r['isbn']}": r['id_libro'] for _, r in libri_ritirati.iterrows()}
            scelta = st.selectbox("Seleziona il libro da togliere dal ritiro", list(scelte.keys()))
            if st.button("🗑️ Storna ritiro (rimuovi dal magazzino)", use_container_width=True):
                id_libro = scelte[scelta]
                # Lo storno di un ritiro DEVE rimuovere fisicamente la copia dal magazzino
                res = requests.delete(f"{URL_REST}/copie_libri?id_libro=eq.{id_libro}", headers=HEADERS)
                if res.status_code < 400:
                    # Libro rimosso: rigenera la ricevuta di ritiro COMPLETA (senza il libro cancellato)
                    # e la ripubblica online con i dati aggiornati.
                    try:
                        libri_rimasti = libri_cliente[libri_cliente['id_libro'] != id_libro]
                        pdf_ritiro = _rigenera_ricevuta_ritiro_completa(cliente_full, libri_rimasti)
                        if pdf_ritiro:
                            st.session_state["ricevuta_ritiro_ristampata_pdf"] = pdf_ritiro
                            st.session_state["codice_cliente_ritiro"] = cliente['codice_personale']
                            pubblica_ricevuta_online(
                                st, pdf_ritiro, "ritiro", cliente_full,
                                data_riferimento=datetime.date.today().strftime("%Y-%m-%d"),
                                suffisso=cliente['codice_personale'],
                            )
                    except Exception as e:
                        st.warning(f"Libro rimosso, ma impossibile rigenerare/pubblicare la ricevuta: {e}")
                    st.success("Ritiro stornato: libro rimosso dal magazzino. Ricevuta di ritiro rigenerata per intero e aggiornata online.")
                    st.rerun()
                else:
                    st.error("Errore nello storno del ritiro.")
