-- =============================================================================
--  Finance Tracker — Modulo 4: transacciones (ingresos, egresos, transferencias)
--
--  Uso:  psql -d finance_tracker -f db/05_transactions.sql
--
--  La tabla central. Un usuario registra MUCHAS transacciones: la relacion es
--  1:N por user_id, y cada una apunta ademas a la cuenta afectada.
--
--  Tres reglas que hacen cumplir los CHECK:
--    · amount SIEMPRE positivo — el signo lo da el type, no el numero
--    · income/expense: llevan categoria y NO llevan contracuenta
--    · transfer:       lleva contracuenta, NO lleva categoria, y las dos
--                      cuentas deben ser distintas
--
--  Incluye la vista account_balances: el saldo se CALCULA, no se guarda.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transaction_type') THEN
        CREATE TYPE transaction_type AS ENUM ('income', 'expense', 'transfer');
    END IF;
END
$$;


--  transactions — la tabla central
--
--  Los tres tipos conviven aquí. Los CHECK garantizan que cada tipo tenga
--  exactamente las columnas que le corresponden y ninguna otra.
-- -----------------------------------------------------------------------------
CREATE TABLE transactions (
    id                 UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID             NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type               transaction_type NOT NULL,
    -- SIEMPRE positivo. El signo lo determina el type, no el número.
    amount             NUMERIC(14,2)    NOT NULL,
    currency           CHAR(3)          NOT NULL DEFAULT 'USD',
    -- Cuenta afectada. En una transferencia, la de ORIGEN.
    account_id         UUID             NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    -- Solo en transferencias: la cuenta de DESTINO.
    counter_account_id UUID             REFERENCES accounts(id) ON DELETE RESTRICT,
    category_id        UUID             REFERENCES categories(id) ON DELETE RESTRICT,
    occurred_at        DATE             NOT NULL,   -- cuándo pasó (la usan los reportes)
    note               TEXT,
    created_at         TIMESTAMPTZ      NOT NULL DEFAULT now(),  -- cuándo se registró
    updated_at         TIMESTAMPTZ      NOT NULL DEFAULT now(),
    deleted_at         TIMESTAMPTZ,                -- borrado lógico

    CONSTRAINT ck_tx_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_tx_note_len        CHECK (note IS NULL OR char_length(note) <= 500),

    -- Una transferencia tiene destino, no tiene categoría, y las dos cuentas
    -- deben ser distintas (mover dinero a la misma cuenta no es nada).
    CONSTRAINT ck_tx_transfer_shape CHECK (
        type <> 'transfer' OR (
            counter_account_id IS NOT NULL
            AND category_id IS NULL
            AND account_id <> counter_account_id
        )
    ),

    -- Un ingreso o egreso siempre lleva categoría y nunca lleva contracuenta.
    CONSTRAINT ck_tx_flow_shape CHECK (
        type = 'transfer' OR (
            counter_account_id IS NULL
            AND category_id IS NOT NULL
        )
    )
);

-- Índices parciales: no indexan lo borrado, que es justo lo que nunca se consulta.
CREATE INDEX ix_tx_user_date ON transactions (user_id, occurred_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ix_tx_account   ON transactions (account_id)                WHERE deleted_at IS NULL;
CREATE INDEX ix_tx_counter   ON transactions (counter_account_id)        WHERE deleted_at IS NULL;
CREATE INDEX ix_tx_category  ON transactions (category_id)               WHERE deleted_at IS NULL;

CREATE TRIGGER tg_tx_updated
    BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- -----------------------------------------------------------------------------
--  Trigger: coherencia entre el tipo de transacción y el kind de la categoría
--  Impide pagar la luz con la categoría "Sueldo".
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION check_transaction_category() RETURNS TRIGGER AS $$
DECLARE
    cat_kind category_kind;
BEGIN
    IF NEW.category_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT kind INTO cat_kind FROM categories WHERE id = NEW.category_id;

    IF cat_kind::text <> NEW.type::text THEN
        RAISE EXCEPTION 'La categoría es de tipo % pero la transacción es de tipo %',
                        cat_kind, NEW.type
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_tx_category_kind
    BEFORE INSERT OR UPDATE OF category_id, type ON transactions
    FOR EACH ROW EXECUTE FUNCTION check_transaction_category();


-- -----------------------------------------------------------------------------
--  Vista: saldo actual de cada cuenta
--
--  El saldo NO se guarda como columna: se calcula. Una columna que se actualiza
--  a mano se desincroniza y entonces hay dos verdades que no coinciden.
--
--  Nótese la transferencia: RESTA cuando la cuenta es el origen y SUMA cuando
--  es el destino. Por eso una transferencia no altera el patrimonio total.
-- -----------------------------------------------------------------------------
CREATE VIEW account_balances AS
SELECT
    a.id                AS account_id,
    a.user_id,
    a.name,
    a.type,
    a.currency,
    a.initial_balance,
    a.initial_balance
      + COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'income'   AND t.account_id         = a.id), 0)
      - COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'expense'  AND t.account_id         = a.id), 0)
      - COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'transfer' AND t.account_id         = a.id), 0)
      + COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'transfer' AND t.counter_account_id = a.id), 0)
                        AS balance
FROM accounts a
LEFT JOIN transactions t
       ON (t.account_id = a.id OR t.counter_account_id = a.id)
      AND t.deleted_at IS NULL
GROUP BY a.id, a.user_id, a.name, a.type, a.currency, a.initial_balance;



-- =============================================================================
--  Verificacion
-- =============================================================================
\echo ''
\echo '--- Estructura de transactions ---'
\d transactions
\echo ''
\echo '--- Vista de saldos ---'
\d account_balances
