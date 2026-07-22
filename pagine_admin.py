"""
Pagine Admin: tutte le funzioni amministrative in un unico modulo.
- Fascicoli
- Import CSV
- Chiusura Fine Anno
- Cancellazione Utenti
- Conteggi Giornalieri Contanti/Banca
- Progressivo Soldi
- Stampa Ricevute di Restituzione Libri/Soldi
"""
import streamlit as st
import pandas as pd
import requests
import json
import datetime
from io import BytesIO, StringIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from ricevute_condivise import inserisci_intestazione_marconi, inserisci_anagrafica_cliente, inserisci_qrcode_marconi


def mostra_admin(URL_REST, HEADERS):
    """Mostra tutte le funzioni admin in tabs."""
    # Seleziona il tab iniziale da session_state (se impostato)
    tab_iniziale = st.session_state.get("admin_tab", 0)
    if "admin_tab" in st.session_state:
        del st.session_state["admin_tab"]  # reset dopo uso
    
    tab_fascicoli, tab_csv, tab_fine_anno, tab_operatori, tab_utenti, tab_conteggi, tab_progressivo, tab_restituzioni = st.tabs([
        "📁 Fascicoli",
        "📥 Import CSV",
        "📅 Chiusura Fine Anno",
        "👥 Gestione Operatori",
        "🗑️ Cancellazione Utenti",
        "💰 Conteggi Giornalieri",
        "💵 Progressivo Soldi",
        "📄 Restituzioni"
    ])

    with tab_fascicoli:
        _pagina_fascicoli(URL_REST, HEADERS)
    with tab_csv:
        _pagina_import_csv(URL_REST, HEADERS)
    with tab_fine_anno:
        _pagina_fine_anno(URL_REST, HEADERS)
    with tab_operatori:
        _pagina_operatori(URL_REST, HEADERS)
    with tab_utenti:
        _pagina_utenti(URL_REST, HEADERS)
    with tab_conteggi:
        _pagina_conteggi(URL_REST, HEADERS)
    with tab_progressivo:
        _pagina_progressivo(URL_REST, HEADERS)
    with tab_restituzioni:
        _pagina_restituzioni(URL_REST, HEADERS)


# ============================================================
# 1. FASCICOLI
# ============================================================
def _pagina_fascicoli(URL_REST, HEADERS):
    st.subheader("Gestione Fascicoli")
    st.caption("Imposta per ogni copia se prevede fascicoli, quanti sono e quanti sono stati consegnati.")

    id_libro = st.text_input("ID Copia Libro", key="admin_fasc_id", placeholder="es. 42")
    if id_libro.strip():
        try:
            id_l = int(id_libro.strip())
            r = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{id_l}", headers=HEADERS)
            if r.status_code == 200 and r.json():
                copia = r.json()[0]
                st.markdown(f"**Libro ID {id_l}** - ISBN: {copia.get('isbn', '')}")
                isbn = copia.get('isbn', '')
                if isbn:
                    r_cat = requests.get(f"{URL_REST}/catalogo_libri?isbn=eq.{isbn}&select=titolo,autore", headers=HEADERS)
                    if r_cat.status_code == 200 and r_cat.json():
                        cat = r_cat.json()[0]
                        st.markdown(f"*{cat.get('titolo', '')}* - {cat.get('autore', '')}")

                prevede = st.checkbox("Prevede fascicoli", value=copia.get('prevede_fascicoli', False), key="fasc_prevede")
                totale = st.number_input("Totale fascicoli", min_value=0, value=copia.get('totale_fascicoli', 0), key="fasc_totale")
                consegnati = st.number_input("Fascicoli consegnati", min_value=0, value=copia.get('fascicoli_consegnati', 0), key="fasc_cons")

                if st.button("Salva", key="fasc_salva", use_container_width=True):
                    payload = {"prevede_fascicoli": prevede, "totale_fascicoli": totale, "fascicoli_consegnati": consegnati}
                    r_upd = requests.patch(f"{URL_REST}/copie_libri?id_libro=eq.{id_l}", json=payload, headers=HEADERS)
                    if r_upd.status_code in (200, 204):
                        st.success("Dati fascicoli aggiornati!")
                        st.rerun()
                    else:
                        st.error(f"Errore: {r_upd.status_code} - {r_upd.text[:200]}")
            else:
                st.warning(f"Nessuna copia trovata con ID {id_l}")
        except ValueError:
            st.error("Inserisci un ID numerico valido.")

    st.markdown("---")
    st.markdown("### Ricerca multipla per ID Venditore")
    id_venditore = st.text_input("ID Venditore", key="admin_fasc_vend", placeholder="es. 1")
    if id_venditore.strip():
        try:
            id_v = int(id_venditore.strip())
            r = requests.get(f"{URL_REST}/copie_libri?id_venditore=eq.{id_v}&order=id_libro.asc", headers=HEADERS)
            if r.status_code == 200 and r.json():
                copie = r.json()
                st.markdown(f"**{len(copie)} copie trovate per venditore {id_v}**")
                for cp in copie:
                    c1, c2, c3, c4, c5 = st.columns([1, 3, 1, 1, 1])
                    with c1:
                        st.write(f"ID {cp['id_libro']}")
                    with c2:
                        isbn = cp.get('isbn', '')
                        r_cat = requests.get(f"{URL_REST}/catalogo_libri?isbn=eq.{isbn}&select=titolo", headers=HEADERS)
                        titolo = r_cat.json()[0]['titolo'] if r_cat.status_code == 200 and r_cat.json() else isbn
                        st.write(titolo)
                    with c3:
                        st.write(f"Fasc: {'✅' if cp.get('prevede_fascicoli') else '❌'}")
                    with c4:
                        st.write(f"{cp.get('fascicoli_consegnati', 0)}/{cp.get('totale_fascicoli', 0)}")
                    with c5:
                        if st.button(f"Modifica", key=f"fasc_mod_{cp['id_libro']}"):
                            st.session_state["admin_fasc_id"] = str(cp['id_libro'])
                            st.rerun()
            else:
                st.info("Nessuna copia trovata per questo venditore.")
        except ValueError:
            st.error("ID venditore non valido.")


# ============================================================
# 2. IMPORT CSV
# ============================================================
def _pagina_import_csv(URL_REST, HEADERS):
    st.subheader("Import Libri da CSV")
    st.caption("Carica un file CSV con colonne: isbn, titolo, autore, prezzo_copertina, classe, materia")
    st.caption("Il file deve avere l'intestazione (header).")

    uploaded_file = st.file_uploader("Scegli file CSV", type=["csv"], key="admin_csv_upload")
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.markdown(f"**{len(df)} righe trovate**")
            st.dataframe(df.head(10), use_container_width=True, hide_index=True)

            # Verifica colonne obbligatorie
            required = ['isbn', 'titolo']
            missing = [c for c in required if c not in df.columns]
            if missing:
                st.error(f"Colonne mancanti: {', '.join(missing)}. Il CSV deve avere: isbn, titolo, autore, prezzo_copertina, classe, materia")
                return

            if st.button("Importa nel Catalogo", key="admin_csv_import", use_container_width=True):
                with st.spinner("Importazione in corso..."):
                    inseriti = 0
                    errori = 0
                    for _, row in df.iterrows():
                        isbn = str(row.get('isbn', '')).strip()
                        titolo = str(row.get('titolo', '')).strip()
                        if not isbn or not titolo:
                            errori += 1
                            continue
                        # Controlla se esiste già
                        r_check = requests.get(f"{URL_REST}/catalogo_libri?isbn=eq.{isbn}&select=isbn", headers=HEADERS)
                        if r_check.status_code == 200 and r_check.json():
                            # Esiste già, salta
                            continue
                        payload = {
                            "isbn": isbn,
                            "titolo": titolo,
                            "autore": str(row.get('autore', '')).strip(),
                            "prezzo_copertina": float(row.get('prezzo_copertina', 0) or 0),
                            "classe": str(row.get('classe', '')).strip(),
                            "materia": str(row.get('materia', '')).strip(),
                        }
                        r_ins = requests.post(f"{URL_REST}/catalogo_libri", json=payload, headers=HEADERS)
                        if r_ins.status_code in (200, 201):
                            inseriti += 1
                        else:
                            errori += 1
                    st.success(f"Importazione completata: {inseriti} inseriti, {errori} errori/saltati")
        except Exception as e:
            st.error(f"Errore lettura CSV: {e}")


# ============================================================
# 3. CHIUSURA FINE ANNO
# ============================================================
def _pagina_fine_anno(URL_REST, HEADERS):
    st.subheader("Chiusura Fine Anno")
    st.caption("Genera il resoconto completo e scarica il file JSON.")
    st.warning("ATTENZIONE: Questa operazione non cancella i dati. Genera solo un report di riepilogo.")

    if st.button("Genera Resoconto Fine Anno", key="admin_fine_anno_gen", use_container_width=True):
        with st.spinner("Generazione resoconto..."):
            try:
                from export_fine_anno import genera_resoconto_fine_anno
                testo_json, nome_file = genera_resoconto_fine_anno()
                st.download_button(
                    label="📥 Scarica Resoconto JSON",
                    data=testo_json,
                    file_name=nome_file,
                    mime="application/json",
                    key="admin_dl_resoconto"
                )
                st.success("Resoconto generato con successo!")
            except Exception as e:
                st.error(f"Errore: {e}")


# ============================================================
# 4. GESTIONE OPERATORI
# ============================================================
def _pagina_operatori(URL_REST, HEADERS):
    st.subheader("Gestione Operatori")
    st.caption("Crea, modifica ed elimina operatori. Puoi cambiare il ruolo tra 'operatore' e 'admin'.")

    from gestione_operatori import lista_operatori, crea_operatore, elimina_operatore, cambia_ruolo

    # Elenco operatori
    st.markdown("### Elenco Operatori")
    operatori = lista_operatori()
    if operatori:
        for op in operatori:
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                st.write(f"**{op['username']}** - Ruolo: {op.get('ruolo', 'operatore')}")
            with c2:
                if st.button(f"Elimina {op['username']}", key=f"admin_del_op_{op['username']}"):
                    ok, msg = elimina_operatore(op['username'])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with c3:
                nuovo_ruolo = "admin" if op.get("ruolo") != "admin" else "operatore"
                if st.button(f"Rendi {nuovo_ruolo}", key=f"admin_role_{op['username']}"):
                    ok, msg = cambia_ruolo(op['username'], nuovo_ruolo)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with c4:
                st.caption(f"Creato: {op.get('creato_il', '?')[:10]}")
    else:
        st.info("Nessun operatore trovato.")

    st.markdown("---")
    st.markdown("### Crea Nuovo Operatore")
    nuovo_user = st.text_input("Username", key="admin_nuovo_op_user")
    nuovo_pass = st.text_input("Password", type="password", key="admin_nuovo_op_pass")
    nuovo_ruolo = st.selectbox("Ruolo", ["operatore", "admin"], key="admin_nuovo_op_ruolo")
    if st.button("Crea Operatore", key="admin_nuovo_op_btn", use_container_width=True):
        if nuovo_user and nuovo_pass:
            ok, msg = crea_operatore(nuovo_user, nuovo_pass, ruolo=nuovo_ruolo)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        else:
            st.warning("Inserisci username e password.")


# ============================================================
# 5. CANCELLAZIONE UTENTI
# ============================================================
def _pagina_utenti(URL_REST, HEADERS):
    st.subheader("Cancellazione Utenti / Clienti")
    st.caption("Elimina un cliente e tutti i suoi dati associati.")
    st.warning("ATTENZIONE: Operazione irreversibile!")

    id_cliente = st.text_input("ID Cliente da eliminare", key="admin_del_cliente", placeholder="es. 42")
    conferma = st.text_input("Digita 'CONFERMA' per procedere", key="admin_del_confirm", placeholder="CONFERMA")

    if st.button("Elimina Cliente", key="admin_del_btn", use_container_width=True, type="primary"):
        if conferma != "CONFERMA":
            st.error("Devi digitare 'CONFERMA' per procedere.")
            return
        if not id_cliente.strip():
            st.error("Inserisci un ID cliente.")
            return
        try:
            id_c = int(id_cliente.strip())
            # Elimina copie associate
            requests.delete(f"{URL_REST}/copie_libri?id_venditore=eq.{id_c}", headers=HEADERS)
            requests.delete(f"{URL_REST}/copie_libri?id_acquirente=eq.{id_c}", headers=HEADERS)
            # Elimina ricevute
            requests.delete(f"{URL_REST}/ricevute?id_acquirente=eq.{id_c}", headers=HEADERS)
            # Elimina cliente
            r_del = requests.delete(f"{URL_REST}/clienti?id=eq.{id_c}", headers=HEADERS)
            if r_del.status_code in (200, 204):
                st.success(f"Cliente {id_c} e dati associati eliminati!")
            else:
                st.error(f"Errore: {r_del.status_code} - {r_del.text[:200]}")
        except ValueError:
            st.error("ID non valido.")


# ============================================================
# 5. CONTEGGI GIORNALIERI CONTANTI/BANCA
# ============================================================
def _pagina_conteggi(URL_REST, HEADERS):
    st.subheader("Conteggi Giornalieri")
    st.caption("Riepilogo delle vendite per data, suddivise per metodo di pagamento.")

    data_inizio = st.date_input("Data inizio", value=datetime.date.today() - datetime.timedelta(days=7), key="admin_cont_inizio")
    data_fine = st.date_input("Data fine", value=datetime.date.today(), key="admin_cont_fine")

    if st.button("Calcola Conteggi", key="admin_cont_calc", use_container_width=True):
        with st.spinner("Calcolo..."):
            try:
                r = requests.get(
                    f"{URL_REST}/copie_libri?stato=eq.venduto&data_vendita=gte.{data_inizio}&data_vendita=lt.{data_fine + datetime.timedelta(days=1)}&order=data_vendita.asc",
                    headers=HEADERS
                )
                if r.status_code != 200:
                    st.error(f"Errore API: {r.status_code}")
                    return
                vendite = r.json()
                if not vendite:
                    st.info("Nessuna vendita nel periodo.")
                    return

                # Raggruppa per data e metodo
                from collections import defaultdict
                gruppi = defaultdict(lambda: {"contanti": 0.0, "bancomat": 0.0, "altro": 0.0, "n": 0})
                for v in vendite:
                    data = v.get('data_vendita', '')[:10]
                    prezzo = float(v.get('prezzo_inserito_mano', 0) or 0) / 2 + 0.50
                    metodo = (v.get('metodo_pagamento', '') or '').lower()
                    if 'bancomat' in metodo or 'carta' in metodo:
                        gruppi[data]["bancomat"] += prezzo
                    elif 'contanti' in metodo:
                        gruppi[data]["contanti"] += prezzo
                    else:
                        gruppi[data]["altro"] += prezzo
                    gruppi[data]["n"] += 1

                rows = []
                tot_cont = tot_banco = tot_altro = tot_n = 0
                for data in sorted(gruppi.keys()):
                    g = gruppi[data]
                    rows.append({
                        "Data": data,
                        "N. Vendite": g["n"],
                        "Contanti (€)": round(g["contanti"], 2),
                        "Bancomat (€)": round(g["bancomat"], 2),
                        "Altro (€)": round(g["altro"], 2),
                        "Totale (€)": round(g["contanti"] + g["bancomat"] + g["altro"], 2),
                    })
                    tot_cont += g["contanti"]
                    tot_banco += g["bancomat"]
                    tot_altro += g["altro"]
                    tot_n += g["n"]

                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.markdown(f"**Totale periodo:** {tot_n} vendite | Contanti: €{tot_cont:.2f} | Bancomat: €{tot_banco:.2f} | Altro: €{tot_altro:.2f} | **Totale: €{tot_cont+tot_banco+tot_altro:.2f}**")
            except Exception as e:
                st.error(f"Errore: {e}")


# ============================================================
# 6. PROGRESSIVO SOLDI
# ============================================================
def _pagina_progressivo(URL_REST, HEADERS):
    st.subheader("Progressivo Soldi")
    st.caption("Mostra il saldo progressivo per ogni venditore (quanto ha guadagnato).")

    if st.button("Calcola Progressivo", key="admin_prog_calc", use_container_width=True):
        with st.spinner("Calcolo..."):
            try:
                # Leggi tutti i clienti
                r_cli = requests.get(f"{URL_REST}/clienti?select=id,codice_personale,nome,cognome", headers=HEADERS)
                if r_cli.status_code != 200:
                    st.error("Errore lettura clienti")
                    return
                clienti = r_cli.json()

                # Leggi tutte le copie vendute
                r_copie = requests.get(f"{URL_REST}/copie_libri?stato=eq.venduto&select=*", headers=HEADERS)
                if r_copie.status_code != 200:
                    st.error("Errore lettura copie")
                    return
                vendute = r_copie.json()

                # Leggi catalogo per i prezzi
                r_cat = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,prezzo_copertina", headers=HEADERS)
                catalogo = {}
                if r_cat.status_code == 200:
                    for c in r_cat.json():
                        catalogo[c['isbn']] = c

                rows = []
                for cl in clienti:
                    id_cl = cl['id']
                    libri_venduti = [v for v in vendute if v.get('id_venditore') == id_cl]
                    if not libri_venduti:
                        continue
                    totale_liq = 0.0
                    for v in libri_venduti:
                        prezzo_base = float(v.get('prezzo_inserito_mano', 0) or 0)
                        if prezzo_base == 0:
                            isbn = v.get('isbn', '')
                            if isbn in catalogo:
                                prezzo_base = float(catalogo[isbn].get('prezzo_copertina', 0) or 0)
                        liq = (prezzo_base / 2) - 0.50
                        totale_liq += liq
                    rows.append({
                        "ID": id_cl,
                        "Codice": cl.get('codice_personale', ''),
                        "Nome": f"{cl.get('nome', '')} {cl.get('cognome', '')}",
                        "N. Libri Venduti": len(libri_venduti),
                        "Totale da Liquidare (€)": round(totale_liq, 2),
                    })

                if rows:
                    df = pd.DataFrame(rows)
                    df = df.sort_values("Totale da Liquidare (€)", ascending=False)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.markdown(f"**Totale complessivo da liquidare: €{sum(r['Totale da Liquidare (€)'] for r in rows):.2f}**")
                else:
                    st.info("Nessuna vendita registrata.")
            except Exception as e:
                st.error(f"Errore: {e}")


# ============================================================
# 7. STAMPA RICEVUTE DI RESTITUZIONE LIBRI/SOLDI
# ============================================================
def _pagina_restituzioni(URL_REST, HEADERS):
    st.subheader("Stampa Ricevute di Restituzione")
    st.caption("Genera una ricevuta PDF per la restituzione di libri e/o soldi a un venditore.")

    id_venditore = st.text_input("ID Venditore", key="admin_rest_id", placeholder="es. 42")
    if id_venditore.strip():
        try:
            id_v = int(id_venditore.strip())
            r_cli = requests.get(f"{URL_REST}/clienti?id=eq.{id_v}", headers=HEADERS)
            if r_cli.status_code != 200 or not r_cli.json():
                st.warning("Venditore non trovato.")
                return
            venditore = r_cli.json()[0]
            st.markdown(f"**Venditore:** {venditore.get('nome', '')} {venditore.get('cognome', '')} ({venditore.get('codice_personale', '')})")

            # Libri non venduti (da restituire)
            r_copie = requests.get(f"{URL_REST}/copie_libri?id_venditore=eq.{id_v}&stato=neq.venduto", headers=HEADERS)
            if r_copie.status_code == 200 and r_copie.json():
                copie = r_copie.json()
                st.markdown(f"**{len(copie)} libri da restituire**")

                # Recupera titoli dal catalogo
                isbn_list = list(set(c.get('isbn', '') for c in copie if c.get('isbn')))
                catalogo_map = {}
                if isbn_list:
                    r_cat = requests.get(f"{URL_REST}/catalogo_libri?isbn=in.({','.join(isbn_list)})&select=isbn,titolo,autore,prezzo_copertina", headers=HEADERS)
                    if r_cat.status_code == 200:
                        for c in r_cat.json():
                            catalogo_map[c['isbn']] = c

                # Mostra tabella
                rows = []
                for cp in copie:
                    cat = catalogo_map.get(cp.get('isbn', ''), {})
                    rows.append({
                        "ID": cp['id_libro'],
                        "Titolo": cat.get('titolo', 'N/D'),
                        "ISBN": cp.get('isbn', ''),
                        "Prezzo": cp.get('prezzo_inserito_mano', 0) or cat.get('prezzo_copertina', 0),
                    })
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)

                if st.button("Genera Ricevuta di Restituzione PDF", key="admin_rest_pdf", use_container_width=True):
                    with st.spinner("Generazione PDF..."):
                        pdf_bytes = _genera_ricevuta_restituzione(venditore, copie, catalogo_map)
                        if pdf_bytes:
                            st.download_button(
                                label="📥 Scarica Ricevuta Restituzione",
                                data=pdf_bytes,
                                file_name=f"restituzione_{venditore.get('codice_personale', id_v)}.pdf",
                                mime="application/pdf",
                                key="admin_dl_rest"
                            )
            else:
                st.info("Nessun libro da restituire per questo venditore.")
        except ValueError:
            st.error("ID non valido.")


def _genera_ricevuta_restituzione(venditore, copie, catalogo_map):
    """Genera PDF ricevuta di restituzione libri."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    inserisci_intestazione_marconi(story)
    story.append(Paragraph("<b>RICEVUTA DI RESTITUZIONE LIBRI</b>", styles['Title']))
    stile_data = ParagraphStyle('DataOra', parent=styles['Normal'], alignment=2, fontSize=9, textColor=colors.grey)
    story.append(Paragraph(f"Data: {datetime.date.today().isoformat()}", stile_data))
    story.append(Spacer(1, 10))

    inserisci_anagrafica_cliente(story, "VENDITORE", venditore)
    story.append(Spacer(1, 10))

    stile_cella = ParagraphStyle('Cella', parent=styles['Normal'], fontSize=9, leading=11)
    stile_cella_b = ParagraphStyle('CellaB', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold')

    dati_tabella = [[
        Paragraph("<b>ID</b>", stile_cella_b),
        Paragraph("<b>Titolo</b>", stile_cella_b),
        Paragraph("<b>ISBN</b>", stile_cella_b),
        Paragraph("<b>Prezzo (€)</b>", stile_cella_b),
    ]]

    totale_restituito = 0.0
    for cp in copie:
        cat = catalogo_map.get(cp.get('isbn', ''), {})
        prezzo = float(cp.get('prezzo_inserito_mano', 0) or 0) or float(cat.get('prezzo_copertina', 0) or 0)
        totale_restituito += prezzo
        dati_tabella.append([
            Paragraph(str(cp['id_libro']), stile_cella),
            Paragraph(cat.get('titolo', 'N/D').upper(), stile_cella),
            Paragraph(cp.get('isbn', ''), stile_cella),
            Paragraph(f"€{prezzo:.2f}", stile_cella),
        ])

    dati_tabella.append([
        Paragraph("<b>TOTALE</b>", stile_cella_b),
        "",
        "",
        Paragraph(f"<b>€{totale_restituito:.2f}</b>", stile_cella_b),
    ])

    tabella = Table(dati_tabella, colWidths=[50, 250, 120, 80])
    tabella.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(tabella)

    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>Il venditore dichiara di aver ricevuto i libri sopra elencati.</b>", styles['Normal']))
    story.append(Spacer(1, 30))
    story.append(Paragraph("Firma del venditore: ______________________________", styles['Normal']))
    story.append(Spacer(1, 5))
    story.append(Paragraph("Firma dell'operatore: ______________________________", styles['Normal']))

    inserisci_qrcode_marconi(story)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
