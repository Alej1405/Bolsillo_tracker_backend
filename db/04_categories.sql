-- =============================================================================
--  Finance Tracker — Modulo 3: categorias
--
--  Uso:  psql -d finance_tracker -f db/04_categories.sql
--
--  En que se gasta / de donde viene el dinero.
--
--  · user_id NULL  = categoria del sistema, visible para todos
--  · parent_id     = subcategoria. Solo DOS niveles (lo fuerza un trigger)
--  · kind          = 'income' o 'expense'. Una categoria de ingreso no puede
--                    usarse en un egreso (lo comprueba otro trigger, en
--                    transactions)
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'category_kind') THEN
        CREATE TYPE category_kind AS ENUM ('income', 'expense');
    END IF;
END
$$;


--  categories — en qué se gasta / de dónde viene
--  user_id NULL  =>  categoría del sistema, compartida por todos los usuarios
--  parent_id NULL =>  categoría padre
-- -----------------------------------------------------------------------------
CREATE TABLE categories (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID          REFERENCES users(id) ON DELETE CASCADE,
    parent_id   UUID          REFERENCES categories(id) ON DELETE RESTRICT,
    name        TEXT          NOT NULL,
    kind        category_kind NOT NULL,
    icon        TEXT,
    color       TEXT,
    archived_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT ck_categories_name_len  CHECK (char_length(name) BETWEEN 1 AND 60),
    CONSTRAINT ck_categories_color_hex CHECK (color IS NULL OR color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT ck_categories_not_self  CHECK (parent_id IS DISTINCT FROM id)
);

-- Índices UNIQUE: no puede haber dos categorías con el mismo nombre bajo el
-- mismo padre.
--
-- Se necesitan DOS índices y el COALESCE por una razón sutil: en SQL,
-- NULL <> NULL. Un UNIQUE normal sobre columnas que admiten NULL deja pasar
-- duplicados — dos categorías del sistema (user_id NULL) llamadas "Salud", o
-- dos categorías padre (parent_id NULL) con el mismo nombre. El COALESCE
-- convierte el NULL en un UUID fijo para que el índice sí los compare.
CREATE UNIQUE INDEX uq_categories_child
    ON categories (COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
                   parent_id, lower(name))
    WHERE parent_id IS NOT NULL;

CREATE UNIQUE INDEX uq_categories_root
    ON categories (COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
                   lower(name), kind)
    WHERE parent_id IS NULL;

CREATE INDEX ix_categories_user ON categories (user_id) WHERE archived_at IS NULL;

CREATE TRIGGER tg_categories_updated
    BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- -----------------------------------------------------------------------------
--  Trigger: jerarquía de máximo dos niveles + herencia del kind
--
--  Un CHECK no puede consultar otras filas, así que estas dos reglas se
--  imponen con un trigger:
--    1. El padre de una categoría no puede tener padre a su vez.
--    2. Una subcategoría hereda obligatoriamente el kind del padre
--       (no tendría sentido "Luz (ingreso)" colgando de "Servicios básicos (egreso)").
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION check_category_hierarchy() RETURNS TRIGGER AS $$
DECLARE
    parent_parent_id UUID;
    parent_kind      category_kind;
    parent_user_id   UUID;
BEGIN
    IF NEW.parent_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT parent_id, kind, user_id
      INTO parent_parent_id, parent_kind, parent_user_id
      FROM categories WHERE id = NEW.parent_id;

    IF parent_parent_id IS NOT NULL THEN
        RAISE EXCEPTION 'Solo se permiten dos niveles de categorías'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.kind <> parent_kind THEN
        RAISE EXCEPTION 'La subcategoría debe ser del mismo kind que su padre (%)', parent_kind
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.user_id IS DISTINCT FROM parent_user_id THEN
        RAISE EXCEPTION 'La subcategoría debe pertenecer al mismo dueño que su padre'
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tg_categories_hierarchy
    BEFORE INSERT OR UPDATE OF parent_id, kind, user_id ON categories
    FOR EACH ROW EXECUTE FUNCTION check_category_hierarchy();



-- =============================================================================
--  Verificacion
-- =============================================================================
\echo ''
\echo '--- Estructura de categories ---'
\d categories
