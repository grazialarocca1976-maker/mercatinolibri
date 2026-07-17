# Changelog — Mercatino Libri Usati (Marconi Verona)

<!-- ISTRUZIONE PER AGENTI AI (Cline, Codex, ecc.): ogni volta che modifichi/crei file di questo progetto, DEVI registrare la modifica in questo file, nella sezione del giorno corrente (formato ## AAAA-MM-GG). Se non esiste la sezione del giorno, creala. Mantieni lo stesso stile: elenchi puntati raggruppati per area. Leggi questo file prima di iniziare e aggiornalo alla fine. NON caricare mai .streamlit/secrets.toml nel repository. -->

Tutte le modifiche significative al progetto vengono documentate in questo file.

## 2026-07-17 (oggi) — v1.1.0

### Barcode, numerazione ricevute ed etichette
- **Fix lettura barcode (apostrofo)**: lo scanner leggeva `BOR85RW0001'31` (apostrofo al posto del trattino). Ora il parser normalizza qualsiasi separatore non alfanumerico in `-` (`cassa.py`), cosi `BOR85RW0001-31` → estrae correttamente l'id_libro `31`.
- **Barcode ritiro numerico e corto**: generazione etichetta/barcode nel formato `<id_venditore>-<id_libro>` (es. `123-31`) invece di `<codice_personale>-<id_libro>` (`ritiro.py`), per una scansione piu affidabile (niente lettere da leggere).
- **Numero ricevuta progressivo per tipo**: le ricevute ora riportano un numero progressivo dedicato — `N/V` per le vendite e `N/R` per i ritiri (es. `1/V`, `2/V`, `1/R`…) — calcolato su DB (`crea_tabella_ricevute.sql` arricchito con le colonne `tipo` e `numero_progressivo`).
- **Numero ricevuta in alto a destra, grande**: su entrambe le ricevute (vendita e ritiro) il numero appare in basso stile Title, allineato a destra; sotto, in piccolo grigio, **Data e Ora** della transazione.
- **Etichette A4**: `ID: <numero>` mostrato grande e in grassetto; la parte scannabile del codice (es. `-31`) in grassetto, il prefisso in normale (`gestore_etichette.py`).
- **Clausola ritiro**: didascalia QRCode aggiornata in `"Scansiona il QRCode per prenotare il reso libri/soldi:"` (`ricevute_condivise.py`).

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