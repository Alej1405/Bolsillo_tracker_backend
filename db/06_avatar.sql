-- =============================================================================
--  Finance Tracker — Módulo 6: foto de perfil
--
--  Uso:  psql -d finance_tracker -f db/06_avatar.sql
--
--  Una sola columna sobre la tabla users. Guarda la RUTA pública del archivo
--  ("/media/avatares/xxx.jpg"), nunca la imagen: una foto dentro de la base
--  la hace pesada, lenta de respaldar y obliga a leerla en cada consulta de
--  usuario aunque nadie la esté mirando. El archivo vive en disco y aquí
--  queda solo la dirección donde encontrarlo.
--
--  Es NULL mientras la persona no suba nada: no hay foto por defecto, y una
--  cadena vacía obligaría al frontend a distinguir "" de NULL para lo mismo.
-- =============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- El nombre del archivo lo genera el backend y siempre empieza igual. El CHECK
-- corta el caso de que alguien escriba a mano una URL a otro servidor y el
-- frontend termine cargando una imagen de un sitio que no controlamos.
ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_avatar_ruta;
ALTER TABLE users ADD CONSTRAINT ck_users_avatar_ruta
    CHECK (avatar_url IS NULL OR avatar_url ~ '^/media/avatares/[A-Za-z0-9._-]+$');


-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- Estructura de la tabla users ---'
\d users

\echo ''
\echo '--- Usuarios con foto ---'
SELECT count(*) FILTER (WHERE avatar_url IS NOT NULL) AS con_foto,
       count(*)                                       AS total
FROM users;
