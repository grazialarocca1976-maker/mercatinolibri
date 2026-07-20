-- Esegui questo script SQL nell'SQL Editor di Supabase per aggiungere il supporto ai fascicoli.

ALTER TABLE public.copie_libri 
ADD COLUMN IF NOT EXISTS prevede_fascicoli boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS totale_fascicoli integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS fascicoli_consegnati integer DEFAULT 0;

COMMENT ON COLUMN public.copie_libri.prevede_fascicoli IS 'Indica se la copia del libro prevede dei fascicoli allegati.';
COMMENT ON COLUMN public.copie_libri.totale_fascicoli IS 'Il numero totale di fascicoli previsti per questo testo.';
COMMENT ON COLUMN public.copie_libri.fascicoli_consegnati IS 'Il numero di fascicoli effettivamente consegnati dal venditore.';
