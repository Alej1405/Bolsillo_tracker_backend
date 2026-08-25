-- =============================================================================
--  Finance Tracker — Modulo 2: cuentas
--
--  Uso:  psql -d finance_tracker -f db/03_accounts.sql
--
--  Donde esta el dinero. El fondo de ahorro NO es una tabla aparte: es una
--  cuenta de tipo 'savings'. Por eso ahorrar sera una transferencia entre
--  cuentas y no un egreso.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'account_type') THEN
        CREATE TYPE account_type AS ENUM ('cash', 'bank', 'card', 'savings');
    END IF;
END
$$;


--  accounts — dónde está el dinero
--  El fondo de ahorro es simplemente type = 'savings'
-- -----------------------------------------------------------------------------
CREATE TABLE accounts (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT          NOT NULL,
    type            account_type  NOT NULL,
    currency        CHAR(3)       NOT NULL DEFAULT 'USD',
    -- Cuánto había en la cuenta al momento de crearla en la app.
    -- Puede ser negativo: una tarjeta de crédito con deuda.
    initial_balance NUMERIC(14,2) NOT NULL DEFAULT 0,
    icon            TEXT,
    color           TEXT,
    archived_at     TIMESTAMPTZ,            -- oculta la cuenta sin perder historial
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT uq_accounts_user_name UNIQUE (user_id, name),
    CONSTRAINT ck_accounts_name_len  CHECK (char_length(name) BETWEEN 1 AND 60),
    CONSTRAINT ck_accounts_currency  CHECK (currency = 'USD')  -- ampliar a futuro
);

CREATE INDEX ix_accounts_user ON accounts (user_id) WHERE archived_at IS NULL;

CREATE TRIGGER tg_accounts_updated
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
--  Verificacion
-- =============================================================================
\echo ''
\echo '--- Estructura de accounts ---'
\d accounts
\echo ''
\echo '--- Tipos de cuenta posibles ---'
SELECT enum_range(NULL::account_type) AS tipos;
