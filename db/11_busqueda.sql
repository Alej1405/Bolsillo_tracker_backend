-- =============================================================================
--  11 · Búsqueda: trigramas y texto completo en español
-- =============================================================================
--
--  Hasta aquí la API buscaba con `ILIKE '%texto%'`. Eso funciona, pero tiene
--  dos problemas que se notan en cuanto la base crece:
--
--    1. Un patrón que empieza por comodín NO puede usar un índice B-tree. La
--       consulta recorre la tabla entera: O(n).
--    2. No perdona nada. "maria" no encuentra "María", y "alimentacion" no
--       encuentra "Alimentación".
--
--  Esto lo resuelve con dos estructuras de datos de PostgreSQL, sin IA y sin
--  servicios externos:
--
--    · pg_trgm  — parte cada texto en trigramas (grupos de 3 letras) y los
--                 indexa en un GIN. "María" produce "  m", " ma", "mar",
--                 "ari", "ría", "ía ". Buscar "maria" comparte casi todos, así
--                 que la encuentra aunque falte la tilde o sobre una letra.
--                 Devuelve además una SIMILITUD de 0 a 1, que sirve para
--                 ordenar por relevancia.
--
--    · to_tsvector('spanish') — analiza la frase: separa palabras, quita las
--                 vacías (de, la, para) y reduce cada una a su raíz. "compras"
--                 y "comprando" caen en la misma. También va a un índice GIN.
--
--  Un índice GIN (Generalized Inverted Index) es un índice invertido: en vez
--  de ordenar filas por valor, guarda para cada término la lista de filas que
--  lo contienen. Es la misma estructura que usa un buscador web, y es lo que
--  convierte un recorrido O(n) en una consulta que va directa a las filas
--  candidatas.
--
--  Idempotente: se puede correr las veces que haga falta.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- -----------------------------------------------------------------------------
--  `unaccent` no se puede indexar tal cual
-- -----------------------------------------------------------------------------
--  PostgreSQL solo indexa expresiones IMMUTABLE —que devuelven siempre lo
--  mismo para la misma entrada—, y `unaccent()` se declara STABLE porque
--  depende de un diccionario que en teoría podría cambiar.
--
--  El envoltorio fija el diccionario ('public.unaccent') y con eso ya es
--  determinista. Es el patrón recomendado en la documentación de PostgreSQL,
--  no un atajo.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION inmutable_unaccent(texto text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$ SELECT public.unaccent('public.unaccent', texto) $$;

-- -----------------------------------------------------------------------------
--  Usuarios: buscar por nombre o correo tolerando errores
-- -----------------------------------------------------------------------------
--  Un solo índice sobre la concatenación de los dos campos: así una búsqueda
--  cubre ambos sin tener que decidir por cuál buscar ni consultar dos veces.
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_users_busqueda
    ON users
    USING gin (
        (inmutable_unaccent(lower(full_name)) || ' ' || inmutable_unaccent(lower(email)))
        gin_trgm_ops
    );

-- -----------------------------------------------------------------------------
--  Movimientos: texto completo en español sobre la nota
-- -----------------------------------------------------------------------------
--  `coalesce` porque la nota es opcional: sin él, las filas con nota NULL
--  quedarían fuera del índice y la consulta tendría que ir a la tabla igual.
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_transactions_nota_fts
    ON transactions
    USING gin (to_tsvector('spanish', coalesce(note, '')));

--  Y trigramas sobre la misma nota, para los casos que el texto completo no
--  cubre: buscar un trozo de palabra ("aliment") o un código con guiones, que
--  el analizador de español parte de otra manera.
CREATE INDEX IF NOT EXISTS ix_transactions_nota_trgm
    ON transactions
    USING gin (inmutable_unaccent(lower(coalesce(note, ''))) gin_trgm_ops);

-- -----------------------------------------------------------------------------
--  El dueño
-- -----------------------------------------------------------------------------
--  Las migraciones se corren como `postgres`, que es quien puede crear
--  extensiones. Sin este bloque, la función nace siendo suya y la aplicación
--  —que se conecta como `finance_user`— recibe "permission denied".
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finance_user') THEN
        EXECUTE 'ALTER FUNCTION inmutable_unaccent(text) OWNER TO finance_user';
    END IF;
END
$$;

-- =============================================================================
--  Verificación
-- =============================================================================
\echo ''
\echo '--- Extensiones ---'
SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent') ORDER BY extname;

\echo ''
\echo '--- Índices de búsqueda ---'
SELECT indexname, tablename
FROM pg_indexes
WHERE indexname IN ('ix_users_busqueda', 'ix_transactions_nota_fts', 'ix_transactions_nota_trgm')
ORDER BY indexname;

\echo ''
\echo '--- Prueba: buscar "maria" sin tilde debe encontrar "María" ---'
--  Usa `%>` (word_similarity), la MISMA medida que la API.
--
--  Con `%` (similarity a secas) esta comprobacion devolvia cero filas y
--  parecia que la migracion habia fallado: `similarity` compara contra la
--  cadena ENTERA —nombre mas correo— y "maria" contra
--  "maria guerrero maria.guerrero@ejemplo.com" da 0.222, por debajo del
--  umbral de 0.3. Comparando contra la palabra mas parecida da 1.000.
--
--  Verificar con una medida distinta de la que usa el codigo es no verificar
--  nada: o da un susto que no toca, o aprueba algo que no se probo.
SELECT full_name, email,
       round(word_similarity(
           'maria',
           inmutable_unaccent(lower(full_name)) || ' ' || inmutable_unaccent(lower(email))
       )::numeric, 3) AS parecido
FROM users
WHERE (inmutable_unaccent(lower(full_name)) || ' ' || inmutable_unaccent(lower(email)))
      %> 'maria'
ORDER BY parecido DESC
LIMIT 5;
