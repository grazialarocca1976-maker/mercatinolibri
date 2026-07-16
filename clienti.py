import streamlit as st
import pandas as pd
import random
import string
import requests

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def mostra_pagina():
    st.header("👤 Gestione Anagrafica Clienti")
    
    # Carichiamo l'elenco clienti una sola volta (serve sia per Modifica che per il tabellone)
    res_c = requests.get(f"{URL_REST}/clienti?select=*&order=id.asc", headers=HEADERS)
    clienti_list = res_c.json() if res_c.status_code == 200 else []
    
    tab_registra, tab_modifica = st.tabs(["➕ Registra Nuovo Cliente", "✏️ Modifica o Elimina Cliente"])
    
    # --- 1. SCHERMATA REGISTRAZIONE CON CONTROLLO DOPPIONI ---
    with tab_registra:
        st.subheader("Inserisci un nuovo cliente")
        
        if "lettere_casuali_correnti" not in st.session_state:
            st.session_state["lettere_casuali_correnti"] = ''.join(random.choices(string.ascii_uppercase, k=2))
            
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome", key="ins_nome").strip()
            cognome = st.text_input("Cognome", key="ins_cognome").strip()
        with col2:
            telefono = st.text_input("Numero di Telefono", key="ins_tel").strip()
            email = st.text_input("Indirizzo Email", key="ins_email").strip().lower()
        
        st.write("")
        if st.button("💾 Salva Nuovo Cliente"):
            if nome and cognome and telefono and email:
                with st.spinner("Verifica duplicati in corso..."):
                    # Usiamo l'elenco già caricato per il controllo incrociato
                    clienti_esistenti = clienti_list

                    doppione_trovato = False
                    for c in clienti_esistenti:
                        # 1. Controllo sul telefono (se inserito)
                        if telefono and c.get('telefono') == telefono:
                            st.error(f"❌ Errore: Il numero di telefono **{telefono}** è già associato al cliente: **{c['id']} - {c['cognome']} {c['nome']}**.")
                            doppione_trovato = True
                            break
                        
                        # 2. Controllo sull'email (se inserita)
                        if email and c.get('email', '').strip().lower() == email:
                            st.error(f"❌ Errore: L'indirizzo email **{email}** è già associato al cliente: **{c['id']} - {c['cognome']} {c['nome']}**.")
                            doppione_trovato = True
                            break
                    
                    if not doppione_trovato:
                        # Calcola il codice personale dinamico (stesse regole di prima)
                        testo_base = f"{cognome}{nome}XXX".upper()
                        tre_lettere = ''.join([c for c in testo_base if c.isalpha()])[:3]
                        tel_pulito = ''.join([c for c in telefono if c.isdigit()])
                        due_numeri = tel_pulito[-2:] if len(tel_pulito) >= 2 else "00"
                        ctrl_lettere = st.session_state["lettere_casuali_correnti"]
                        codice_automatico = f"{tre_lettere}{due_numeri}{ctrl_lettere}"

                        # calcola un suffisso numerico progressivo basato sul massimo ID attuale
                        try:
                            ids = [int(c.get('id', 0)) for c in clienti_esistenti if c.get('id') is not None]
                            next_id_seq = (max(ids) + 1) if ids else 1
                        except Exception:
                            next_id_seq = 1

                        codice_finale = f"{codice_automatico}{next_id_seq:04d}"

                        nuovo_cliente = {
                            "codice_personale": codice_finale,
                            "nome": nome,
                            "cognome": cognome,
                            "telefono": telefono,
                            "email": email
                        }
                        res = requests.post(f"{URL_REST}/clienti", headers=HEADERS, json=nuovo_cliente)
                        if res.status_code < 400:
                            st.success(f"🎉 Cliente {nome} {cognome} registrato con successo! Codice cliente: {codice_finale}")
                            if "lettere_casuali_correnti" in st.session_state:
                                del st.session_state["lettere_casuali_correnti"]
                            st.rerun()
                        else:
                            st.error("Errore nel salvataggio online. Il codice generato potrebbe essere un doppione raro, riprova.")
            else:
                st.warning("⚠️ I campi Nome, Cognome, Numero di Telefono e Indirizzo Email sono tutti obbligatori.")

    # --- 2. SCHERMATA MODIFICA E VARIAZIONE ---
    with tab_modifica:
        st.subheader("Varia i dati o cancella un utente")
        
        if not clienti_list:
            st.info("Nessun cliente registrato nel database.")
        else:
            mappa_clienti = {f"{c['id']} - {c['cognome']} {c['nome']} ({c['codice_personale']})": c for c in clienti_list}
            scelta = st.selectbox("Seleziona il cliente su cui lavorare", list(mappa_clienti.keys()))
            cliente_selezionato = mappa_clienti[scelta]
            
            st.write("---")
            st.text_input("Numero Progressivo assegnato (ID)", value=str(cliente_selezionato['id']), disabled=True)
            st.text_input("Codice Personale (Bloccato di sicurezza)", value=cliente_selezionato['codice_personale'], disabled=True)
            
            mod_nome = st.text_input("Varia Nome", value=cliente_selezionato['nome'])
            mod_cognome = st.text_input("Varia Cognome", value=cliente_selezionato['cognome'])
            mod_tel = st.text_input("Varia Telefono", value=cliente_selezionato['telefono'] or "")
            mod_email = st.text_input("Varia Email", value=cliente_selezionato.get('email', '') or "").strip().lower()
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔄 Aggiorna Dati Anagrafici"):
                    with st.spinner("Controllo variazioni..."):
                        # Anche in fase di modifica controlliamo che i nuovi dati non vadano a sovrapporsi a qualcun altro
                        doppione_mod = False
                        for c in clienti_list:
                            if c['id'] != cliente_selezionato['id']: # Non controlliamo contro se stesso
                                if mod_tel and c.get('telefono') == mod_tel.strip():
                                    st.error(f"❌ Impossibile aggiornare: Il telefono è già usato da un altro cliente (ID: {c['id']}).")
                                    doppione_mod = True
                                    break
                                if mod_email and c.get('email', '').strip().lower() == mod_email:
                                    st.error(f"❌ Impossibile aggiornare: L'email è già usata da un altro cliente (ID: {c['id']}).")
                                    doppione_mod = True
                                    break
                        
                        if not doppione_mod:
                            dati_up = {
                                "nome": mod_nome.strip(), 
                                "cognome": mod_cognome.strip(), 
                                "telefono": mod_tel.strip(),
                                "email": mod_email
                            }
                            url_up = f"{URL_REST}/clienti?id=eq.{cliente_selezionato['id']}"
                            res_up = requests.patch(url_up, headers=HEADERS, json=dati_up)
                            if res_up.status_code < 400:
                                st.success("✅ Dati aggiornati correttamente online!")
                                st.rerun()
                            else:
                                st.error("Modifica rifiutata dal server.")
                        
            with col_btn2:
                if st.button("❌ Elimina Cliente Definitivamente"):
                    url_del = f"{URL_REST}/clienti?id=eq.{cliente_selezionato['id']}"
                    res_del = requests.delete(url_del, headers=HEADERS)
                    if res_del.status_code < 400:
                        st.warning(f"🗑️ Cliente rimosso dal database online!")
                        st.rerun()
                    else:
                        st.error("Impossibile eliminare. Il cliente potrebbe avere libri attivi.")

    # --- TABELLONE GENERALE ---
    st.markdown("---")
    st.subheader("📋 Elenco Totale Clienti")
    if clienti_list:
        df_clienti = pd.DataFrame(clienti_list)
        df_clienti['Riferimento comodo'] = df_clienti['id'].astype(str) + " - " + df_clienti['codice_personale']
        df_clienti = df_clienti[['id', 'Riferimento comodo', 'nome', 'cognome', 'telefono', 'email']]
        df_clienti.columns = ['ID Progressivo', 'Codice per la Cassa', 'Nome', 'Cognome', 'Telefono', 'Email']
        st.dataframe(df_clienti.sort_values(by='ID Progressivo', ascending=False), use_container_width=True, hide_index=True)
