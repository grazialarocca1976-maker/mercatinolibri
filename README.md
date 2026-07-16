# 📚 Mercatino Libri Usati — Marconi Verona

Gestionale Streamlit per il mercatino dei libri usati scolastici: registrazione clienti, ritiro (conto vendita), cassa, gestione conti, archivio ricevute e chiusura fine anno.

## Funzionalità
- **👤 Registrazione Clienti**: anagrafica venditori/acquirenti con codice personale automatico.
- **📥 Ritiro Libri**: ricerca per ISBN / Titolo-Autore / Classe, stampa ricevuta A4 + etichette (foglio A4 o stampante termica TM-L90).
- **🛒 Cassa e Vendita Rapida**: individuazione libro (numero copertina, codice venditore o barcode), carrello, pagamento contanti/bancomat, ricevuta PDF.
- **📒 Gestione Conti Cliente**: elenco libri consegnati/venduti, prezzi, correzione prezzo, storno vendita/ritiro, chiusura conto.
- **🔍 Cerca Libro**: filtro per ISBN, titolo, numero copia o codice cliente.
- **📁 Archivio**: ricevute online, clienti, libri in possesso, libri venduti.
- **🔧 Area Admin**: contabilità, import CSV catalogo, gestione operatori, generazione ricevute fine anno, reset database (protetto).

## Avvio in locale
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configurazione (segreti)
I dati sensibili stanno in `.streamlit/secrets.toml` (escluso dal repo tramite `.gitignore`):
```toml
[connections.supabase_connection]
url = "https://supabase.co"
key = "<CHIAVE_SUPABASE>"

password_admin = "Marconi2026"
password_master = "Marconi2026"
```
L'app legge `st.secrets.get("password_admin")` e `st.secrets.get("password_master")`, con fallback ai valori di default se il file manca.

> ⚠️ **Non caricare `secrets.toml` su repository pubblici.** Su Streamlit Community Cloud incollane il contenuto nella sezione **Settings → Secrets**.

## Database (Supabase)
Tabelle usate: `clienti`, `catalogo_libri`, `copie_libri`, `operatori`.
Per creare la tabella operatori eseguire `crea_tabella_operatori.sql` nell'SQL Editor di Supabase.

## Struttura file
| File | Descrizione |
|------|-------------|
| `app.py` | Entry point, login, navigazione, area admin |
| `clienti.py` | Registrazione e modifica clienti |
| `ritiro.py` | Presa in carico libri + ricevute/etichette |
| `cassa.py` | Vendita e report di cassa |
| `gestione_conti.py` | Conti cliente, storni, correzione prezzi |
| `cerca_libro.py` | Ricerca copie |
| `gestione_operatori.py` | Auth operatori (hash + salt) |
| `gestore_etichette.py` | Generazione etichette A4 / TM-L90 |
| `ricevute_condivise.py` | Layout PDF condivisi + upload Storage |
| `export_fine_anno.py` | Resoconto JSON fine anno |
| `catalogo.py` | Import CSV catalogo adozioni |
| `crea_tabella_operatori.sql` | DDL tabella operatori |

## Note di sicurezza
- Le password operatori sono salvate come **SHA-256 + salt** su Supabase.
- La `CHIAVE_SUPABASE` è attualmente presente nei sorgenti: per massima sicurezza su repo pubblici, spostarla in `secrets.toml` e leggerla via `st.secrets`.