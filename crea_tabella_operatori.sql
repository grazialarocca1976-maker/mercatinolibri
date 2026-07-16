-- Esegui questo script nell'SQL Editor di Supabase
-- (https://supabase.com/dashboard -> progetto -> SQL -> New query)
-- per creare la tabella degli operatori usata dal gestionale.

CREATE TABLE IF NOT EXISTS public.operatori (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    salt text NOT NULL,
    ruolo text NOT NULL DEFAULT 'operatore',
    creato_il timestamptz NOT NULL DEFAULT now()
);

-- Abilita l'accesso anonimo (la stessa modalita' usata per le altre tabelle del gestionale)
ALTER TABLE public.operatori ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anon full access operatori" ON public.operatori;
CREATE POLICY "Anon full access operatori" ON public.operatori
    FOR ALL TO anon USING (true) WITH CHECK (true);