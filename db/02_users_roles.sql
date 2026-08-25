-- =============================================================================
--  Finance Tracker — Módulo 1 (ampliación): roles y baja lógica de usuarios
--
--  Uso:  psql -d finance_tracker -f db/02_users_roles.sql
--
--  Se corre UNA vez sobre una base que ya tiene la tabla users (01_users.sql).
--  No recrea nada: solo agrega lo que falta.
-- =============================================================================

-- -----------------------------------------------------------------------------
--  user_role — los roles son FIJOS: solo estos dos existen y no se crean desde
--  la aplicación. Por eso un ENUM y no una tabla `roles` con clave foránea:
--  Postgres impide guardar un valor inválido y no hace falta ningún JOIN.
--  Mismo criterio que `transaction_type` y `account_type`.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('super_admin', 'client');
    END IF;
END
$$;


-- -----------------------------------------------------------------------------
--  users.role — quien se registra es siempre 'client'.
--  El 'super_admin' se promueve a mano desde psql; nunca por la API, o
--  cualquiera podría convertirse en administrador al registrarse.
-- -----------------------------------------------------------------------------
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role user_role NOT NULL DEFAULT 'client';


-- -----------------------------------------------------------------------------
--  users.is_active — baja LÓGICA.
--  Un DELETE real arrastraría cuentas y transacciones: el historial financiero
--  desaparecería. Dar de baja = poner is_active = false. El usuario no puede
--  iniciar sesión, pero sus datos quedan intactos.
-- -----------------------------------------------------------------------------
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;


-- -----------------------------------------------------------------------------
--  Índice parcial: los listados del panel de administración piden usuarios
--  activos. Al indexar solo esas filas, el índice es más chico que uno normal.
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_users_active
    ON users (created_at DESC)
    WHERE is_active;


-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- Estructura de la tabla users ---'
\d users

\echo ''
\echo '--- Valores posibles de user_role ---'
SELECT enum_range(NULL::user_role) AS roles;

\echo ''
\echo '--- Usuarios por rol ---'
SELECT role, count(*) AS total, count(*) FILTER (WHERE is_active) AS activos
FROM users
GROUP BY role;
