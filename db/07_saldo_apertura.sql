-- =============================================================================
--  Finance Tracker — Módulo 7: el saldo de apertura es un ingreso
--
--  Uso:  psql -d finance_tracker -f db/07_saldo_apertura.sql
--
--  Antes, abrir un bolsillo con saldo guardaba ese número en accounts
--  (initial_balance) y no creaba ningún movimiento. El saldo del bolsillo salía
--  bien, pero los reportes mostraban "entró 0": los ingresos se leen de
--  transactions, y ahí no había nada.
--
--  A partir de aquí, el saldo con el que se abre un bolsillo ES un ingreso y
--  vive en transactions como cualquier otro. Eso implica dos cambios:
--
--    1. La vista account_balances DEJA de sumar initial_balance. Si lo sumara,
--       el dinero se contaría dos veces: una en la columna y otra en el
--       movimiento. La columna se conserva como dato informativo —con cuánto
--       abrió el bolsillo— pero ya no interviene en el saldo.
--    2. Los bolsillos que ya existen reciben su movimiento de apertura, para
--       que su saldo siga siendo el mismo bajo la vista nueva.
--
--  Los dos van en la misma transacción: entre el cambio de vista y la creación
--  de los movimientos, los saldos estarían mal, y nadie debe poder leerlos así.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
--  1. La categoría del sistema en la que caen estos ingresos
--
--  Propia y no "Otros ingresos": en el reporte por categorías, abrir un bolsillo
--  no es lo mismo que recibir dinero, y mezclarlos deformaría el reparto.
--  user_id NULL = del sistema, la ven todos y nadie la edita.
-- -----------------------------------------------------------------------------
INSERT INTO categories (user_id, parent_id, name, kind, icon, color)
SELECT NULL, NULL, 'Saldo inicial', 'income', '🏦', '#0EA5E9'
WHERE NOT EXISTS (
    SELECT 1 FROM categories
    WHERE user_id IS NULL AND parent_id IS NULL
      AND lower(name) = 'saldo inicial' AND kind = 'income'
);

-- -----------------------------------------------------------------------------
--  2. Los saldos de apertura negativos, a cero
--
--  Un bolsillo no se abre debiendo. Un saldo en contra aparece después, cuando
--  se gasta de un bolsillo que estaba en cero, y eso ya son movimientos.
--
--  La API los aceptaba por no tener mínimo, y quedó alguno registrado. Se
--  ponen a cero antes de crear los movimientos —un ingreso negativo no existe—
--  y el CHECK del final impide que vuelva a entrar ninguno.
-- -----------------------------------------------------------------------------
UPDATE accounts SET initial_balance = 0 WHERE initial_balance < 0;


-- -----------------------------------------------------------------------------
--  3. El movimiento de apertura de los bolsillos que ya existían
--
--  La fecha es la de creación del bolsillo, no la de hoy: el dinero estaba ahí
--  desde que se abrió, y fecharlo hoy movería el resultado del mes en curso.
--
--  El NOT EXISTS hace el script repetible: correrlo dos veces no duplica nada.
-- -----------------------------------------------------------------------------
INSERT INTO transactions (user_id, type, amount, account_id, category_id, occurred_at, note)
SELECT
    a.user_id,
    'income',
    a.initial_balance,
    a.id,
    (SELECT id FROM categories
      WHERE user_id IS NULL AND lower(name) = 'saldo inicial' AND kind = 'income'
      LIMIT 1),
    a.created_at::date,
    'Saldo con el que abriste este bolsillo'
FROM accounts a
WHERE a.initial_balance > 0
  AND NOT EXISTS (
      SELECT 1 FROM transactions t
      WHERE t.account_id = a.id
        AND t.note = 'Saldo con el que abriste este bolsillo'
        AND t.deleted_at IS NULL
  );


-- -----------------------------------------------------------------------------
--  4. La vista, sin initial_balance
--
--  Idéntica a la anterior salvo el primer sumando, que desaparece. El saldo pasa
--  a salir solo de los movimientos.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW account_balances AS
SELECT
    a.id                AS account_id,
    a.user_id,
    a.name,
    a.type,
    a.currency,
    a.initial_balance,
    COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'income'   AND t.account_id         = a.id), 0)
      - COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'expense'  AND t.account_id         = a.id), 0)
      - COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'transfer' AND t.account_id         = a.id), 0)
      + COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'transfer' AND t.counter_account_id = a.id), 0)
      AS balance
FROM accounts a
LEFT JOIN transactions t
       ON (t.account_id = a.id OR t.counter_account_id = a.id)
      AND t.deleted_at IS NULL
GROUP BY a.id;


-- -----------------------------------------------------------------------------
--  5. Que no vuelva a entrar un saldo de apertura en contra
-- -----------------------------------------------------------------------------
ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_accounts_saldo_apertura;
ALTER TABLE accounts ADD CONSTRAINT ck_accounts_saldo_apertura
    CHECK (initial_balance >= 0);

COMMIT;


-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- Bolsillos: con cuánto abrieron y cuánto tienen ahora ---'
SELECT a.name,
       a.initial_balance AS abrio_con,
       b.balance         AS tiene_ahora,
       count(t.id) FILTER (WHERE t.note = 'Saldo con el que abriste este bolsillo') AS mov_apertura
FROM accounts a
JOIN account_balances b ON b.account_id = a.id
LEFT JOIN transactions t ON t.account_id = a.id AND t.deleted_at IS NULL
GROUP BY a.name, a.initial_balance, b.balance
ORDER BY a.name;
