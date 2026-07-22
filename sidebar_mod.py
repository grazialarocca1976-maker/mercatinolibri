"""Modulo per la sidebar: Libri in possesso, Macro-aree, Logout."""
import streamlit as st
import pandas as pd
import requests


def mostra_sidebar(URL_REST, HEADERS):
    """Mostra la sidebar con:
    - Libri in mio possesso (caricamento lazy)
    - Pulsante Logout
    """
    st.sidebar.markdown("---")
    st.sidebar.caption("Mercatino Libri Usati · Marconi Verona")

    # --- LIBRI IN MIO POSSESSO (caricamento lazy) ---
    with st.sidebar.expander("Libri in mio possesso", expanded=False):
        if st.button("Carica elenco", key="sidebar_carica_possesso", use_container_width=True):
            with st.spinner("Caricamento..."):
                try:
                    r = requests.get(
                        f"{URL_REST}/copie_libri?stato=neq.venduto&order=id_libro.desc&limit=500",
                        headers=HEADERS, timeout=30
                    )
                    copie = r.json() if r.status_code == 200 else []
                    if copie:
                        r2 = requests.get(
                            f"{URL_REST}/catalogo_libri?select=isbn,titolo,autore,prezzo_copertina",
                            headers=HEADERS, timeout=30
                        )
                        cat = r2.json() if r2.status_code == 200 else []
                        df_p = pd.merge(pd.DataFrame(copie), pd.DataFrame(cat), on="isbn", how="left")
                        df_p = df_p[['id_libro', 'isbn', 'titolo', 'autore', 'prezzo_copertina', 'id_venditore']]
                        df_p.columns = ['Cod.', 'ISBN', 'Titolo', 'Autore', 'Prezzo', 'ID Vend.']
                        st.dataframe(df_p, use_container_width=True, hide_index=True)
                        st.caption(f"Totale: {len(df_p)} libri")
                    else:
                        st.info("Nessun libro in possesso.")
                except Exception as e:
                    st.error(f"Errore: {e}")

    # --- LOGOUT ---
    st.sidebar.markdown("---")
    if st.sidebar.button("Esci (Logout)", key="sidebar_logout", use_container_width=True):
        for k in ["logged_in", "operatore", "pagina", "flusso_iniziale", "sidebar_aperta"]:
            if k in st.session_state:
                del st.session_state[k]
        st.query_params.clear()
        st.rerun()
