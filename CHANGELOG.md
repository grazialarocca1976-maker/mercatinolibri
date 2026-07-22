# Changelog — Mercatino Libri Usati (Marconi Verona)

<!-- ISTRUZIONE PER AGENTI AI (Cline, Codex, ecc.): ogni volta che modifichi/crei file di questo progetto, DEVI registrare la modifica in questo file, nella sezione del giorno corrente (formato ## AAAA-MM-GG). Se non esiste la sezione del giorno, creala. Mantieni lo stesso stile: elenchi puntati raggruppati per area. Leggi questo file prima di iniziare e aggiornalo alla fine. NON caricare mai .streamlit/secrets.toml nel repository. -->

Tutte le modifiche significative al progetto vengono documentate in questo file.

## 2026-07-23 — v2.2.1 — Fix Macro Aree: filtro separato per anno (1° o 3°)

### Macro Aree
- **Fix critico**: la funzione `costruisci_filtro_area_per_indirizzo` restituiva SEMPRE entrambi gli anni (1° e 3°), mescolando i risultati. Ora accetta il parametro `anno_classe` e restituisce SOLO il filtro per l'anno richiesto (`macro_aree.py`).
- **Chiamata aggiornata**: `mostra_selector_macro_aree` ora passa `anno_classe` a `costruisci_filtro_area_per_indirizzo`, garantendo che la ricerca 1° anno trovi SOLO libri con classi di 1° anno, e la ricerca 3° anno trovi SOLO libri con classi di 3° anno (`macro_aree.py`).
- **Nessuna mescolanza**: libri di 3° (es. "VALORE STORIA 1", "TUTTI I COLORI DELLA MATEMATICA - SECONDO BIENNIO") non appaiono più nella ricerca 1° anno e viceversa (`macro_aree.py`).

## 2026-07-22 — Bottoni HOME ingranditi, Ristampa Etichette in terzo tab Archivio, text_input

### Interfaccia Home
- **Bottoni HOME ingranditi**: i 3 pulsanti (VENDITA, RITIRO, ALTRO) ora hanno `padding: 40px`, `font-size: 28px`, gradienti colorati distinti (verde, blu, giallo) e ombra pronunciata (`app.py`).
- **CSS `.home-btn-container`**: aggiunto contenitore flex con gap 20px e animazione hover con `translateY(-4px)` (`app.py`).

### Archivio
- **5 tab in Archivio**: aggiunto il quinto tab "🖨️ Ristampa Etichette" dopo Ricevute, Clienti, Libri in possesso, Libri venduti (`app.py`).
- **Ristampa Etichette con text_input**: sostituiti i selectbox con campi `text_input` (ID Venditore + Codice Copia), nessuna chiamata API al caricamento della pagina (`app.py`).
- **Guida Archivio aggiornata**: menziona "Ristampa Etichette" tra le sezioni disponibili (`app.py`).

### Ritiro
- **3 tab in Ritiro**: Ritiro, Archivio, Ristampa Etichette (già implementato in precedenza, confermato funzionante) (`ritiro.py`).

### Gestore Etichette
- **text_input invece di selectbox**: campi per ID Venditore e Codice Copia ora sono `text_input` (nessuna chiamata API al caricamento) (`gestore_etichette.py`).
- **Barcode numerico**: formato `id_venditore-id_libro` (es. `42-101`) (`gestore_etichette.py`).
- **Fascicoli in rosso**: evidenziati in rosso e più visibili sulle etichette (`gestore_etichette.py`).
- **Volume/Classe sulle etichette A4**: aggiunto campo Volume/Classe (`gestore_etichette.py`).

## 2026-07-22 — Configurazione indirizzi di studio da secrets.toml

### Configurazione centralizzata
- **Mappa indirizzi di studio spostata in `secrets.toml`**: la configurazione delle classi raggruppate per indirizzo (Liceo, Tecnico, Professionale) non è più hardcoded in `ritiro.py` ma letta dinamicamente da `.streamlit/secrets.toml` tramite la nuova sezione `[indirizzi]`. Ogni indirizzo contiene l'elenco delle classi che condividono lo stesso percorso di studi (`ritiro.py`).
- **Nuove funzioni `_carica_indirizzi_da_secrets()` e `_costruisci_filtro_area_per_indirizzo()`**: la prima carica la configurazione da `st.secrets` con fallback di default; la seconda costruisce automaticamente il filtro OR per Supabase a partire dal nome dell'indirizzo (`ritiro.py`).
- **Selectbox dinamico per le aree**: il menu a tendina delle macro-aree ora si popola automaticamente dalla configurazione in `secrets.toml`, senza bisogno di modificare il codice quando cambiano gli indirizzi (`ritiro.py`).
- **Macro-aree estese anche alle classi 3ª**: la visualizzazione delle macro-aree non è più limitata alle sole classi prime (`startswith("1")`), ma funziona anche per le classi terze (`"3"`) e potenzialmente per qualsiasi anno, estraendo dinamicamente la prima cifra della classe inserita (`ritiro.py`).
- **Filtro per lettera indirizzo**: la configurazione in `secrets.toml` ora usa la **lettera identificativa dell'indirizzo** (es. `L` per Logistica e Trasporti, `I` per Informatica e Telecomunicazioni, `E` per Elettronica) invece dei nomi completi delle classi. Il filtro cerca tutte le classi che contengono quella lettera, a prescindere dall'anno e dalla sezione (es. `L` trova 1AL, 1BL, 3AL, 3BL...) (`secrets.toml`, `ritiro.py`).
- **Modulo condiviso `macro_aree.py`**: create le funzioni `carica_indirizzi_da_secrets()`, `costruisci_filtro_area_per_indirizzo()` e `mostra_selector_macro_aree()` in un modulo separato e riutilizzabile (`macro_aree.py`).
- **Macro-aree nella sidebar**: aggiunti due expander "Classi 1ª" e "Classi 3ª" nella barra laterale di `app.py`, accessibili da qualsiasi pagina dell'app (`app.py`).
- **Macro-aree in Cassa**: il selettore macro-aree è ora disponibile anche nella pagina di vendita (`cassa.py`).
- **Ritiro.py usa `macro_aree`**: sostituite le funzioni locali `_carica_indirizzi_da_secrets()` e `_costruisci_filtro_area_per_indirizzo()` con l'import dal modulo condiviso (`ritiro.py`).
- **Flusso semplificato VENDITA/RITIRO**: i bottoni HOME ora portano direttamente a Cassa e Ritiro, senza passare da Registrazione Clienti (`app.py`).
- **Selezione/creazione clienti inline**: in Cassa e Ritiro ora c'è un unico selettore che permette sia di scegliere un cliente esistente sia di crearne uno nuovo, senza cambiare pagina (`cassa.py`, `ritiro.py`).
- **"Libri in mio possesso" nella sidebar**: spostato dall'Archivio alla barra laterale, accessibile da tutta l'app (`app.py`).
- **Pagina "Registrazione Clienti"**: rimane solo per modificare/eliminare clienti esistenti (admin), accessibile da ALTRO (`app.py`).
- **Archivio semplificato**: rimosse le sezioni "Libri in mio possesso" e "Libri venduti" (ridondanti: la prima è nella sidebar, la seconda in Gestione Conti). Archivio ora ha solo Ricevute (con filtri) e Clienti (`app.py`).
- **Fix NameError `_archivio_copie`**: spostate le funzioni di archivio PRIMA della sidebar che le chiama, per evitare NameError in esecuzione (`app.py`).






## 2026-07-20 — Fascicoli: gestione, stampa, ricerca unificata e test


### Ritiro Libri (Venditori)
- **Ricerca unificata (niente più pallini)**: sostituito il `radio` con 3 modalità (ISBN / Titolo / Classe) con un UNICO campo di testo che riconosce automaticamente se hai scritto un ISBN (anche parziale), un titolo/autore o una classe (es. `1AI`), mostrando l'aiuto contestuale (`ritiro.py`).
- **Fix crash stampa etichette rotolo TM-L90**: `genera_pdf_rotolo_etichette` ora ritorna SEMPRE bytes PDF validi (prima, con un solo libro, ritornava `None` dentro il ciclo → `StreamlitAPIException: Invalid binary data format: NoneType`). Aggiunto anche controllo difensivo `if pdf_et_data is None` prima di `st.download_button`. Inserita l'interruzione di pagina PRIMA di ogni etichetta (più robusto) e una riga "Nessun libro" se la lista è vuota (`ritiro.py`).
- **Memoria scelta fascicoli per ISBN**: se lo STESSO ISBN viene ritirato 2-3 volte (anche da persone/venditori diversi nella stessa sessione di lavoro), i campi fascicoli vengono pre-compilati con l'ultima scelta fatta (`st.session_state["fascicoli_per_isbn"]`, chiavi dinamiche per ISBN) (`ritiro.py`).
- **Codice identificativo della persona sulle etichette**: aggiunto `Vend: <codice_personale>` (es. `BOR85RW0001`) su etichette rotolo TM-L90 — prima mancava il codice del venditore (mostrava solo `id_venditore-id_libro`). `prepara_dati_etichette` ora include `codice_personale` (`ritiro.py`, `gestore_etichette.py`).
- **Fascicoli su TUTTI i tipi di stampa**: ora i fascicoli compaiono anche nella ricevuta di ritiro A4 (`(FASCICOLI: X/Y)` nel titolo) e nell'inventario per materia A4 (`genera_pdf_ricevuta`, `genera_pdf_inventario_materia`). Erano già presenti su etichette rotolo TM-L90, etichette A4 (bytes/file), anteprima e ricevuta vendita cassa.
- **Quantità reale nel carrello**: l'inserimento in DB ora esegue un ciclo sulle copie richieste (`quantita`), cosi più copie dello stesso libro creano righe distinte (`ritiro.py`).
- **Layout etichette A4 personalizzato**: nuovo `calcola_layout_personalizzato(foglio_l, foglio_h, totale_etichette)` che calcola automaticamente colonne/righe e dimensioni etichetta; aggiunta la voce "Personalizzato" nel `selectbox` dei layout (`ritiro.py`, `gestore_etichette.py`).
- **Download button etichette non scompare al rerun**: i `st.download_button` di A4 e ristampa ora vivono fuori dal blocco del pulsante (salvati in `st.session_state`), cosi restano visibili dopo il `st.rerun()` (`ritiro.py`).

### Cassa e Vendita Rapida
- **Ricerca unificata (niente più pallini)**: sostituito il `radio` (Numero / Codice venditore / Barcode) con un UNICO campo che riconosce da solo numero copertina, codice venditore (es. `BOR85RW0001`) o codice a barre, con warning chiari se il libro non è disponibile (`cassa.py`).
- **Sconto 4€ su fascicoli incompleti**: se un libro prevede fascicoli e quelli consegnati sono < totali, avviso chiaro + checkbox "cliente accetta sconto di 4,00 €". Vendita bloccata se incompleti e sconto non accettato. Il prezzo vendita = (prezzo_base − sconto) / 2 (`cassa.py`).
- **Helper puro `calcola_prezzo_vendita_scontato(prezzo_base, sconto_fascicoli=0.0)`** estratto dal flusso per testabilità (`cassa.py`).

### Gestione Conti Cliente
- **Colonna "Fascicoli" nella tabella**: mostra `Sì (X/Y)` o `No` per ogni libro, calcolata dai campi `prevede_fascicoli`/`totale_fascicoli`/`fascicoli_consegnati` (`gestione_conti.py`).
- **Modifica fascicoli nella "Correggi prezzo"**: ora oltre al prezzo si può spuntare "Prevede fascicoli" e impostare totale/consegnati; l'aggiornamento fa PATCH su `copie_libri` con fallback (se le nuove colonne non esistono ancora, riprova aggiornando solo il prezzo) (`gestione_conti.py`).
- **Fascicoli nella ricevuta di ritiro rigenerata**: `_rigenera_ricevuta_ritiro_completa` annota `(Fascicoli: X/Y)` nel titolo (`gestione_conti.py`).

### Cerca Libro (Archivio)
- **Dettagli fascicoli**: nella scheda del libro trovato ora compare `📁 Fascicoli Allegati: SÌ (X/Y)` o `NO` (`cerca_libro.py`).

### Registrazione Clienti
- **Elenco "Clienti già registrati" cliccabile**: nuovo `expander` con `radio` di TUTTI i clienti; la selezione si sincronizza istantaneamente col `selectbox` del tab "Cerca" (senza ricaricare la pagina) (`clienti.py`).

### Gestore Etichette
- **Campi fascicoli in `prepara_dati_etichette`**: ora normalizza `prevede_fascicoli`, `totale_fascicoli`, `fascicoli_consegnati` e include `codice_personale` (`gestore_etichette.py`).
- **Fascicoli su etichette A4 (bytes e file) e anteprima**: `genera_griglia_a4_bytes`, `genera_griglia_a4` e `genera_preview_etichette` mostrano `FASC: X/Y` quando il libro prevede fascicoli. Disegno etichette A4 rifattorizzato in `_disegna_etichetta_a4` (più leggibile, niente sovrapposizioni) (`gestore_etichette.py`).
- **Fascicoli su stampa TM-L90 diretta**: `stampa_singola_tml90` / `stampa_etichette_tm_l90` stampano `Fascicoli: X/Y`; barcode ingrandito (width 3, height 70) (`gestore_etichette.py`).
- **Layout personalizzato**: `calcola_layout_personalizzato` supporta fogli e numeri di etichette arbitrari, con scala dei font proporzionale (`gestore_etichette.py`).

### Database (SQL)
- **`crea_colonne_fascicoli.sql`** (nuovo): script per aggiungere le colonne `prevede_fascicoli`, `totale_fascicoli`, `fascicoli_consegnati` a `copie_libri` su Supabase. I moduli fanno fallback se le colonne non esistono ancora (`crea_colonne_fascicoli.sql`).

### Test automatici (pytest)
- **`tests/test_gestore_etichette.py`** (esteso): `prepara_dati_etichette` include i campi fascicoli; `genera_preview_etichette` mostra `FASC: X/Y`; `genera_griglia_a4_bytes` genera PDF valido con fascicoli; `stampa_etichette_tm_l90` passa i fascicoli alla stampante (mock `Usb`).
- **`tests/test_ritiro_etichette.py`** (nuovo): `genera_pdf_rotolo_etichette` non ritorna `None` (1 libro, lista vuota) e genera PDF valido con fascicoli.
- **`tests/test_cassa_fascicoli.py`** (nuovo): `calcola_prezzo_vendita_scontato` con/senza sconto 4€, non negativo, prezzo zero.

## 2026-07-19 — v2.1.0 (Versione Corrente)

### Interfaccia e navigazione
- **Pulsante MENU solo con barra laterale chiusa**: il controllo nativo di Streamlit che riapre la sidebar viene ora mostrato come pulsante `☰ MENU`, posizionato in alto a sinistra e visibile solo quando la barra laterale è collassata (`app.py`, CSS `collapsedControl` / `stSidebarCollapsedControl`). Rimosso il vecchio tentativo di gestire lo stato della sidebar via `session_state`, non sincronizzabile con il click nativo di Streamlit.
- **Correzione pulsante MENU non visibile**: aggiunto un controllo interno all'app con pulsante `☰ Chiudi menu` nella sidebar e pulsante fisso `☰ MENU` nella pagina principale quando il menu è nascosto. La visibilità non dipende più dai selettori interni del frontend Streamlit, che cambiavano nella versione installata; il vecchio controllo nativo della sidebar viene nascosto quando intercettabile via attributi `aria-label`/`title` (`app.py`).

### Gestione Conti Cliente
- **Chiusura conto: stato `chiuso_conto`**: alla chiusura del conto i libri non venduti (`disponibile`) diventano `chiuso_conto` (prima `ritirato`), cosi tutti i libri del cliente finiscono nello stesso stato terminale di conto chiuso (`gestione_conti.py`).
- **Correzione prezzo aggiorna anche il "Prezzo di Copertina"**: oltre a `prezzo_inserito_mano` su `copie_libri`, la correzione aggiorna `prezzo_copertina` su `catalogo_libri` (per ISBN), cosi la colonna "Prezzo di Copertina" risulta aggiornata (`gestione_conti.py`).
- **Correzione prezzo libro venduto: entrambe le ricevute**: se si corregge il prezzo di un libro `venduto`, vengono rigenerate e ripubblicate online SIA la ricevuta di ritiro SIA la ricevuta di vendita, entrambe con il prezzo aggiornato (`gestione_conti.py`, usa `genera_pdf_vendita_multipla` da `cassa.py`).
- **Ricevuta di ritiro include il libro corretto**: la rigenerazione della ricevuta di ritiro ora include il libro selezionato anche se non è in stato `disponibile` (es. `venduto`), tramite il parametro `includi_id_libro` (`gestione_conti.py`).
- **Selezione libro dalla tabella (niente più menu a cascata)**: in Gestione Conti si seleziona il libro cliccando la riga della tabella (interattiva, `on_select`/`single-row`) invece di usare il `selectbox`, per la correzione prezzo e per gli storni vendita/ritiro (`gestione_conti.py`).
- **Pulsante diretto "Riporta in disponibile"**: nella sezione "Correggi prezzo" di un libro `venduto` compare il pulsante per stornare la vendita (venduto → disponibile) direttamente, senza passare dal tab storno (`gestione_conti.py`).
- **Tabella separata: attivi vs conti chiusi**: i libri sono ora mostrati in due sezioni distinte — "Libri attivi (vendibili / venduti)" e "Libri di conti già chiusi (restituiti / liquidati)" — cosi non si confondono se il cliente porta altri libri dopo la chiusura (`gestione_conti.py`).
- **Colonna `operatore`**: la tabella mostra ora l'operatore che ha ritirato il libro (richiede `ALTER TABLE copie_libri ADD COLUMN operatore text;` da eseguire su Supabase) (`gestione_conti.py`).

### Ritiro Libri (Venditori)
- **Tracciamento operatore**: ogni libro ritirato registra l'operatore connesso (`st.session_state["operatore"]`) su `copie_libri.operatore`, con fallback sicuro se la colonna non esiste ancora (`ritiro.py`).
- **Stampa inventario per materia**: nella tab "Inventario Generale Magazzino" nuovo pulsante che genera un PDF dei soli libri `disponibile` (ancora in carico), raggruppati per `materia`, con conteggio per materia (`ritiro.py`, `genera_pdf_inventario_materia`).

### Resoconti / Reset
- **Cancella tutti i clienti (dati di prova)**: nuovo pulsante (con spunta di conferma) nella pagina "Resoconti Finanziari e Reset di Fine Anno" che elimina TUTTI i clienti e i dati collegati (`copie_libri`, `ricevute`, `clienti`), utile per rimuovere i dati di test. Gli account `operatori` non vengono toccati (`report .py`).

### Test automatici (pytest)
- **Suite test estesa a 51 test (tutti verdi)**: aggiunti 6 nuovi file di test in `tests/` per coprire le funzioni pure/isolabili dei moduli:
  - `test_ricevute_condivise.py` (10): `_sanifica_testo`, `build_receipt_storage_path`, `build_public_storage_url`.
  - `test_gestione_operatori.py` (16): `_hash_password`/`verifica_password` e `crea_operatore`/`elimina_operatore`/`cambia_ruolo`/`lista_operatori`/`autentica` con `requests` mockato.
  - `test_gestore_etichette_pdf.py` (5): `genera_preview_etichette` e `genera_griglia_a4_bytes` (verifica PDF bytes validi, incluso layout "a5").
  - `test_export_fine_anno.py` (3): `genera_resoconto_fine_anno` con `_get` mockato (struttura JSON, calcoli cassa, liquidazioni per cliente).
  - `test_cassa_pdf.py` (4): `genera_pdf_vendita_multipla` e `genera_pdf_chiusura_giornaliera` (verifica PDF bytes validi).
  - `test_logger_supabase.py` (6): `log_errore` (payload, troncamento campi, non-sollevazione) e `leggi_log_errori` con `requests` mockato.
- **Fix `prepara_dati_etichette`**: estrazione dell'id dall'etichetta ora cerca l'**ultima parte numerica** tra tutte le parti separate da `-`, gestendo sia il formato `<id_libro> - <codice>` che `<codice> - <id_libro>` (prima falliva con `IndexError` su etichette tipo `"27 - ABC"`).

## 2026-07-17 — v2.0.0

### Barcode, numerazione ricevute ed etichette
- **Fix lettura barcode (apostrofo)**: lo scanner leggeva `BOR85RW0001'31` (apostrofo al posto del trattino). Ora il parser normalizza qualsiasi separatore non alfanumerico in `-` (`cassa.py`), cosi `BOR85RW0001-31` → estrae correttamente l'id_libro `31`.
- **Barcode ritiro numerico e corto**: generazione etichetta/barcode nel formato `<id_venditore>-<id_libro>` (es. `123-31`) invece di `<codice_personale>-<id_libro>` (`ritiro.py`), per una scansione piu affidabile (niente lettere da leggere).
- **Numero ricevuta progressivo per tipo**: le ricevute ora riportano un numero progressivo dedicato — `N/V` per le vendite e `N/R` per i ritiri (es. `1/V`, `2/V`, `1/R`…) — calcolato su DB (`crea_tabella_ricevute.sql` arricchito con le colonne `tipo` e `numero_progressivo`).
- **Numero ricevuta in alto a destra, grande**: su entrambe le ricevute (vendita e ritiro) il numero appare in basso stile Title, allineato a destra; sotto, in piccolo grigio, **Data e Ora** della transazione.
- **Etichette A4**: `ID: <numero>` mostrato grande e in grassetto; la parte scannabile del codice (es. `-31`) in grassetto, il prefisso in normale (`gestore_etichette.py`).
- **Clausola ritiro**: didascalia QRCode aggiornata in `"Scansiona il QRCode per prenotare il reso libri/soldi:"` (`ricevute_condivise.py`).
- **Reset contatore ricevute a fine anno**: il pulsante "Reset Database" (`app.py`) ora svuota anche la tabella `ricevute` quando si azzerano copie/catalogo. Lo storico delle ricevute resta preservato nel resoconto JSON di fine anno e nei singoli PDF gia' caricati su Supabase Storage (bucket `ricevute`), cosi il numero riparte pulito da `1/V`, `1/R` ogni anno senza perdere nulla.

### Grafica (leggero restyling, senza stravolgere)
- **Sfondo "pieno di libri"**: sfondo con motivo a spine di libri tenui (verde, azzurro, sabbia, rosa, lilla) su base crema, con un velo bianco semi-trasparente per mantenere la leggibilita (`app.py`, CSS `.stApp`).
- **Bottoni colorati e identificabili**: i 3 pulsanti HOME ora hanno colori tenui distinti — VENDITA verde, RITIRO azzurro, ALTRO ambra; i pulsanti del menu laterale hanno sfondo crema con bordo marrone caldo e stato attivo evidenziato.

### Scorporo rimborso spese e Etichette antispreco
- **Scorporo 50 centesimi**: I 50 centesimi di rimborso spese non vengono più inclusi nel prezzo di vendita del singolo libro sulla ricevuta. Sono ora calcolati e mostrati chiaramente come riga separata `"RIMBORSO SPESE"` in fondo alla ricevuta PDF, completata dalla riga del `"TOTALE COMPLESSIVO RICEVUTO"` (in `cassa.py`).
- **Riepilogo in Cassa trasparente**: La schermata di cassa a monitor mostra adesso tre metriche chiare e distinte per trasparenza: `"TOTALE SOLO LIBRI"`, `"RIMBORSO SPESE GESTIONE"` e `"TOTALE COMPLESSIVO PAGATO"`.
- **Etichette A4 Antispreco**: Aggiunta la funzionalità di **stampa con offset (posizione di partenza)** in `gestore_etichette.py` e `ritiro.py`. Consente all'operatore di selezionare da quale etichetta far partire la stampa (es. inserendo 11 se le prime 10 sono già state usate e staccate), evitando di sprecare e dover gettare i fogli adesivi A4 parzialmente utilizzati.

### Log errori centralizzato (online)
- Sostituito il file locale `login_errors.log` (scritto sui PC degli utenti) con un **logger centralizzato su Supabase** (`logger_supabase.py` → tabella `log_errori`).
- Aggiunto `crea_tabella_log_errori.sql` per creare la tabella `log_errori` (con RLS anon access).
- I tentativi di login falliti vengono ora registrati online (tipo, messaggio, dettaglio, operatore, pagina).
- Aggiunta la voce **"📜 Log Errori"** nell'Area Admin: mostra la tabella degli errori (Data/Ora, Tipo, Messaggio, Dettaglio, Operatore, Pagina) letta da Supabase, visibile ovunque tu sia, non sui singoli PC.

## 2026-07-16 — v1.1.0

### Interfaccia e navigazione
- Sfondo bianco e stile grafico centralizzato (header operatore sempre visibile in alto).
- Menu laterale trasformato in **pulsanti grandi con icone** (niente più pallini/radio), con evidenziazione della voce attiva.
- Aggiunte **guide in linea** sintetiche per ogni pagina.

### Area Amministratore
- Caricamento dati admin con `@st.cache_data` (clienti, copie, catalogo in parallelo) per velocizzare i report.
- Report contabilità totale (contanti / bancomat / quota 1€ trattenuta).
- Importazione CSV del catalogo adozioni.

### Gestione Operatori
- Creazione/eliminazione operatori con **checkbox di selezione** (flegi) per l'eliminazione multipla.
- Ruolo admin gestito con **checkbox "admin"** (spuntato = admin, non spuntato = operatore) invece di testo/selectbox.
- La scritta "admin" è ora in piccolo (`st.caption`) per non essere invadente.

### Fine anno / Reset Database
- Pulsanti separati: **"🧾 Genera Ricevute Fine Anno"** (PDF cumulativo + resoconto JSON) e **"🚨 Reset Database"**.
- Il reset del database è **bloccato** finché non si scaricano sia il PDF delle ricevute che il resoconto JSON.
- Aggiunto **reimport dei dati dal file JSON** esportato (ripristino del database).

### Ritiro Libri (Venditori)
- Ricerche (ISBN, Titolo/Autore, Classe, Area macro) e lista clienti **cacheate** (`@st.cache_data`) → ricerche ripetute istantanee.

### Cassa e Vendita Rapida
- Caricamento copie, catalogo e clienti **cacheato**; dopo una vendita la cache viene invalidata (`st.cache_data.clear()`) per mostrare subito il magazzino aggiornato.

### Gestione Conti Cliente
- Tabella arricchita con **Titolo** e **Prezzi** (vendita e liquidazione) completi, non solo ISBN.
- Aggiunta **correzione del prezzo** di un libro (PATCH su `copie_libri`) tramite select + number_input.
- **Arrotondamento ai 10 centesimi**: Prezzo Vendita per eccesso (chi acquista), Liquidazione per difetto (chi vende/ritira).
- **Storno ritiro corretto**: ora elimina fisicamente la copia dal magazzino (prima la rimetteva "disponibile" per errore).

### Sicurezza / Deploy
- Password admin e master spostate da hardcoded a `.streamlit/secrets.toml` (`password_admin`, `password_master`), lette via `st.secrets`.
- Creato `.gitignore` che esclude `secrets.toml`, log e file temporanei dal repository.

## 2026-07-15 — v1.0.0 (Versione Iniziale)
- Struttura iniziale del gestionale con login operatori e tabella `operatori` su Supabase.
- Pagine: Registrazione Clienti, Ritiro Libri, Cassa, Gestione Conti, Cerca Libro, Archivio.
- Generazione ricevute PDF (A4 + etichette termiche TM-L90) e pubblicazione su Storage Supabase.
- Export resoconto fine anno (JSON) e generazione ricevute di liquidazione cumulative.
