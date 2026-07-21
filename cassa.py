import datetime
import re
import pandas as pd
import requests
import streamlit as st

# 1. Recupero variabili di connessione da app.py o session_state
try:
    # Recupera i dati direttamente dalla sessione di Streamlit, evitando di importare app.py
    HEADERS = st.session_state.get("HEADERS", {})
    URL_REST = st.session_state.get("URL_REST", "")
except ImportError:
    # Se non sono in app.py, imposti i fallback/valori standard
    URL_REST = st.session_state.get("URL_REST", "")
    HEADERS = st.session_state.get("HEADERS", {})

# 2. Funzioni di supporto locali
def calcola_prezzo_vendita_scontato(prezzo_base, sconto):
    p = (prezzo_base / 2) + 0.50 - sconto
    return max(p, 0.0)

def format_date_for_db(dt):
    return dt.strftime("%Y-%m-%d")

def prossimo_numero_ricevuta(tipo):
    return 1

def genera_pdf_vendita_multipla(*args, **kwargs):
    return b""

def pubblica_ricevuta_online(*args, **kwargs):
    pass
def mostra_pagina():
    st.title("🛒 Cassa e Vendita Libri")

    if "carrello_cassa" not in st.session_state:
        st.session_state["carrello_cassa"] = []

    # 1. Recupero Clienti per selezione acquirente
    res_clienti = requests.get(f"{URL_REST}/clienti?select=id,cognome,nome,codice_personale", headers=HEADERS)
    clienti_list = res_clienti.json() if res_clienti.status_code == 200 else []

    opzioni_clienti = {}
    chiavi_clienti = []

    for c in clienti_list:
        label = f"{c['cognome']} {c['nome']} ({c.get('codice_personale', 'N/D')})"
        opzioni_clienti[label] = c
        chiavi_clienti.append(label)

    if not chiavi_clienti:
        st.warning("⚠️ Nessun cliente presente a sistema. Registra un cliente prima di procedere.")
        return

    # Memorizzazione ultimo acquirente selezionato
    index_acquirente = 0
    if "id_acquirente_corrente" in st.session_state:
        for idx, key in enumerate(chiavi_clienti):
            if opzioni_clienti[key]["id"] == st.session_state["id_acquirente_corrente"]:
                index_acquirente = idx
                break

    cliente_acquirente = st.selectbox(
        "Seleziona il Cliente Acquirente (Chi Compra)",
        chiavi_clienti,
        index=index_acquirente,
        key="acquirente_select",
        help="Puoi digitare per filtrare l'elenco. La selezione resta memorizzata tra un'operazione e l'altra.",
    )
    dati_acquirente = opzioni_clienti[cliente_acquirente]
    st.session_state["id_acquirente_corrente"] = dati_acquirente["id"]

    if "id_libro_selezionato_cassa" not in st.session_state:
        st.session_state["id_libro_selezionato_cassa"] = None
    id_libro_selezionato = None

    st.caption("🔍 Scrivi qui sotto: riconosco da solo se è il NUMERO sulla copertina, il CODICE BARRE (es. 15-55) o il CODICE del venditore.")
    ricerca_cassa = st.text_input(
        "Cerca per Numero copertina, Codice venditore o Codice a barre (es. 15-55):",
        key="ricerca_unica_cassa",
    ).strip()

    if ricerca_cassa:
        found_by_customer_code = False

        # A. Cerca per codice personale del cliente/venditore
        res_cli_exact = requests.get(f"{URL_REST}/clienti?codice_personale=eq.{ricerca_cassa}", headers=HEADERS)
        cli_exact = res_cli_exact.json() if res_cli_exact.status_code == 200 else []

        if not cli_exact and not ricerca_cassa.isdigit() and len(ricerca_cassa) >= 4:
            res_cli_like = requests.get(f"{URL_REST}/clienti?codice_personale=ilike.*{ricerca_cassa}*", headers=HEADERS)
            cli_exact = res_cli_like.json() if res_cli_like.status_code == 200 else []

        found_copy = None

        if cli_exact:
            found_by_customer_code = True
            id_v = cli_exact[0]['id']
            cod_v = cli_exact[0]['codice_personale']
            st.info(f"👤 Cliente trovato: **{cli_exact[0]['cognome']} {cli_exact[0]['nome']}** ({cod_v})")

            res_libri_v = requests.get(f"{URL_REST}/copie_libri?id_venditore=eq.{id_v}", headers=HEADERS)
            libri_v_list = res_libri_v.json() if res_libri_v.status_code == 200 else []

            if libri_v_list:
                res_cat_all = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo", headers=HEADERS)
                df_cat_all = pd.DataFrame(res_cat_all.json()) if res_cat_all.status_code == 200 else pd.DataFrame()

                mappa_libri_v = {}
                for cp in libri_v_list:
                    titolo_trovato = "Titolo Sconosciuto"
                    if not df_cat_all.empty and cp.get('isbn') in df_cat_all['isbn'].values:
                        titolo_trovato = df_cat_all[df_cat_all['isbn'] == cp['isbn']]['titolo'].values[0]

                    st_raw = str(cp.get('stato', '')).strip().lower()
                    stato_display = "✅ Disponibile" if st_raw in ['disponibile', 'in_carico', 'presente'] else f"❌ {cp.get('stato')}"
                    label = f"ID: {cp.get('id_libro', cp.get('id'))} - {titolo_trovato} ({stato_display})"
                    mappa_libri_v[label] = cp

                scelta_cp = st.selectbox("Seleziona quale vendere:", list(mappa_libri_v.keys()), key="libro_vend_unico")
                copia_sel = mappa_libri_v[scelta_cp]

                st_sel_raw = str(copia_sel.get('stato', '')).strip().lower()
                if st_sel_raw not in ['disponibile', 'in_carico', 'presente']:
                    st.warning(f"⚠️ Il libro selezionato non risulta disponibile (stato nel DB: '{copia_sel.get('stato')}').")
                else:
                    id_libro_selezionato = copia_sel.get('id_libro') or copia_sel.get('id')
                    st.session_state["id_libro_selezionato_cassa"] = id_libro_selezionato
            else:
                st.warning("❓ Questo venditore non ha libri registrati.")

        # B. Ricerca diretta libro per "15-56", ID singolo o Barcode
        if not found_by_customer_code:

            # 1. Se c'è un trattino (es. "15-56")
            if "-" in ricerca_cassa:
                parti = [p.strip() for p in ricerca_cassa.split("-") if p.strip().isdigit()]
                if len(parti) == 2:
                    v_cod, l_id = parti[0], parti[1]
                    
                    # Cerca direttamente per ID del libro
                    res_p = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{l_id}", headers=HEADERS)
                    copie = res_p.json() if res_p.status_code == 200 else []
                    
                    # Se non lo trova con id_libro, prova cercando per colonna 'id'
                    if not copie:
                        res_p = requests.get(f"{URL_REST}/copie_libri?id=eq.{l_id}", headers=HEADERS)
                        copie = res_p.json() if res_p.status_code == 200 else []

                    if copie:
                        found_copy = copie[0]

            # 2. Cerca per ID libro singolo (es. "56")
            if not found_copy:
                m = re.search(r"\d+", ricerca_cassa)
                token = m.group(0) if m else None
                if token:
                    res_by_id = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{token}", headers=HEADERS)
                    if res_by_id.status_code == 200 and res_by_id.json():
                        found_copy = res_by_id.json()[0]

            # 3. Cerca per campo barcode esatto
            if not found_copy:
                try:
                    res_by_bar = requests.get(f"{URL_REST}/copie_libri?barcode=eq.{ricerca_cassa}", headers=HEADERS)
                    if res_by_bar.status_code == 200 and res_by_bar.json():
                        found_copy = res_by_bar.json()[0]
                except Exception:
                    found_copy = None

            # Esito finale e pulizia controllo stato
            if found_copy:
                stato_reale = str(found_copy.get('stato', '')).strip().lower()
                
                # Accetta 'disponibile', 'in_carico' o 'presente' (ignorando spazi e maiuscole)
                if stato_reale not in ['disponibile', 'in_carico', 'presente']:
                    st.error(f"⚠️ Libro trovato (ID: {found_copy.get('id_libro', found_copy.get('id'))}), ma il valore nel DB per lo stato è: **'{found_copy.get('stato')}'**")
                else:
                    id_libro_selezionato = found_copy.get('id_libro') or found_copy.get('id')
                    st.session_state["id_libro_selezionato_cassa"] = id_libro_selezionato
                    st.success(f"🎯 Trovata copia disponibile! ID Libro: **{id_libro_selezionato}**")
            else:
                st.error(f"❌ Nessun libro trovato nel database per l'input: '{ricerca_cassa}'")
        found_by_customer_code = False

        # A. Cerca per codice personale del cliente/venditore
        res_cli_exact = requests.get(f"{URL_REST}/clienti?codice_personale=eq.{ricerca_cassa}", headers=HEADERS)
        cli_exact = res_cli_exact.json() if res_cli_exact.status_code == 200 else []

        if not cli_exact and not ricerca_cassa.isdigit() and len(ricerca_cassa) >= 4:
            res_cli_like = requests.get(f"{URL_REST}/clienti?codice_personale=ilike.*{ricerca_cassa}*", headers=HEADERS)
            cli_exact = res_cli_like.json() if res_cli_like.status_code == 200 else []

        found_copy = None

        if cli_exact:
            found_by_customer_code = True
            id_v = cli_exact[0]['id']
            cod_v = cli_exact[0]['codice_personale']
            st.info(f"👤 Cliente trovato: **{cli_exact[0]['cognome']} {cli_exact[0]['nome']}** ({cod_v})")

            res_libri_v = requests.get(f"{URL_REST}/copie_libri?id_venditore=eq.{id_v}", headers=HEADERS)
            libri_v_list = res_libri_v.json() if res_libri_v.status_code == 200 else []

            if libri_v_list:
                res_cat_all = requests.get(f"{URL_REST}/catalogo_libri?select=isbn,titolo", headers=HEADERS)
                df_cat_all = pd.DataFrame(res_cat_all.json()) if res_cat_all.status_code == 200 else pd.DataFrame()

                mappa_libri_v = {}
                for cp in libri_v_list:
                    titolo_trovato = "Titolo Sconosciuto"
                    if not df_cat_all.empty and cp.get('isbn') in df_cat_all['isbn'].values:
                        titolo_trovato = df_cat_all[df_cat_all['isbn'] == cp['isbn']]['titolo'].values[0]

                    st_norm = str(cp.get('stato', '')).lower()
                    stato_display = "✅ Disponibile" if st_norm == 'disponibile' else f"❌ {cp.get('stato')}"
                    label = f"ID: {cp.get('id_libro', cp.get('id'))} - {titolo_trovato} ({stato_display})"
                    mappa_libri_v[label] = cp

                scelta_cp = st.selectbox("Seleziona quale vendere:", list(mappa_libri_v.keys()), key="libro_vend_unico")
                copia_sel = mappa_libri_v[scelta_cp]

                if str(copia_sel.get('stato')).lower() != 'disponibile':
                    st.warning(f"⚠️ Il libro selezionato non risulta disponibile (stato: {copia_sel.get('stato')}).")
                else:
                    id_libro_selezionato = copia_sel.get('id_libro') or copia_sel.get('id')
                    st.session_state["id_libro_selezionato_cassa"] = id_libro_selezionato
            else:
                st.warning("❓ Questo venditore non ha libri registrati.")

        # B. Ricerca diretta libro per "15-55", ID singolo o Barcode
        if not found_by_customer_code:

            # 1. Se c'è un trattino (es. "15-55")
            if "-" in ricerca_cassa:
                parti = [p.strip() for p in ricerca_cassa.split("-") if p.strip().isdigit()]
                if len(parti) == 2:
                    v_id, l_id = parti[0], parti[1]
                    # Prova prima con il secondo numero come ID del libro
                    res_p = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{l_id}", headers=HEADERS)
                    copie = res_p.json() if res_p.status_code == 200 else []
                    if not copie:
                        # Altrimenti prova con il primo numero
                        res_p = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{v_id}", headers=HEADERS)
                        copie = res_p.json() if res_p.status_code == 200 else []
                    
                    if copie:
                        found_copy = copie[0]

            # 2. Cerca per ID libro diretto (es. "55")
            if not found_copy:
                m = re.search(r"\d+", ricerca_cassa)
                token = m.group(0) if m else None
                if token:
                    res_by_id = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{token}", headers=HEADERS)
                    if res_by_id.status_code == 200 and res_by_id.json():
                        found_copy = res_by_id.json()[0]

            # 3. Cerca nel campo `barcode`
            if not found_copy:
                try:
                    res_by_bar = requests.get(f"{URL_REST}/copie_libri?barcode=eq.{ricerca_cassa}", headers=HEADERS)
                    if res_by_bar.status_code == 200 and res_by_bar.json():
                        found_copy = res_by_bar.json()[0]
                except Exception:
                    found_copy = None

            # Esito finale
            if found_copy:
                st_copia = str(found_copy.get('stato', '')).lower()
                if st_copia != 'disponibile':
                    st.error(f"⚠️ Libro trovato (ID: {found_copy.get('id_libro')}), ma NON è disponibile! Stato attuale: **{found_copy.get('stato')}**")
                else:
                    id_libro_selezionato = found_copy.get('id_libro') or found_copy.get('id')
                    st.session_state["id_libro_selezionato_cassa"] = id_libro_selezionato
                    st.success(f"🎯 Trovata copia disponibile! ID Libro: **{id_libro_selezionato}**")
            else:
                st.error(f"❌ Nessun libro trovato nel database per: '{ricerca_cassa}'")
    # Inserimento nel carrello spesa
    if id_libro_selezionato is not None:
        gia_inserito = any(x['id_libro'] == id_libro_selezionato for x in st.session_state["carrello_cassa"])
        if gia_inserito:
            st.warning("⚠️ Già nel carrello.")
        else:
            res_copie_singola = requests.get(f"{URL_REST}/copie_libri?id_libro=eq.{id_libro_selezionato}", headers=HEADERS)
            copie_res = res_copie_singola.json() if res_copie_singola.status_code == 200 else []

            if len(copie_res) > 0:
                copia = copie_res[0] if isinstance(copie_res, list) and len(copie_res) > 0 else copie_res

                if copia['stato'] != 'disponibile':
                    st.error("❌ Libro non disponibile.")
                else:
                    res_d = requests.get(f"{URL_REST}/catalogo_libri?isbn=eq.{copia['isbn']}", headers=HEADERS)
                    d_list = res_d.json() if res_d.status_code == 200 else []

                    if len(d_list) > 0:
                        libro_dati = d_list[0] if isinstance(d_list, list) and len(d_list) > 0 else d_list
                        prezzo_base = float(copia.get('prezzo_inserito_mano', 0.0) or 0.0)
                        if prezzo_base == 0.0:
                            prezzo_base = float(libro_dati.get('prezzo_copertina', 0.0) or 0.0)
                        prezzo_base_metà = prezzo_base / 2
                        prezzo_vendita = prezzo_base_metà + 0.50

                        res_vendor_info = requests.get(f"{URL_REST}/clienti?id=eq.{copia['id_venditore']}", headers=HEADERS)
                        vendor_info_list = res_vendor_info.json() if res_vendor_info.status_code == 200 else []
                        codice_venditore_completo = vendor_info_list[0]['codice_personale'] if vendor_info_list else ""

                        st.success(f"🎯 Libro Rilevato: {libro_dati['titolo']} (ISBN: {copia['isbn']})")
                        st.write(f"👤 **Codice Venditore Copia:** {codice_venditore_completo}")

                        prevede_f = copia.get("prevede_fascicoli", False)
                        totale_f = copia.get("totale_fascicoli", 0)
                        consegnati_f = copia.get("fascicoli_consegnati", 0)

                        sconto_fascicoli = 0.0
                        if prevede_f:
                            if consegnati_f >= totale_f:
                                st.info(f"📁 **Fascicoli allegati:** COMPLETO ({consegnati_f}/{totale_f} consegnati)")
                            else:
                                st.warning(f"⚠️ **Fascicoli allegati:** MANCANTI/INCOMPLETI ({consegnati_f}/{totale_f} consegnati)")
                                st.warning(
                                    "⚠️ Il testo risulta sprovvisto di tutti i fascicoli. "
                                    "Se il cliente accetta di acquistarlo incompleto, saranno scalati "
                                    "**4,00 € dal prezzo di copertina**."
                                )
                                accetta_sconto = st.checkbox(
                                    "Il cliente accetta lo sconto di 4,00 € per i fascicoli mancanti",
                                    key=f"accetta_fasc_{id_libro_selezionato}",
                                )
                                if accetta_sconto:
                                    sconto_fascicoli = 4.0

                        prezzo_v_finale = calcola_prezzo_vendita_scontato(prezzo_base, sconto_fascicoli)
                        st.metric(
                            label="💰 PREZZO VENDITA (50% COPERTINA)",
                            value=f"{prezzo_v_finale:.2f} €",
                            delta="+0.50 € rimborso spese (voce a parte)" + (f" | -{sconto_fascicoli:.2f} € fascicoli" if sconto_fascicoli > 0 else ""),
                        )

                        if st.button("➕ CONFERMA E INSERISCI QUESTO TITOLO NEL CARRELLO SPESA", use_container_width=True):
                            if prevede_f and consegnati_f < totale_f and sconto_fascicoli == 0.0:
                                st.error(
                                    "❌ Vendita bloccata: il testo è sprovvisto di fascicoli. "
                                    "Completa i fascicoli oppure applica lo sconto di 4,00 € "
                                    "accettato dal cliente."
                                )
                            else:
                                titolo_cart = f"{libro_dati['titolo']} (ISBN: {copia['isbn']})"
                                if prevede_f:
                                    titolo_cart += f" (Fascicoli: {consegnati_f}/{totale_f})"
                                    if sconto_fascicoli > 0:
                                        titolo_cart += " [SCONTO 4€ FASCICOLI]"

                                st.session_state["carrello_cassa"].append({
                                    "id_libro": id_libro_selezionato,
                                    "titolo": titolo_cart,
                                    "prezzo_v": prezzo_v_finale,
                                    "codice_venditore": codice_venditore_completo
                                })
                                st.session_state["id_libro_selezionato_cassa"] = None
                                st.rerun()

    # Gestione del carrello spesa e finalizzazione
    if st.session_state["carrello_cassa"]:
        st.markdown("---")
        st.subheader("🛒 Riepilogo Spesa Attuale:")
        df_c = pd.DataFrame(st.session_state["carrello_cassa"])
        st.dataframe(df_c, use_container_width=True)

        st.caption("✏️ Puoi variare il prezzo di un singolo libro qui sotto (utile per sconti o correzioni):")
        for i, art in enumerate(st.session_state["carrello_cassa"]):
            c_edit_a, c_edit_b = st.columns([4, 1])
            with c_edit_a:
                st.write(f"{i+1}. {art['titolo'][:55]}")
            with c_edit_b:
                nuovo = st.number_input(
                    "Prezzo (€)",
                    min_value=0.0,
                    value=float(art["prezzo_v"]),
                    step=0.10,
                    key=f"prezzo_cart_{i}",
                    label_visibility="collapsed",
                )
                st.session_state["carrello_cassa"][i]["prezzo_v"] = float(nuovo)

        col_storno_c, _ = st.columns(2)
        with col_storno_c:
            idx_storno_c = st.selectbox(
                "🎯 Rimuovi riga errata:", 
                range(len(st.session_state["carrello_cassa"])), 
                format_func=lambda x: f"Riga {x+1}: {st.session_state['carrello_cassa'][x]['titolo'][:30]}"
            )
            if st.button("❌ Rimuovi dal carrello"):
                st.session_state["carrello_cassa"].pop(idx_storno_c)
                st.rerun()

        st.write("")
        totale_spesa = df_c['prezzo_v'].sum()
        rimborso_totale = len(df_c) * 0.50
        totale_con_rimborso = totale_spesa + rimborso_totale

        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.metric(label="📚 TOTALE SOLO LIBRI", value=f"{totale_spesa:.2f} €")
        with c_m2:
            st.metric(label="🎟️ RIMBORSO SPESE GESTIONE", value=f"{rimborso_totale:.2f} €")
        with c_m3:
            st.metric(label="💰 TOTALE COMPLESSIVO PAGATO", value=f"{totale_con_rimborso:.2f} €")

        st.subheader("💳 Scegli il Metodo di Pagamento:")
        metodo_paga = st.radio("Seleziona come paga il cliente:", ["-- Seleziona --", "Contanti", "Bancomat / Carta"], horizontal=True)

        col_conferma, col_annulla = st.columns(2)
        with col_conferma:
            if metodo_paga == "-- Seleziona --":
                st.warning("⚠️ Seleziona la modalità di pagamento (Contanti o Bancomat) per sbloccare la vendita.")
            else:
                if st.button(f"🚀 REGISTRA VENDITA IN {metodo_paga.upper()} E PRODUCI PDF RICEVUTA", use_container_width=True):
                    successo = True
                    messaggio_errore = ""
                    data_oggi_fissa = format_date_for_db(datetime.date.today())

                    for art in st.session_state["carrello_cassa"]:
                        url_up = f"{URL_REST}/copie_libri?id_libro=eq.{art['id_libro']}"
                        dati_aggiornamento_vendita = {
                            "id_acquirente": dati_acquirente['id'],
                            "stato": "venduto",
                            "metodo_pagamento": metodo_paga,
                            "data_vendita": data_oggi_fissa
                        }
                        res_v = requests.patch(url_up, headers=HEADERS, json=dati_aggiornamento_vendita)
                        if res_v.status_code >= 400:
                            successo = False
                            messaggio_errore = res_v.text or "Errore salvataggio."
                            break

                    if successo:
                        n_ricevuta = prossimo_numero_ricevuta("V")
                        numero_ricevuta = f"{n_ricevuta}/V"
                        try:
                            requests.post(
                                f"{URL_REST}/ricevute",
                                headers=HEADERS,
                                json={
                                    "tipo": "V",
                                    "numero_progressivo": n_ricevuta,
                                    "id_acquirente": dati_acquirente['id'],
                                    "metodo_pagamento": metodo_paga,
                                    "totale_libri": float(totale_spesa),
                                    "rimborso_spese": float(rimborso_totale),
                                    "totale_complessivo": float(totale_con_rimborso),
                                    "numero_articoli": len(st.session_state["carrello_cassa"]),
                                    "operatore": st.session_state.get("operatore", "Sconosciuto"),
                                },
                            )
                        except Exception:
                            pass

                        pdf_data = genera_pdf_vendita_multipla(dati_acquirente, st.session_state["carrello_cassa"], totale_spesa, metodo_paga, numero_ricevuta)

                        st.session_state["vendita_completata_pdf"] = pdf_data

                        op_nome = st.session_state.get("operatore", "anon").lower()
                        pubblica_ricevuta_online(
                            st,
                            pdf_data,
                            "vendita",
                            dati_acquirente,
                            data_riferimento=data_oggi_fissa,
                            suffisso=f"op-{op_nome}-{metodo_paga.lower().replace(' ', '-')}-{len(st.session_state['carrello_cassa'])}-articoli"
                        )
                        st.session_state["carrello_cassa"] = []
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(messaggio_errore or "Errore salvataggio.")

        with col_annulla:
            if st.button("🗑️ Cancella Spesa"):
                st.session_state["carrello_cassa"] = []
                st.rerun()