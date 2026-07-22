"""Modulo per la pagina HOME con i 3 bottoni grandi."""
import streamlit as st


def mostra_home():
    """Mostra la HOME con 3 bottoni grandi: Vendita, Ritiro, Altro."""
    # CSS per bottoni HOME grandi e belli
    st.markdown("""
    <style>
        .home-btn-container {
            display: flex;
            gap: 20px;
            margin-top: 20px;
        }
        .home-btn-container > div {
            flex: 1;
        }
        .home-btn-container .stButton > button {
            width: 100%;
            min-height: 160px !important;
            padding: 45px 30px !important;
            font-size: 36px !important;
            font-weight: 900 !important;
            border-radius: 28px !important;
            border: 5px solid !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 6px 20px rgba(0,0,0,0.12) !important;
            letter-spacing: 2px;
        }
        .home-btn-container .stButton > button:hover {
            transform: translateY(-4px) !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.18) !important;
        }
        .st-key-home_vendita button {
            background: linear-gradient(135deg, #e8f5e9, #c8e6c9) !important;
            border-color: #81c784 !important;
            color: #1b5e20 !important;
        }
        .st-key-home_vendita button:hover {
            background: linear-gradient(135deg, #f1f8e9, #dcedc8) !important;
        }
        .st-key-home_ritiro button {
            background: linear-gradient(135deg, #e3f2fd, #bbdefb) !important;
            border-color: #64b5f6 !important;
            color: #0d47a1 !important;
        }
        .st-key-home_ritiro button:hover {
            background: linear-gradient(135deg, #e8eaf6, #c5cae9) !important;
        }
        .st-key-home_altro button {
            background: linear-gradient(135deg, #fff3e0, #ffe0b2) !important;
            border-color: #ffb74d !important;
            color: #e65100 !important;
        }
        .st-key-home_altro button:hover {
            background: linear-gradient(135deg, #fff8e1, #ffecb3) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### Benvenuto! Scegli l'operazione da eseguire:")

    hc1, hc2, hc3 = st.columns(3)
    with hc1:
        if st.button("Vendita Rapida", key="home_vendita", use_container_width=True):
            st.session_state["flusso_iniziale"] = "vendita"
            st.session_state["pagina"] = "Cassa e Vendita Rapida"
            st.rerun()
    with hc2:
        if st.button("Ritiro Libri", key="home_ritiro", use_container_width=True):
            st.session_state["flusso_iniziale"] = "ritiro"
            st.session_state["pagina"] = "Ritiro Libri (Venditori)"
            st.rerun()
    with hc3:
        if st.button("Altro...", key="home_altro", use_container_width=True):
            st.session_state["pagina"] = "Menu Operazioni"
            st.rerun()
