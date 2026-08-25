-- =============================================================================
--  Finance Tracker — Módulo 1: Registro de usuarios
--
--  Uso:  createdb finance_tracker
--        psql -d finance_tracker -f db/01_users.sql
--
--  Solo la tabla users. Cada módulo agrega sus propias tablas.
-- =============================================================================

-- CITEXT = texto insensible a mayúsculas.
-- Con esto, 'Ana@correo.com' y 'ana@correo.com' son el MISMO email y el UNIQUE
-- los detecta como duplicados. Con un TEXT normal, se registrarían dos veces.
CREATE EXTENSION IF NOT EXISTS citext;


CREATE TABLE IF NOT EXISTS users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name     TEXT        NOT NULL,
    email         CITEXT      NOT NULL UNIQUE,
    -- Aquí va el HASH de la contraseña, nunca la contraseña.
    -- Un hash bcrypt mide 60 caracteres y se ve así:
    --   $2b$12$KIXQJ1s7f9pQvLd8n3mZ1eYt.../abcdefgHIJ
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_users_name_len     CHECK (char_length(full_name) BETWEEN 2 AND 120),
    CONSTRAINT ck_users_email_format CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    -- El hash siempre mide lo mismo. Si aquí entra algo de 8 caracteres,
    -- es que alguien guardó la contraseña en claro por error.
    CONSTRAINT ck_users_hash_len     CHECK (char_length(password_hash) >= 20)
);


-- Mantiene updated_at al día sin que el backend tenga que acordarse
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_users_updated ON users;
CREATE TRIGGER tg_users_updated
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- Estructura de la tabla users ---'
\d users

\echo ''
\echo '--- Usuarios registrados ---'
SELECT count(*) AS total FROM users;
