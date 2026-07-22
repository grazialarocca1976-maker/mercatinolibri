"""Modulo per la pagina Archivio: Ricevute, Clienti, Ristampa Etichette."""
import streamlit as st
import pandas as pd
import requests


def mostra_archivio(URL_REST, HEADERS):
    """Mostra l'Archivio con 3 tab: Ricevute, Clienti, Ristampa Etichette."""
    tab_ricevute, tab_clienti, tab_ristampa = st.tabs([
        "Ricevute", "Clienti", "Ristampa Etichette"
    ])

    with tab_ricevute:
        _mostra_ricevute(URL_REST, HEADERS)

    with tab_clienti:
        _mostra_clienti(URL_REST, HEADERS)

    with tab_ristampa:
        _mostra_ristampa(URL_REST, HEADERS)


def _mostra_ricevute(URL_REST, HEADERS):
    """Tab Ricevute: elenco ricevute dal database REST."""
    st.subheader("Archivio ricevute")
    st.caption("Elenco delle ricevute registrate nel database.")

    PROJECT_ID = st.secrets["supabase"]["project_id"]

    try:
        r = requests.get(
            f"{URL_REST}/ricevute?select=*&order=created_at.desc&limit=100",
            headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            ricevute = r.json()
        else:
            ricevute = []
    except Exception as e:
        st.warning(f"Database non disponibile: {e}")
        ricevute = []

    if not ricevute:
        st.info("Nessuna ricevuta trovata nel database.")
        return

    # Recupera la lista dei file PDF in Storage
    from ricevute_condivise import build_public_storage_url
    try:
        r_storage = requests.post(
            f"https://{PROJECT_ID}.supabase.co/storage/v1/object/list/ricevute",
            headers=HEADERS,
            json={"limit": 200, "prefix": ""},
            timeout=10
        )
        if r_storage.status_code == 200:
            file_storage = {o['name'] for o in r_storage.json()}
        else:
            file_storage = set()
    except:
        file_storage = set()

    # Mappa: tipo -> nome file in italiano per Storage
    MAPPA_TIPI = {"V": "vendita", "R": "ritiro", "C": "chiusura_conto"}

    # Mostra ogni ricevuta con link al PDF (se presente in Storage)
    for ric in ricevute:
        c1, c2 = st.columns([4, 1])
        with c1:
            tipo = ric.get('tipo', '?')
            data = ric.get('data_ricevuta', '')
            totale = ric.get('totale_complessivo', 0)
            metodo = ric.get('metodo_pagamento', '')
            st.markdown(f"**{tipo}** | {data} | €{totale:.2f} | {metodo}")
            st.caption(f"ID: {ric.get('id')} | Cliente: {ric.get('id_acquirente')} | Operatore: {ric.get('operatore', 'N/D')}")
        with c2:
            # Cerca un file in Storage che inizia con il tipo e la data
            tipo_storage = MAPPA_TIPI.get(tipo, tipo.lower())
            # Cerca file che iniziano con "tipo_storage-data"
            prefisso = f"{tipo_storage}-{data}"
            pdf_trovato = None
            for fname in file_storage:
                if fname.startswith(prefisso) and fname.endswith(".pdf"):
                    pdf_trovato = fname
                    break
            if pdf_trovato:
                pdf_url = build_public_storage_url(PROJECT_ID, "ricevute", pdf_trovato)
                st.link_button("📄 Apri PDF", pdf_url, use_container_width=True)
            else:
                st.caption("📄 PDF non disponibile")
        st.markdown("<hr style='margin: 4px 0px; border-color: rgba(49, 51, 63, 0.08);'>", unsafe_allow_html=True)


def _mostra_clienti(URL_REST, HEADERS):
    """Tab Clienti: anagrafica completa."""
    st.subheader("Archivio anagrafica clienti")
    try:
        r = requests.get(f"{URL_REST}/clienti?select=id,codice_personale,nome,cognome,telefono,email&order=cognome.asc", headers=HEADERS, timeout=30)
        clienti = r.json() if r.status_code == 200 else []
    except Exception as e:
        st.error(f"Errore: {e}")
        return

    if not clienti:
        st.info("Nessun cliente registrato.")
    else:
        df_c = pd.DataFrame(clienti)
        df_c = df_c[['id', 'codice_personale', 'nome', 'cognome', 'telefono', 'email']]
        df_c.columns = ['ID', 'Codice', 'Nome', 'Cognome', 'Telefono', 'Email']
        st.dataframe(df_c, use_container_width=True, hide_index=True)


def _mostra_ristampa(URL_REST, HEADERS):
    """Tab Ristampa Etichette: stampa etichette di un venditore, scegliendo quali."""
    st.subheader("Ristampa Etichette")
    st.caption("Inserisci l'ID del venditore per vedere tutti i suoi libri e scegliere quali etichette stampare.")
    from gestore_etichette import genera_griglia_a4_bytes

    id_venditore_input = st.text_input("ID Venditore", key="archivio_ristampa_id_venditore", placeholder="es. 42")

    if "archivio_libri_venditore" not in st.session_state:
        st.session_state["archivio_libri_venditore"] = None
    if "archivio_selezionati" not in st.session_state:
        st.session_state["archivio_selezionati"] = {}

    if id_venditore_input.strip():
        try:
            id_v = int(id_venditore_input.strip())
            if st.button("Carica libri del venditore", key="archivio_carica_libri", use_container_width=True):
                with st.spinner("Caricamento..."):
                    # Query: libri del venditore NON venduti (per ristampa etichette)
                    r = requests.get(
                        f"{URL_REST}/copie_libri?id_venditore=eq.{id_v}&stato=neq.venduto&order=id_libro.asc",
                        headers=HEADERS, timeout=30
                    )
                    if r.status_code == 200:
                        libri = r.json()
                        if libri:
                            # Poi recupera i dati del catalogo per ogni libro
                            isbn_list = list(set(l['isbn'] for l in libri if l.get('isbn')))
                            catalogo_map = {}
                            if isbn_list:
                                isbn_str = ",".join(isbn_list)
                                r_cat = requests.get(
                                    f"{URL_REST}/catalogo_libri?select=isbn,titolo,autore,prezzo_copertina&isbn=in.({isbn_str})",
                                    headers=HEADERS, timeout=30
                                )
                                if r_cat.status_code == 200:
                                    for c in r_cat.json():
                                        catalogo_map[c['isbn']] = c
                            # Unisce i dati
                            for libro in libri:
                                libro['catalogo_libri'] = catalogo_map.get(libro.get('isbn'), {})
                            st.session_state["archivio_libri_venditore"] = libri
                            st.session_state["archivio_selezionati"] = {str(l['id_libro']): True for l in libri}
                            st.rerun()
                        else:
                            st.warning("Nessun libro trovato per questo venditore (solo libri non venduti).")
                            st.session_state["archivio_libri_venditore"] = []
                    else:
                        st.error(f"Errore API: {r.status_code} - {r.text[:200]}")
        except ValueError:
            st.error("Inserisci un ID venditore valido (numero).")

    libri = st.session_state.get("archivio_libri_venditore")
    if libri is not None and len(libri) > 0:
        st.markdown(f"#### Libri del venditore ID {id_venditore_input} ({len(libri)} libri)")
        st.caption("Seleziona/deseleziona i libri da stampare, poi clicca 'Stampa Selezionate'.")

        # Pulsanti per selezionare/deselezionare tutti
        col_sel, col_desel, col_stampa = st.columns([1, 1, 2])
        with col_sel:
            if st.button("Seleziona tutti", key="archivio_sel_tutti", use_container_width=True):
                st.session_state["archivio_selezionati"] = {str(l['id_libro']): True for l in libri}
                st.rerun()
        with col_desel:
            if st.button("Deseleziona tutti", key="archivio_desel_tutti", use_container_width=True):
                st.session_state["archivio_selezionati"] = {str(l['id_libro']): False for l in libri}
                st.rerun()

        # Mostra i libri con checkbox
        for libro in libri:
            id_libro = str(libro['id_libro'])
            catalogo = libro.get('catalogo_libri', {}) or {}
            titolo = catalogo.get('titolo', 'N/D')
            autore = catalogo.get('autore', '')
            prezzo = libro.get('prezzo_inserito_mano', 0) or catalogo.get('prezzo_copertina', 0)
            classe = libro.get('classe', '')
            materia = libro.get('materia', '')

            checked = st.session_state["archivio_selezionati"].get(id_libro, True)
            nuovo_check = st.checkbox(
                f"**{titolo}** - {autore} | €{prezzo:.2f} | {classe} {materia}",
                value=checked,
                key=f"archivio_chk_{id_libro}"
            )
            st.session_state["archivio_selezionati"][id_libro] = nuovo_check

        st.markdown("---")

        # Pulsante stampa
        with col_stampa:
            if st.button("🖨️ Stampa Selezionate", key="archivio_stampa_sel", use_container_width=True):
                selezionati = [l for l in libri if st.session_state["archivio_selezionati"].get(str(l['id_libro']), False)]
                if selezionati:
                    with st.spinner(f"Generazione PDF per {len(selezionati)} etichette..."):
                        dati_etichette = []
                        for libro in selezionati:
                            catalogo = libro.get('catalogo_libri', {}) or {}
                            dati_etichette.append({
                                'id': libro['id_libro'],
                                'titolo': catalogo.get('titolo', 'N/D'),
                                'autore': catalogo.get('autore', ''),
                                'prezzo': libro.get('prezzo_inserito_mano', 0) or catalogo.get('prezzo_copertina', 0),
                                'isbn': libro.get('isbn', ''),
                                'classe': libro.get('classe', ''),
                                'materia': libro.get('materia', ''),
                                'id_venditore': libro['id_venditore'],
                                'barcode': f"{libro['id_venditore']}-{libro['id_libro']}"
                            })
                        pdf_bytes = genera_griglia_a4_bytes(dati_etichette)
                        if pdf_bytes:
                            st.download_button(
                                label="📥 Scarica PDF Etichette",
                                data=pdf_bytes,
                                file_name=f"etichette_venditore_{id_venditore_input}.pdf",
                                mime="application/pdf",
                                key="archivio_dl_etichette"
                            )
                        else:
                            st.error("Errore nella generazione del PDF.")
                else:
                    st.warning("Nessun libro selezionato.")
    elif libri is not None and len(libri) == 0:
        st.info("Nessun libro trovato per questo venditore.")
