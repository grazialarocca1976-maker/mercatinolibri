import streamlit as st
import pandas as pd
import requests

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_REST = f"https://{PROJECT_ID}.supabase.co/rest/v1"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

HEADERS = {
    "apikey": CHIAVE_SUPABASE,
    "Authorization": f"Bearer {CHIAVE_SUPABASE}",
    "Content-Type": "application/json"
}

def mostra_pagina():
    st.header("📊 Resoconti Finanziari e Reset di Fine Anno")
    
    # 1. Scarichiamo i dati dal cloud
    res_copie = requests.get(f"{URL_REST}/copie_libri?select=*", headers=HEADERS)
    res_cat = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo,prezzo_copertina", headers=HEADERS)
    res_cli = requests.get(f"{URL_REST}/clienti?select=id,codice_personale,nome,cognome", headers=HEADERS)
    
    if res_copie.status_code == 200 and res_cat.status_code == 200 and res_cli.status_code == 200:
        copie = res_copie.json()
        cat = res_cat.json()
        cli = res_cli.json()
        
        if not copie:
            st.info("Nessun libro cartaceo movimentato nel magazzino al momento.")
            return
            
        df_copie = pd.DataFrame(copie)
        df_cat = pd.DataFrame(cat)
        df_cli = pd.DataFrame(cli)
        
        # Uniamo i dati sul PC
        df_m = pd.merge(df_copie, df_cat, on="isbn", how="left")
        df_m['prezzo_copertina'] = df_m['prezzo_copertina'].astype(float)
        
        # Calcoli finanziari
        df_m['Prezzo Vendita'] = (df_m['prezzo_copertina'] / 2) + 0.50
        df_m['Prezzo Liquidazione'] = (df_m['prezzo_copertina'] / 2) - 0.50
        df_m['Tuo Guadagno'] = 1.00
        
        # Calcolo Cassa Totale
        venduti = df_m[df_m['stato'] == 'venduto']
        totale_incassato = venduti['Prezzo Vendita'].sum()
        totale_da_rendere = venduti['Prezzo Liquidazione'].sum()
        tuo_ricavo = venduti['Tuo Guadagno'].sum()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Totale Incassato in Cassa", f"{totale_incassato:.2f} €")
        with col2:
            st.metric("🤝 Totale da Liquidare ai Venditori", f"{totale_da_rendere:.2f} €")
        with col3:
            st.metric("📈 Tuo Guadagno Netto", f"{tuo_ricavo:.2f} €")
            
        st.markdown("---")
        st.subheader("🔍 Ricerca Liquidazione per Singolo Cliente")
        
        opzioni_c = {f"{c['id']} - {c['cognome']} {c['nome']} ({c['codice_personale']})": c['id'] for c in cli}
        scelta_c = st.selectbox("Seleziona una persona per vedere quanto deve avere", list(opzioni_c.keys()))
        id_ricerca = opzioni_c[scelta_c]
        
        libri_utente = df_m[df_m['id_venditore'] == id_ricerca]
        if not libri_utente.empty:
            st.dataframe(libri_utente[['id_libro', 'titolo', 'prezzo_copertina', 'stato']], use_container_width=True)
            libri_venduti_utente = libri_utente[libri_utente['stato'] == 'venduto']
            somma_dovuta = libri_venduti_utente['Prezzo Liquidazione'].sum()
            st.subheader(f"💵 Somma totale da dare a questa persona: {somma_dovuta:.2f} €")
        else:
            st.info("Questo cliente non ha ancora portato libri in conto vendita.")
            
        # --- RESET GENERALE DI FINE ANNO ---
        st.markdown("---")
        st.subheader("⚠️ Zona Pericolosa: Reset Generale")
        st.write("A fine anno scolastico, questo pulsante cancella tutte le copie ritirate e vendute per iniziare il nuovo anno da zero.")
        
        conferma_reset = st.checkbox("Sono consapevole che questa azione svuoterà l'inventario delle copie fisiche.")
        if conferma_reset:
            if st.button("🚨 ESEGUI RESET GENERALE DI FINE ANNO"):
                res_del = requests.delete(f"{URL_REST}/copie_libri", headers=HEADERS)
                if res_del.status_code < 400:
                    st.success("🎉 Reset completato con successo! Il magazzino copie è pronto per il nuovo anno scolastico.")
                    st.rerun()
                else:
                    st.error("Errore durante l'azzeramento.")
