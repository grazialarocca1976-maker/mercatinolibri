# Changelog — Mercatino Libri Usati (Marconi Verona)

<!-- ISTRUZIONE PER AGENTI AI (Cline, Codex, ecc.): ogni volta che modifichi/crei file di questo progetto, DEVI registrare la modifica in questo file, nella sezione del giorno corrente (formato ## AAAA-MM-GG). Se non esiste la sezione del giorno, creala. Mantieni lo stesso stile: elenchi puntati raggruppati per area. Leggi questo file prima di iniziare e aggiornalo alla fine. NON caricare mai .streamlit/secrets.toml nel repository. -->

Tutte le modifiche significative al progetto vengono documentate in questo file.

## 2026-07-19 (oggi)

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

## 2026-07-17 (oggi) — v2.0.0

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

## 2026-07-16 (ieri)

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

## 2026-07-15 (ieri)
- Struttura iniziale del gestionale con login operatori e tabella `operatori` su Supabase.
- Pagine: Registrazione Clienti, Ritiro Libri, Cassa, Gestione Conti, Cerca Libro, Archivio.
- Generazione ricevute PDF (A4 + etichette termiche TM-L90) e pubblicazione su Storage Supabase.
- Export resoconto fine anno (JSON) e generazione ricevute di liquidazione cumulative.
