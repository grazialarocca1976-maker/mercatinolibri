-- Tabella log errori centralizzata (visibile online, non sui PC degli utenti)
CREATE TABLE IF NOT EXISTS public.log_errori (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    creato_il timestamptz NOT NULL DEFAULT now(),
    tipo text NOT NULL DEFAULT 'generico',
    messaggio text NOT NULL,
    dettaglio text,
    operatore text,
    pagina text
);

ALTER TABLE public.log_errori ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anon full access log_errori" ON public.log_errori
    FOR ALL TO anon USING (true) WITH CHECK (true);