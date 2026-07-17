-- Tabella ricevute di vendita/ritiro: una riga per ogni scontrino emesso.
-- L'id e' un seriale automatico. La numerazione progressiva per TIPO
-- (R = ritiro, V = vendita) e' calcolata a runtime in base a numero_progressivo + tipo.
CREATE TABLE IF NOT EXISTS ricevute (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_ricevuta DATE DEFAULT CURRENT_DATE,
    tipo TEXT NOT NULL DEFAULT 'V',            -- 'R' = ritiro, 'V' = vendita
    numero_progressivo INT NOT NULL DEFAULT 0, -- progressivo per tipo (1/R, 2/R, 1/V, ...)
    id_acquirente BIGINT,
    metodo_pagamento TEXT,
    totale_libri NUMERIC(10,2) DEFAULT 0,
    rimborso_spese NUMERIC(10,2) DEFAULT 0,
    totale_complessivo NUMERIC(10,2) DEFAULT 0,
    numero_articoli INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Se la tabella esisteva gia' (vecchia versione senza tipo/numero_progressivo),
-- aggiungi le nuove colonne in modo idempotente.
ALTER TABLE ricevute ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'V';
ALTER TABLE ricevute ADD COLUMN IF NOT EXISTS numero_progressivo INT NOT NULL DEFAULT 0;

ALTER TABLE ricevute ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Anon full access ricevute" ON ricevute;
CREATE POLICY "Anon full access ricevute" ON ricevute FOR ALL TO anon USING (true) WITH CHECK (true);