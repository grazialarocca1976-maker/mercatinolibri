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


def _rigenera_ricevuta_ritiro_completa(cliente_full, libri_cliente, includi_id_libro=None):
    """Rigenera la ricevuta di ritiro COMPLETA del cliente con i prezzi aggiornati.
    Usa tutti i libri ancora 'disponibile' (ritirati ma non venduti) del cliente,
    cosi la ricevuta viene ristampata per intero. Se si passa 'includi_id_libro',
    quel libro viene include nella ricevuta anche se non è in stato 'disponibile'
    (es. è già 'venduto'), così la correzione prezzo rigenera la ricevuta giusta."""
    from ritiro import genera_pdf_ricevuta
    maschera = libri_cliente['stato'] == 'disponibile'
    if includi_id_libro is not None:
        maschera = maschera | (libri_cliente['id_libro'] == includi_id_libro)
    disponibili = libri_cliente[maschera]
    if disponibili.empty:
        return None
    libri_ritirati = []
    for _, r in disponibili.iterrows():
        titolo_completo = r.get('titolo', r['isbn'])
        # Se prevede fascicoli, aggiunge l'annotazione nel titolo per il PDF
        if r.get('prevede_fascicoli', False):
            titolo_completo += f" (Fascicoli: {r.get('fascicoli_consegnati', 0)}/{r.get('totale_fascicoli', 0)})"
            
        libri_ritirati.append({
            "etichetta": f"{r['id_libro']} - {cliente_full['codice_personale']}",
            "isbn": r['isbn'],
            "titolo": titolo_completo,
            "prezzo": float(r.get('prezzo_inserito_mano', 0.0) or r.get('prezzo_copertina', 0.0)),
        })
    return genera_pdf_ricevuta(cliente_full, libri_ritirati)


def _rigenera_ricevuta_vendita(cliente_full, riga_mod, nuovo_prezzo):
    """Rigenera la ricevuta di VENDITA per un singolo libro già venduto, con il prezzo aggiornato.
    Restituisce i byte del PDF o None se non è possibile (es. acquirente mancante)."""
    from cassa import genera_pdf_vendita_multipla
    id_acquirente = riga_mod.get('id_acquirente')
    if not id_acquirente:
        return None
    res_acq = requests.get(f"{URL_REST}/clienti?id=eq.{id_acquirente}&select=*", headers=HEADERS)
    acquirente = res_acq.json()[0] if (res_acq.status_code == 200 and res_acq.json()) else None
    if acquirente is None:
        return None
    libro = {
        "codice_venditore": cliente_full.get('codice_personale', ''),
        "id_libro": riga_mod['id_libro'],
        "titolo": riga_mod.get('titolo', riga_mod.get('isbn', '')),
        "prezzo_v": float(nuovo_prezzo),
    }
    modalita = riga_mod.get('metodo_pagamento') or 'contanti'
    totale = float(nuovo_prezzo)
    return genera_pdf_vendita_multipla(acquirente, [libro], totale, modalita, numero_ricevuta=None)


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

    # Se c'è una ricevuta di vendita rigenerata (dopo correzione prezzo di un libro venduto),
    # mostriamo il download
    if "ricevuta_vendita_ristampata_pdf" in st.session_state:
        st.success("🎉 Ricevuta di vendita rigenerata con i prezzi aggiornati!")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📄 SCARICA RICEVUTA VENDITA AGGIORNATA (PDF)",
                data=st.session_state["ricevuta_vendita_ristampata_pdf"],
                file_name=f"ricevuta_vendita_{st.session_state.get('codice_cliente_vendita', 'cliente')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            if st.button("🆕 Chiudi ricevuta vendita e continua", use_container_width=True, key="chiudi_vendita_rist"):
                del st.session_state["ricevuta_vendita_ristampata_pdf"]
                if "codice_cliente_vendita" in st.session_state:
                    del st.session_state["codice_cliente_vendita"]
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
    libri_cliente['Prezzo di Copertina'] = libri_cliente['prezzo_copertina']
    libri_cliente['Prezzo Vendita (€)'] = libri_cliente['Prezzo Base'].apply(lambda b: math.ceil((b / 2) * 10) / 10 + 0.50)
    libri_cliente['Liquidazione (€)'] = libri_cliente['Prezzo Base'].apply(lambda b: math.floor((b / 2) * 10) / 10 - 0.50)

    # Colonna calcolata per visualizzare lo stato dei fascicoli
    def _format_fascicoli(row):
        prevede = row.get("prevede_fascicoli", False)
        totale = row.get("totale_fascicoli", 0)
        cons = row.get("fascicoli_consegnati", 0)
        if prevede:
            return f"Si ({cons}/{totale})"
        return "No"

    if 'prevede_fascicoli' in libri_cliente.columns:
        libri_cliente['Fascicoli'] = libri_cliente.apply(_format_fascicoli, axis=1)
    else:
        libri_cliente['Fascicoli'] = 'No'

    # Separiamo i libri ATTIVI (vendibili/venduti) da quelli di conti GIÀ CHIUSI,
    # cosi risultano ben distinti anche se il cliente ha portato altri libri dopo la chiusura.
    df_attivi = libri_cliente[libri_cliente['stato'].isin(['disponibile', 'venduto'])]
    df_chiusi = libri_cliente[libri_cliente['stato'] == 'chiuso_conto']

    colonne = ['id_libro', 'isbn', 'titolo', 'Fascicoli', 'stato', 'Prezzo Vendita (€)', 'Liquidazione (€)', 'Prezzo di Copertina', 'id_acquirente', 'metodo_pagamento', 'data_vendita', 'operatore']
    colonne = [c for c in colonne if c in libri_cliente.columns]

    riga_selezionata = None

    if df_attivi.empty:
        st.info("📗 Nessun libro attivo (vendibile o venduto) per questo cliente.")
    else:
        st.subheader("📗 Libri attivi (vendibili / venduti)")
        st.caption("💡 Clicca su una riga della tabella per selezionare il libro (invece di usare il menu a cascata).")
        st.dataframe(
            df_attivi[colonne],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tab_attivi",
        )
        _sel = st.session_state.get("tab_attivi", {}).get("selection", {}).get("rows", [])
        if _sel:
            id_sel = df_attivi.iloc[int(_sel[0])]['id_libro']
            riga_selezionata = libri_cliente[libri_cliente['id_libro'] == id_sel].iloc[0]

    if not df_chiusi.empty:
        st.subheader("📕 Libri di conti già chiusi (restituiti / liquidati)")
        st.caption("💡 Clicca su una riga per selezionare anche un libro di un conto chiuso.")
        st.dataframe(
            df_chiusi[colonne],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tab_chiusi",
        )
        _sel = st.session_state.get("tab_chiusi", {}).get("selection", {}).get("rows", [])
        if _sel and riga_selezionata is None:
            id_sel = df_chiusi.iloc[int(_sel[0])]['id_libro']
            riga_selezionata = libri_cliente[libri_cliente['id_libro'] == id_sel].iloc[0]

    # Il conto è considerato chiuso solo se NON rimangono libri attivi
    # ('venduto' o 'disponibile'). Questo evita incongruenze in cui il conto
    # risulta "chiuso" (per la presenza di libri 'chiuso_conto') ma rimane
    # un libro 'disponibile' non ancora gestito/restituito.
    libri_attivi = libri_cliente[libri_cliente['stato'].isin(['venduto', 'disponibile'])]
    conto_gia_chiuso = libri_attivi.empty

    # --- MODIFICA PREZZO (correzione errori di digitazione) ---
    st.markdown("---")
    st.subheader("✏️ Correggi il prezzo di un libro (se digitato male)")
    
    # Controlla se il conto è chiuso (nessun libro attivo rimasto)
    conto_chiuso = conto_gia_chiuso
    
    if conto_chiuso:
        st.error("🚫 Impossibile modificare i prezzi: il conto di questo cliente è già stato chiuso e liquidato.")
        st.info("💡 I prezzi dei libri già venduti non possono essere modificati una volta che il conto è stato chiuso.")
    else:
        if riga_selezionata is None:
            st.info("👆 Seleziona un libro dalla tabella qui sopra per correggerne il prezzo.")
        else:
            riga_mod = riga_selezionata.to_dict()
            st.markdown(f"**Libro selezionato:** `{riga_mod['id_libro']} - {riga_mod.get('titolo', riga_mod['isbn'])}` (stato: `{riga_mod['stato']}`)")
            
            col_mod1, col_mod2 = st.columns(2)
            with col_mod1:
                nuovo_prezzo = st.number_input(
                    "Nuovo prezzo di copertina / base (€)",
                    min_value=0.0,
                    value=float(riga_mod.get('prezzo_inserito_mano', 0.0) or riga_mod.get('prezzo_copertina', 0.0)),
                    step=0.10,
                )
            with col_mod2:
                # Modifica stato fascicoli
                mod_prevede_f = st.checkbox(
                    "Prevede fascicoli allegati?",
                    value=bool(riga_mod.get('prevede_fascicoli', False)),
                    key="mod_prevede_f"
                )
            
            mod_totale_f = int(riga_mod.get('totale_fascicoli', 0))
            mod_consegnati_f = int(riga_mod.get('fascicoli_consegnati', 0))
            
            if mod_prevede_f:
                col_mod_f1, col_mod_f2 = st.columns(2)
                with col_mod_f1:
                    mod_totale_f = st.number_input(
                        "Fascicoli totali previsti:",
                        min_value=1,
                        value=max(1, int(riga_mod.get('totale_fascicoli', 1))),
                        step=1,
                        key="mod_totale_f"
                    )
                with col_mod_f2:
                    mod_consegnati_f = st.number_input(
                        "Fascicoli effettivamente consegnati:",
                        min_value=0,
                        max_value=mod_totale_f,
                        value=min(mod_totale_f, int(riga_mod.get('fascicoli_consegnati', 1) if riga_mod.get('prevede_fascicoli') else mod_totale_f)),
                        step=1,
                        key="mod_consegnati_f"
                    )
            else:
                mod_totale_f = 0
                mod_consegnati_f = 0
            
            # Previene aggiornamenti doppi usando un flag in session_state
            update_key = f"price_update_in_progress_{cliente['id']}"
            if st.button("💾 Aggiorna dettagli e fascicoli libro", use_container_width=True) and not st.session_state.get(update_key, False):
                st.session_state[update_key] = True
                
                payload_up = {
                    "prezzo_inserito_mano": nuovo_prezzo,
                    "prevede_fascicoli": mod_prevede_f,
                    "totale_fascicoli": mod_totale_f,
                    "fascicoli_consegnati": mod_consegnati_f
                }
                
                res_up = requests.patch(
                    f"{URL_REST}/copie_libri?id_libro=eq.{riga_mod['id_libro']}",
                    headers=HEADERS,
                    json=payload_up,
                )
                
                # Robustezza Fallback: se le nuove colonne dei fascicoli non esistono ancora, riprova aggiornando solo il prezzo
                if res_up.status_code >= 400:
                    payload_up.pop("prevede_fascicoli", None)
                    payload_up.pop("totale_fascicoli", None)
                    payload_up.pop("fascicoli_consegnati", None)
                    res_up = requests.patch(
                        f"{URL_REST}/copie_libri?id_libro=eq.{riga_mod['id_libro']}",
                        headers=HEADERS,
                        json=payload_up,
                    )
                
                if res_up.status_code < 400 and res_up.json():
                    # Aggiorna il prezzo e i fascicoli anche nel DataFrame in memoria PRIMA di rigenerare
                    # la ricevuta: altrimenti verrebbe ristampata quella coi dati vecchi.
                    libri_cliente.loc[libri_cliente['id_libro'] == riga_mod['id_libro'], 'prezzo_inserito_mano'] = nuovo_prezzo
                    if "prevede_fascicoli" in payload_up:
                        libri_cliente.loc[libri_cliente['id_libro'] == riga_mod['id_libro'], 'prevede_fascicoli'] = mod_prevede_f
                        libri_cliente.loc[libri_cliente['id_libro'] == riga_mod['id_libro'], 'totale_fascicoli'] = mod_totale_f
                        libri_cliente.loc[libri_cliente['id_libro'] == riga_mod['id_libro'], 'fascicoli_consegnati'] = mod_consegnati_f
                    # Aggiorna anche il "Prezzo di Copertina" (colonna visibile): quel valore
                    # deriva dal catalogo, quindi lo aggiorniamo in memoria e su catalogo_libri
                    # (per ISBN), cosi la colonna "Prezzo di Copertina" risulta aggiornata.
                    libri_cliente.loc[libri_cliente['isbn'] == riga_mod['isbn'], 'prezzo_copertina'] = nuovo_prezzo
                    requests.patch(
                        f"{URL_REST}/catalogo_libri?isbn=eq.{riga_mod['isbn']}",
                        headers=HEADERS,
                        json={"prezzo_copertina": nuovo_prezzo},
                    )
                    # Rigenera la ricevuta di ritiro COMPLETA (con il prezzo aggiornato) e la
                    # ripubblica online, cosi il prezzo aggiornato appare anche sulle ricevute online.
                    try:
                        pdf_ritiro = _rigenera_ricevuta_ritiro_completa(cliente_full, libri_cliente, includi_id_libro=riga_mod['id_libro'])
                        if pdf_ritiro:
                            st.session_state["ricevuta_ritiro_ristampata_pdf"] = pdf_ritiro
                            st.session_state["codice_cliente_ritiro"] = cliente['codice_personale']
                            pubblica_ricevuta_online(
                                st, pdf_ritiro, "ritiro", cliente_full,
                                data_riferimento=datetime.date.today().strftime("%Y-%m-%d"),
                                suffisso=cliente['codice_personale'],
                            )
                    except Exception as e:
                        st.warning(f"Prezzo aggiornato, ma impossibile rigenerare/pubblicare la ricevuta di ritiro: {e}")
                    # Se il libro è VENDUTO, rigenera anche la ricevuta di VENDITA (con il prezzo aggiornato)
                    if str(riga_mod.get('stato')) == 'venduto':
                        try:
                            pdf_vendita = _rigenera_ricevuta_vendita(cliente_full, riga_mod, nuovo_prezzo)
                            if pdf_vendita:
                                st.session_state["ricevuta_vendita_ristampata_pdf"] = pdf_vendita
                                st.session_state["codice_cliente_vendita"] = cliente['codice_personale']
                                pubblica_ricevuta_online(
                                    st, pdf_vendita, "vendita", cliente_full,
                                    data_riferimento=datetime.date.today().strftime("%Y-%m-%d"),
                                    suffisso=cliente['codice_personale'],
                                )
                        except Exception as e:
                            st.warning(f"Prezzo aggiornato, ma impossibile rigenerare/pubblicare la ricevuta di vendita: {e}")
                    # Il flag va resettato PRIMA di st.rerun(): altrimenti resterebbe True
                    # e la pagina mostrerebbe per sempre "Aggiornamento in corso...".
                    st.session_state[update_key] = False
                    st.success("✅ Prezzo aggiornato. Ricevuta di ritiro rigenerata per intero e aggiornata online.")
                    st.rerun()
                else:
                    st.session_state[update_key] = False
                    st.error("Errore nell'aggiornamento del prezzo: nessuna riga aggiornata nel database.")
            elif st.session_state.get(update_key, False):
                st.info("⏳ Aggiornamento in corso... Attendere prego.")

            # Cambio stato del libro (es. venduto -> disponibile) direttamente da qui
            if str(riga_mod.get('stato')) == 'venduto':
                st.markdown("---")
                if st.button("↩️ Riporta il libro in 'disponibile' (storna vendita)", use_container_width=True, key="stato_a_disponibile"):
                    res = requests.patch(
                        f"{URL_REST}/copie_libri?id_libro=eq.{riga_mod['id_libro']}",
                        headers=HEADERS,
                        json=payload_storno_vendita(),
                    )
                    if res.status_code < 400:
                        st.success("Libro riportato in 'disponibile'.")
                        st.rerun()
                    else:
                        st.error("Errore nel cambio di stato.")

    tab_chiusura, tab_vendita, tab_ritiro = st.tabs(["Chiudi conto", "Storno vendita", "Storno ritiro"])

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

                      # Chiude il conto: i libri venduti diventano 'chiuso_conto' (liquidati),
                      # quelli disponibili diventano a loro volta 'chiuso_conto' (conto chiuso).
                      res_disp = requests.patch(f"{URL_REST}/copie_libri?id_venditore=eq.{cliente['id']}&stato=eq.disponibile", headers=HEADERS, json={"stato": "chiuso_conto"})
                      res_vend = requests.patch(f"{URL_REST}/copie_libri?id_venditore=eq.{cliente['id']}&stato=eq.venduto", headers=HEADERS, json={"stato": "chiuso_conto"})

                      # Verifica che la chiusura sia effettivamente completa: nessun libro
                      # deve rimanere in stato 'venduto' o 'disponibile' (evita che un
                      # libro 'disponibile' resti nel magazzino pur con il conto "chiuso").
                      res_ver = requests.get(
                          f"{URL_REST}/copie_libri?select=stato&id_venditore=eq.{cliente['id']}",
                          headers=HEADERS,
                      )
                      stati_rimasti = [r.get('stato') for r in (res_ver.json() if res_ver.status_code == 200 else [])]
                      chiusura_ok = (
                          res_disp.status_code < 400
                          and res_vend.status_code < 400
                          and not any(s in ('venduto', 'disponibile') for s in stati_rimasti)
                      )

                      if chiusura_ok:
                          st.success("Conto chiuso con successo: libri venduti liquidati e libri disponibili restituiti!")
                          st.rerun()
                      else:
                          st.error("Errore nell'aggiornamento dello stato dei libri su Supabase: alcuni libri risultano ancora attivi. Riprova la chiusura del conto.")
                  except Exception as e:
                      st.error(f"Errore nella chiusura del conto: {str(e)}")

    with tab_vendita:
        libri_venduti = libri_cliente[libri_cliente['stato'] == 'venduto']
        if libri_venduti.empty:
            st.info("Nessuna vendita da storno per questo cliente.")
        elif riga_selezionata is None or riga_selezionata['stato'] != 'venduto':
            st.info("👆 Seleziona un libro VENDUTO dalla tabella qui sopra per stornarne la vendita.")
        else:
            riga_mod = riga_selezionata.to_dict()
            st.markdown(f"**Libro selezionato:** `{riga_mod['id_libro']} - {riga_mod.get('titolo', riga_mod['isbn'])}`")
            if st.button("↩️ Storna vendita", use_container_width=True):
                id_libro = riga_mod['id_libro']
                res = requests.patch(f"{URL_REST}/copie_libri?id_libro=eq.{id_libro}", headers=HEADERS, json=payload_storno_vendita())
                if res.status_code < 400:
                    st.success("Vendita stornata. Il libro è tornato disponibile.")
                else:
                    st.error("Errore nello storno della vendita.")

    with tab_ritiro:
        libri_ritirati = libri_cliente[libri_cliente['stato'] == 'disponibile']
        if libri_ritirati.empty:
            st.info("Nessun ritiro da storno per questo cliente.")
        elif riga_selezionata is None or riga_selezionata['stato'] != 'disponibile':
            st.info("👆 Seleziona un libro DISPONIBILE dalla tabella qui sopra per stornarne il ritiro.")
        else:
            riga_mod = riga_selezionata.to_dict()
            st.markdown(f"**Libro selezionato:** `{riga_mod['id_libro']} - {riga_mod.get('titolo', riga_mod['isbn'])}`")
            if st.button("🗑️ Storna ritiro (rimuovi dal magazzino)", use_container_width=True):
                id_libro = riga_mod['id_libro']
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
