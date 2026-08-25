-- =============================================================================
--  Finance Tracker — Datos iniciales
--
--  Uso:  psql -d finance_tracker -f db/seed.sql
--
--  Categorías del SISTEMA (user_id = NULL): las ve todo el mundo y nadie las
--  puede editar ni borrar. El usuario puede archivar las que no use y crear
--  las suyas propias.
--
--  Este archivo es idempotente: se puede ejecutar varias veces sin duplicar.
-- =============================================================================

-- -----------------------------------------------------------------------------
--  Categorías padre — INGRESOS
-- -----------------------------------------------------------------------------
INSERT INTO categories (user_id, parent_id, name, kind, icon, color) VALUES
    (NULL, NULL, 'Sueldo',          'income', '💼', '#16A34A'),
    (NULL, NULL, 'Trabajos extra',  'income', '🛠️', '#22C55E'),
    (NULL, NULL, 'Ventas',          'income', '🏷️', '#4ADE80'),
    (NULL, NULL, 'Regalos',         'income', '🎁', '#86EFAC'),
    (NULL, NULL, 'Rendimientos',    'income', '📈', '#15803D'),
    (NULL, NULL, 'Otros ingresos',  'income', '➕', '#65A30D')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
--  Categorías padre — EGRESOS
-- -----------------------------------------------------------------------------
INSERT INTO categories (user_id, parent_id, name, kind, icon, color) VALUES
    (NULL, NULL, 'Vivienda',           'expense', '🏠', '#DC2626'),
    (NULL, NULL, 'Servicios básicos',  'expense', '💡', '#EA580C'),
    (NULL, NULL, 'Alimentación',       'expense', '🛒', '#D97706'),
    (NULL, NULL, 'Transporte',         'expense', '🚌', '#CA8A04'),
    (NULL, NULL, 'Salud',              'expense', '🏥', '#0891B2'),
    (NULL, NULL, 'Educación',          'expense', '📚', '#2563EB'),
    (NULL, NULL, 'Entretenimiento',    'expense', '🎬', '#7C3AED'),
    (NULL, NULL, 'Cuidado personal',   'expense', '🧴', '#C026D3'),
    (NULL, NULL, 'Deudas',             'expense', '💳', '#BE123C'),
    (NULL, NULL, 'Otros gastos',       'expense', '➖', '#64748B')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
--  Subcategorías
--
--  El padre se busca por nombre en vez de escribir su UUID a mano: los UUID los
--  genera la base de datos, así que no los conocemos al escribir este archivo.
-- -----------------------------------------------------------------------------
WITH nuevas(padre, nombre, icono) AS (VALUES
    -- Vivienda
    ('Vivienda',          'Arriendo',              '🔑'),
    ('Vivienda',          'Mantenimiento',         '🔧'),
    ('Vivienda',          'Alícuota',              '🏢'),
    -- Servicios básicos
    ('Servicios básicos', 'Luz',                   '⚡'),
    ('Servicios básicos', 'Agua',                  '💧'),
    ('Servicios básicos', 'Internet',              '🌐'),
    ('Servicios básicos', 'Teléfono',              '📱'),
    ('Servicios básicos', 'Gas',                   '🔥'),
    -- Alimentación
    ('Alimentación',      'Mercado',               '🥬'),
    ('Alimentación',      'Restaurantes',          '🍽️'),
    ('Alimentación',      'Café y snacks',         '☕'),
    -- Transporte
    ('Transporte',        'Combustible',           '⛽'),
    ('Transporte',        'Transporte público',    '🚏'),
    ('Transporte',        'Taxi y apps',           '🚕'),
    ('Transporte',        'Mantenimiento vehículo','🔩'),
    -- Salud
    ('Salud',             'Medicinas',             '💊'),
    ('Salud',             'Consultas médicas',     '🩺'),
    ('Salud',             'Seguro de salud',       '🛡️'),
    -- Educación
    ('Educación',         'Matrícula',             '🎓'),
    ('Educación',         'Materiales',            '✏️'),
    ('Educación',         'Cursos y certificados', '📜'),
    -- Entretenimiento
    ('Entretenimiento',   'Suscripciones',         '📺'),
    ('Entretenimiento',   'Salidas',               '🎉'),
    ('Entretenimiento',   'Viajes',                '✈️'),
    -- Cuidado personal
    ('Cuidado personal',  'Ropa',                  '👕'),
    ('Cuidado personal',  'Peluquería',            '💇'),
    ('Cuidado personal',  'Gimnasio',              '🏋️'),
    -- Deudas
    ('Deudas',            'Tarjeta de crédito',    '💳'),
    ('Deudas',            'Préstamos',             '🏦'),
    -- Ingresos
    ('Sueldo',            'Salario mensual',       '💵'),
    ('Sueldo',            'Décimo tercero',        '🎄'),
    ('Sueldo',            'Décimo cuarto',         '🎒'),
    ('Sueldo',            'Utilidades',            '📊')
)
INSERT INTO categories (user_id, parent_id, name, kind, icon, color)
SELECT NULL, p.id, n.nombre, p.kind, n.icono, p.color
FROM nuevas n
JOIN categories p
  ON p.name = n.padre
 AND p.user_id IS NULL
 AND p.parent_id IS NULL
ON CONFLICT DO NOTHING;


-- -----------------------------------------------------------------------------
--  Verificación
-- -----------------------------------------------------------------------------
SELECT
    kind                                              AS tipo,
    count(*) FILTER (WHERE parent_id IS NULL)         AS padres,
    count(*) FILTER (WHERE parent_id IS NOT NULL)     AS subcategorias
FROM categories
WHERE user_id IS NULL
GROUP BY kind
ORDER BY kind;
