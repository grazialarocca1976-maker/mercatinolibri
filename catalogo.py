import streamlit as st
import pandas as pd

try:
    from supabase import create_client, Client
except ImportError:  # pragma: no cover - fallback per ambienti con installazione incompleta
    create_client = None
    Client = object

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
URL_SUPABASE = f"https://{PROJECT_ID}.supabase.co"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"

@st.cache_resource
def inizializza_supabase():
    if create_client is None:
        return None
    return create_client(URL_SUPABASE, CHIAVE_SUPABASE)

supabase = inizializza_supabase()

def mostra_pagina_interna():
    st.subheader("📂 Carica il Catalogo dei Libri Scolastici")
    file_caricato = st.file_uploader("Scegli un file CSV", type=["csv"])
    
    if file_caricato is not None:
        try:
            df = pd.read_csv(file_caricato, sep=None, engine='python')
            st.success("File letto con successo!")
            
            if st.button("🚀 Elabora e Salva nel Database Online"):
                with st.spinner("Caricamento in corso..."):
                    df.columns = [c.lower().strip() for c in df.columns]
                    if 'prezzo' in df.columns:
                        df['prezzo'] = df['prezzo'].astype(str).str.replace(',', '.', regex=False)
                        df['prezzo'] = pd.to_numeric(df['prezzo'], errors='coerce').fillna(0.0)
                    else:
                        df['prezzo'] = 0.0

                    df['isbn'] = df['isbn'].astype(str).str.strip()
                    df['isbn'] = df['isbn'].apply(lambda x: x[:-2] if x.endswith('.0') else x)
                    df = df[(df['isbn'] != 'nan') & (df['isbn'] != '')]

                    catalogo_unico = {}
                    for index, row in df.iterrows():
                        isbn = row['isbn'].replace(" ", "").replace("-", "").strip()
                        if isbn:
                            catalogo_unico[isbn] = {
                                "isbn": isbn, 
                                "titolo": str(row.get('titolo', '')).strip(), 
                                "sottotitolo": str(row.get('sottotitolo', '')).strip(), 
                                "volume": str(row.get('volume', '')).strip(),
                                "materia": str(row.get('materia', '')).strip(), 
                                "autore": str(row.get('autore', '')).strip(), 
                                "editore": str(row.get('editore', '')).strip(), 
                                "prezzo_copertina": float(row.get('prezzo', 0.0)),
                                "sperimentazione_specializzazione": str(row.get('sperimentazione_specializzazione', '')).strip(), 
                                "classi": str(row.get('classe', '')).strip(), 
                                "anno_corso": str(row.get('anno_corso', '')).strip(),
                                "indirizzo_classe": str(row.get('indirizzo_classe', '')).strip()
                            }
                    
                    libri_da_inviare = list(catalogo_unico.values())
                    if supabase is None:
                        st.warning("Supabase non è disponibile in questo ambiente. Il file è stato elaborato ma non è stato salvato online.")
                    else:
                        supabase.table("catalogo_libri").upsert(libri_da_inviare).execute()
                        st.success(f"🎉 Catalogo allineato! Gestiti {len(libri_da_inviare)} libri nel cloud.")
        except Exception as e:
            st.error(f"Errore di sistema: {e}")
