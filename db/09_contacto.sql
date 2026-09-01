-- =============================================================================
--  Finance Tracker — Módulo 9: los datos de contacto de la landing
--
--  Uso:  psql -d finance_tracker -f db/09_contacto.sql
--
--  El teléfono, el correo y la dirección que aparecen en la web. Estaban
--  escritos en el código del frontend, así que cambiar un número exigía tocar
--  el repositorio y volver a desplegar. Ahora los edita el super_admin desde
--  su panel y la landing los lee.
--
--  Una sola fila, con `id` fijo en 1: no hay varias sedes ni varios sitios. El
--  CHECK impide que alguien inserte una segunda por descuido y deje al backend
--  eligiendo cuál de las dos mostrar.
-- =============================================================================

CREATE TABLE IF NOT EXISTS site_contact (
    id         SMALLINT    PRIMARY KEY DEFAULT 1,
    phone      TEXT,
    email      CITEXT,
    address    TEXT,
    schedule   TEXT,
    whatsapp   TEXT,
    instagram  TEXT,
    tiktok     TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_contacto_fila_unica CHECK (id = 1),
    CONSTRAINT ck_contacto_correo CHECK (
        email IS NULL OR email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'
    )
);

-- La fila nace con los valores que hoy están escritos en la landing, para que
-- la web siga diciendo lo mismo el día que se conecte.
INSERT INTO site_contact (id, phone, email, address, schedule)
VALUES (1, '+593 99 000 0000', 'hola@mashaec.net', 'Quito, Ecuador', 'Lunes a viernes, 9:00 a 18:00')
ON CONFLICT (id) DO NOTHING;

DROP TRIGGER IF EXISTS tg_site_contact_updated ON site_contact;
CREATE TRIGGER tg_site_contact_updated
    BEFORE UPDATE ON site_contact
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- Datos de contacto ---'
SELECT phone, email, address FROM site_contact;
