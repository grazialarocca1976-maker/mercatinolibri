# Changelog — Mercatino Libri Usati (Marconi Verona)

<!-- ISTRUZIONE PER AGENTI AI (Cline, Codex, ecc.): ogni volta che modifichi/crei file di questo progetto, DEVI registrare la modifica in questo file, nella sezione del giorno corrente (formato ## AAAA-MM-GG). Se non esiste la sezione del giorno, creala. Mantieni lo stesso stile: elenchi puntati raggruppati per area. Leggi questo file prima di iniziare e aggiornalo alla fine. NON caricare mai .streamlit/secrets.toml nel repository. -->

Tutte le modifiche significative al progetto vengono documentate in questo file.

## 2026-07-17 (oggi)

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