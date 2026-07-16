import math
import requests
import streamlit as st
import pandas as pd

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


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


def mostra_pagina():
    st.header("🧾 Gestione conti cliente")
    st.write("Qui puoi chiudere il conto di un cliente, annullare una vendita o annullare un ritiro.")

    res_clienti = requests.get(f"{URL_REST}/clienti?select=id,codice_personale,nome,cognome", headers=HEADERS)
    clienti = res_clienti.json() if res_clienti.status_code == 200 else []
    if not clienti:
        st.info("Nessun cliente registrato.")
        return

    opzioni_clienti = {f"{c['id']} - {c['cognome']} {c['nome']} ({c['codice_personale']})": c for c in clienti}
    cliente_scelto = st.selectbox("Seleziona il cliente", list(opzioni_clienti.keys()))
    cliente = opzioni_clienti[cliente_scelto]

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
    #  - Vendita (chi acquista in cassa): per eccesso (superiore)
    #  - Liquidazione (chi vende/ritira): per difetto (inferiore)
    libri_cliente['Prezzo Vendita (€)'] = libri_cliente['Prezzo Base'].apply(lambda b: math.ceil(((b / 2) + 0.50) * 10) / 10)
    libri_cliente['Liquidazione (€)'] = libri_cliente['Prezzo Base'].apply(lambda b: math.floor(((b / 2) - 0.50) * 10) / 10)

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
            st.success("✅ Prezzo aggiornato. Ricarico i dati...")
            st.rerun()
        else:
            st.error("Errore nell'aggiornamento del prezzo.")

    tab_chiusura, tab_vendita, tab_ritiro = st.tabs(["Chiudi conto", "Storno vendita", "Storno ritiro"])

    with tab_chiusura:
        if st.button("🔒 Chiudi conto cliente", use_container_width=True):
            res = requests.patch(f"{URL_REST}/copie_libri?id_venditore=eq.{cliente['id']}", headers=HEADERS, json=payload_chiusura_conto())
            if res.status_code < 400:
                st.success("Conto chiuso per il cliente.")
            else:
                st.error("Errore nella chiusura del conto.")

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
                    st.success("Ritiro stornato: libro rimosso dal magazzino.")
                    st.rerun()
                else:
                    st.error("Errore nello storno del ritiro.")
