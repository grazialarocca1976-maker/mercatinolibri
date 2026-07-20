import streamlit as st
import pandas as pd
import requests
import datetime
from concurrent.futures import ThreadPoolExecutor
from ricevute_condivise import list_receipts, build_public_storage_url

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json"
}


@st.cache_data(show_spinner=False, ttl=60)
def _carica_dati():
    """Carica in parallelo copie, catalogo e clienti (cache 60s)."""
    def _get(url, params=None):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_copie = ex.submit(_get, f"{URL_REST}/copie_libri?select=*")
        f_cat = ex.submit(_get, f"{URL_REST}/catalogo_libri?select=isbn,titolo,autore,prezzo_copertina")
        f_cli = ex.submit(_get, f"{URL_REST}/clienti?select=*")
        return f_copie.result(), f_cat.result(), f_cli.result()


@st.cache_data(show_spinner=False, ttl=120)
def _carica_ricevute():
    """Carica l'elenco delle ricevute dal cloud storage (cache 120s)."""
    return list_receipts(bucket_name="ricevute", project_id=PROJECT_ID, api_key=CHIAVE_SUPABASE, limit=300)


def mostra_pagina():
    st.header("🔍 Ricerca Avanzata Copie e Ricevute")
    st.markdown("Cerca qualsiasi copia di un libro presente nel sistema e visualizza la sua cronologia completa e le ricevute collegate.")
    
    with st.spinner("Caricamento dati dal server..."):
        copie, cat, cli = _carica_dati()
        
    if not copie:
        st.info("Nessuna copia fisica registrata nel sistema.")
        return
        
    df_copie = pd.DataFrame(copie)
    df_cat = pd.DataFrame(cat)
    df_cli = pd.DataFrame(cli)
    
    # Rinominiamo colonne per evitare collisioni nel merge
    if not df_cli.empty:
        df_venditori = df_cli.copy()
        df_venditori.columns = [f"vend_{col}" if col != 'id' else 'id_venditore_key' for col in df_venditori.columns]
        
        df_acquirenti = df_cli.copy()
        df_acquirenti.columns = [f"acq_{col}" if col != 'id' else 'id_acquirente_key' for col in df_acquirenti.columns]
    else:
        df_venditori = pd.DataFrame()
        df_acquirenti = pd.DataFrame()
        
    # Unione dati
    df_m = pd.merge(df_copie, df_cat, on="isbn", how="left")
    if not df_venditori.empty:
        df_m = pd.merge(df_m, df_venditori, left_on="id_venditore", right_on="id_venditore_key", how="left")
    if not df_acquirenti.empty:
        df_m = pd.merge(df_m, df_acquirenti, left_on="id_acquirente", right_on="id_acquirente_key", how="left")
        
    # Prepara la ricerca testuale
    st.markdown("### 🔎 Inserisci i filtri di ricerca")
    search_query = st.text_input("Cerca per ISBN, Titolo, Progressivo Copia, Venditore o Acquirente (Nome, Cognome, Codice)").strip().lower()
    
    df_filtrato = df_m.copy()
    
    if search_query:
        cond_id = df_filtrato['id_libro'].astype(str) == search_query
        cond_isbn = df_filtrato['isbn'].astype(str).str.lower().str.contains(search_query)
        cond_titolo = df_filtrato['titolo'].astype(str).str.lower().str.contains(search_query)
        cond_autore = df_filtrato['autore'].astype(str).str.lower().str.contains(search_query)
        
        cond_vend = pd.Series(False, index=df_filtrato.index)
        cond_acq = pd.Series(False, index=df_filtrato.index)
        
        if 'vend_nome' in df_filtrato.columns:
            cond_vend = (
                df_filtrato['vend_nome'].astype(str).str.lower().str.contains(search_query) |
                df_filtrato['vend_cognome'].astype(str).str.lower().str.contains(search_query) |
                df_filtrato['vend_codice_personale'].astype(str).str.lower().str.contains(search_query)
            )
        if 'acq_nome' in df_filtrato.columns:
            cond_acq = (
                df_filtrato['acq_nome'].astype(str).str.lower().str.contains(search_query) |
                df_filtrato['acq_cognome'].astype(str).str.lower().str.contains(search_query) |
                df_filtrato['acq_codice_personale'].astype(str).str.lower().str.contains(search_query)
            )
            
        df_filtrato = df_filtrato[cond_id | cond_isbn | cond_titolo | cond_autore | cond_vend | cond_acq]
        
    if df_filtrato.empty:
        st.warning("⚠️ Nessuna copia corrisponde ai criteri di ricerca.")
        return
        
    # Mostriamo una tabella riassuntiva dei risultati
    df_vis = df_filtrato.copy()
    colonne_presenti = ['id_libro', 'isbn', 'titolo', 'stato']
    nomi_colonne = ['N. Copia', 'ISBN', 'Titolo', 'Stato']
    
    if 'vend_codice_personale' in df_vis.columns:
        colonne_presenti.append('vend_codice_personale')
        nomi_colonne.append('Cod. Venditore')
    if 'acq_codice_personale' in df_vis.columns:
        colonne_presenti.append('acq_codice_personale')
        nomi_colonne.append('Cod. Acquirente')
        
    df_tabella = df_vis[colonne_presenti]
    df_tabella.columns = nomi_colonne
    
    st.dataframe(df_tabella.sort_values(by='N. Copia', ascending=False), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("### ℹ️ Dettaglio Copia e Ricevute")
    
    # Selezione singola copia per visualizzare la cronologia completa e ricevute
    opzioni_scelta = {f"Copia N. {row['id_libro']} - {row['titolo'][:40]}": row for _, row in df_filtrato.iterrows()}
    copia_scelta_label = st.selectbox("Seleziona una copia per vedere i dettagli completi:", list(opzioni_scelta.keys()))
    
    if copia_scelta_label:
        copia_selezionata = opzioni_scelta[copia_scelta_label]
        
        col_inf1, col_inf2 = st.columns(2)
        with col_inf1:
            st.markdown(f"**🔢 Numero Progressivo Copia:** {copia_selezionata['id_libro']}")
            st.markdown(f"**📖 Titolo Libro:** {copia_selezionata['titolo']}")
            st.markdown(f"**✍️ Autore:** {copia_selezionata['autore']}")
            st.markdown(f"**🆔 ISBN:** {copia_selezionata['isbn']}")
            st.markdown(f"**📊 Stato Attuale:** `{copia_selezionata['stato'].upper()}`")
            
            # Mostra dettagli fascicoli se presenti
            prevede_f = copia_selezionata.get("prevede_fascicoli", False)
            totale_f = copia_selezionata.get("totale_fascicoli", 0)
            cons_f = copia_selezionata.get("fascicoli_consegnati", 0)
            if prevede_f:
                st.markdown(f"**📁 Fascicoli Allegati:** `SÌ` ({cons_f}/{totale_f} consegnati)")
            else:
                st.markdown(f"**📁 Fascicoli Allegati:** `NO`")
            
        with col_inf2:
            st.markdown("#### 👤 Informazioni Venditore")
            if 'vend_nome' in copia_selezionata and pd.notna(copia_selezionata['vend_nome']):
                st.markdown(f"**Nominativo:** {copia_selezionata['vend_cognome']} {copia_selezionata['vend_nome']}")
                st.markdown(f"**Codice Personale:** `{copia_selezionata['vend_codice_personale']}`")
                st.markdown(f"**Contatti:** {copia_selezionata['vend_telefono']} | {copia_selezionata['vend_email']}")
            else:
                st.markdown("*Nessun venditore collegato*")
                
            st.markdown("#### 👤 Informazioni Acquirente")
            if 'acq_nome' in copia_selezionata and pd.notna(copia_selezionata['acq_nome']):
                st.markdown(f"**Nominativo:** {copia_selezionata['acq_cognome']} {copia_selezionata['acq_nome']}")
                st.markdown(f"**Codice Personale:** `{copia_selezionata['acq_codice_personale']}`")
                st.markdown(f"**Data Vendita:** {copia_selezionata.get('data_vendita', 'N.D.')}")
                st.markdown(f"**Metodo di Pagamento:** {copia_selezionata.get('metodo_pagamento', 'N.D.')}")
            else:
                st.markdown("*Disponibile (Non ancora venduto)*")
                
        # --- CRONOLOGIA DELLE VARIAZIONI DI STATO ---
        st.markdown("#### 🕒 Cronologia Variazioni di Stato")
        cronologia = []
        
        # 1. Presa in carico
        data_ritiro = "N.D."
        if 'vend_nome' in copia_selezionata and pd.notna(copia_selezionata['vend_nome']):
            cronologia.append({
                "Data": "Inizio",
                "Stato": "DISPONIBILE",
                "Operazione": f"Presa in carico / Ritiro in magazzino. Consegnato da {copia_selezionata['vend_cognome']} {copia_selezionata['vend_nome']} ({copia_selezionata['vend_codice_personale']})"
            })
            
        # 2. Vendita
        if copia_selezionata['stato'] == 'venduto' and pd.notna(copia_selezionata.get('acq_nome')):
            cronologia.append({
                "Data": copia_selezionata.get('data_vendita', 'N.D.'),
                "Stato": "VENDUTO",
                "Operazione": f"Venduto a {copia_selezionata['acq_cognome']} {copia_selezionata['acq_nome']} ({copia_selezionata['acq_codice_personale']}) con pagamento {copia_selezionata.get('metodo_pagamento', 'N.D.')}"
            })
            
        st.table(pd.DataFrame(cronologia))
        
        # --- RICERCA RICEVUTE COLLEGATE ---
        st.markdown("#### 📁 Ricevute PDF Collegate (Cloud Storage)")
        res_bucket = _carica_ricevute()
        
        if res_bucket.get("ok"):
            oggetti = res_bucket.get("objects", [])
            trovate = False
            
            # Filtriamo le ricevute che contengono il codice personale del venditore (ritiro) o dell'acquirente (vendita)
            def _codice_pulito(valore):
                if valore is None or (isinstance(valore, float) and pd.isna(valore)):
                    return ""
                return str(valore).lower().replace("-", "")

            cod_vend = _codice_pulito(copia_selezionata.get('vend_codice_personale'))
            cod_acq = _codice_pulito(copia_selezionata.get('acq_codice_personale'))
            
            for obj in oggetti:
                name = obj.get('name', '')
                name_clean = name.lower().replace("-", "")
                
                is_ritiro = cod_vend and cod_vend in name_clean and "ritiro" in name.lower()
                is_vendita = cod_acq and cod_acq in name_clean and "vendita" in name.lower()
                
                if is_ritiro or is_vendita:
                    trovate = True
                    url_pubblico = build_public_storage_url(PROJECT_ID, "ricevute", name)
                    tipo_doc = "📥 RICEVUTA RITIRO" if is_ritiro else "💰 RICEVUTA VENDITA"
                    
                    st.markdown(f"**{tipo_doc}:** [{name}]({url_pubblico})")
                    
            if not trovate:
                st.info("Nessuna ricevuta PDF archiviata online trovata per questa copia.")
        else:
            st.warning("⚠️ Impossibile collegarsi all'archivio cloud delle ricevute.")