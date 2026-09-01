-- =============================================================================
--  Finance Tracker — Módulo 10: los videos de TikTok en la landing
--
--  Uso:  psql -d finance_tracker -f db/10_tiktok.sql
--
--  La sección de TikToks de la web muestra videos reales de la cuenta, no
--  marcadores. Para eso hace falta la Display API de TikTok, que trabaja con
--  OAuth: la persona autoriza una vez y el servidor guarda dos llaves —una para
--  pedir datos y otra para renovar la primera cuando caduca—.
--
--  Dos tablas:
--    · tiktok_config: las credenciales de la aplicación y las llaves de sesión.
--      Una sola fila, como los datos de contacto.
--    · tiktok_videos: lo último que devolvió TikTok, guardado. Se guarda en vez
--      de preguntar en cada visita porque la landing la ve cualquiera y la API
--      tiene límites de uso: mil visitas serían mil llamadas por el mismo dato.
-- =============================================================================

CREATE TABLE IF NOT EXISTS tiktok_config (
    id            SMALLINT    PRIMARY KEY DEFAULT 1,
    -- Las que da TikTok al registrar la aplicación. El secreto no sale nunca
    -- por la API: los endpoints devuelven si está puesto, no su valor.
    client_key    TEXT,
    client_secret TEXT,
    -- Lo que devuelve el OAuth. `expires_at` dice cuándo hay que renovar con
    -- el refresh_token, que dura mucho más.
    access_token  TEXT,
    refresh_token TEXT,
    expires_at    TIMESTAMPTZ,
    open_id       TEXT,
    -- Quién autorizó y cuándo se trajeron los videos por última vez.
    display_name  TEXT,
    synced_at     TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_tiktok_fila_unica CHECK (id = 1)
);

INSERT INTO tiktok_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;


CREATE TABLE IF NOT EXISTS tiktok_videos (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- El identificador que usa TikTok. UNIQUE para que volver a sincronizar
    -- actualice el video en vez de duplicarlo.
    video_id     TEXT        NOT NULL UNIQUE,
    title        TEXT,
    cover_url    TEXT,
    share_url    TEXT,
    embed_link   TEXT,
    duration     INTEGER,
    -- Cuándo se publicó en TikTok, para ordenarlos como los ve la gente allá.
    published_at TIMESTAMPTZ,
    -- Si se muestra en la landing. Permite esconder uno sin borrarlo ni tener
    -- que volver a sincronizar.
    visible      BOOLEAN     NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_tiktok_videos_fecha
    ON tiktok_videos (published_at DESC) WHERE visible;

DROP TRIGGER IF EXISTS tg_tiktok_config_updated ON tiktok_config;
CREATE TRIGGER tg_tiktok_config_updated
    BEFORE UPDATE ON tiktok_config
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- TikTok ---'
SELECT (client_key IS NOT NULL) AS tiene_clave,
       (access_token IS NOT NULL) AS autorizado,
       synced_at
FROM tiktok_config;
SELECT count(*) AS videos FROM tiktok_videos;
