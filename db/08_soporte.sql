-- =============================================================================
--  Finance Tracker — Módulo 8: soporte
--
--  Uso:  psql -d finance_tracker -f db/08_soporte.sql
--
--  Conversaciones entre quien usa Bolsillo y quien lo administra. Van de ida y
--  vuelta: el usuario abre un hilo, el administrador responde dentro del mismo
--  hilo, y la conversación queda entera en un sitio.
--
--  Dos tablas y no una: un hilo tiene estado propio —abierto, respondido,
--  cerrado— que no pertenece a ningún mensaje concreto, y meterlo en cada
--  mensaje obligaría a mirar el último para saber cómo está la conversación.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'support_status') THEN
        CREATE TYPE support_status AS ENUM ('abierto', 'respondido', 'cerrado');
    END IF;
END
$$;


CREATE TABLE IF NOT EXISTS support_threads (
    id          UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    -- NULL cuando escribe alguien desde el formulario de la landing sin tener
    -- cuenta. En ese caso el nombre y el correo se guardan aquí, que es lo
    -- único que sabemos de esa persona.
    user_id     UUID           REFERENCES users(id) ON DELETE CASCADE,
    guest_name  TEXT,
    guest_email CITEXT,
    subject     TEXT           NOT NULL,
    status      support_status NOT NULL DEFAULT 'abierto',
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT ck_support_asunto CHECK (char_length(subject) BETWEEN 3 AND 160),
    -- O es de un usuario, o trae nombre y correo de quien escribió. Un hilo sin
    -- ninguna de las dos cosas no se podría responder.
    CONSTRAINT ck_support_quien CHECK (
        user_id IS NOT NULL
        OR (guest_name IS NOT NULL AND guest_email IS NOT NULL)
    ),
    CONSTRAINT ck_support_correo CHECK (
        guest_email IS NULL OR guest_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'
    )
);


CREATE TABLE IF NOT EXISTS support_messages (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id  UUID        NOT NULL REFERENCES support_threads(id) ON DELETE CASCADE,
    -- Quién lo escribió. NULL si fue un invitado sin cuenta.
    author_id  UUID        REFERENCES users(id) ON DELETE SET NULL,
    -- Si lo escribió el equipo. Se guarda aquí y no se deduce del rol del autor
    -- porque el rol puede cambiar después, y entonces los mensajes viejos
    -- cambiarían de lado en la conversación.
    from_admin BOOLEAN     NOT NULL DEFAULT false,
    body       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_support_cuerpo CHECK (char_length(body) BETWEEN 1 AND 4000)
);


-- Los hilos se listan por actividad reciente, y los mensajes por orden de
-- llegada dentro de su hilo. Índices parciales no hacen falta: aquí no hay
-- borrado lógico.
CREATE INDEX IF NOT EXISTS ix_support_threads_fecha  ON support_threads (updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_support_threads_user   ON support_threads (user_id);
CREATE INDEX IF NOT EXISTS ix_support_threads_estado ON support_threads (status);
CREATE INDEX IF NOT EXISTS ix_support_messages_hilo  ON support_messages (thread_id, created_at);

DROP TRIGGER IF EXISTS tg_support_threads_updated ON support_threads;
CREATE TRIGGER tg_support_threads_updated
    BEFORE UPDATE ON support_threads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- Conversaciones de soporte ---'
SELECT count(*) AS hilos FROM support_threads;
SELECT count(*) AS mensajes FROM support_messages;
