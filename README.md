<div align="center">

<img src="docs/banner.svg" alt="Bolsillo API — el backend que hace las cuentas" width="100%">

<br>

**El backend hace las cuentas. El frontend solo las muestra.**

API de Bolsillo, la aplicación de finanzas personales: registra movimientos, los reparte
por categoría y por bolsillo, y devuelve los reportes ya calculados.

<br>

[![Documentación viva](https://img.shields.io/badge/Swagger-probar_la_API-45596F?style=for-the-badge&logo=swagger&logoColor=white)](https://finance.srv1666598.hstgr.cloud/docs)
&nbsp;
[![Despliegue](https://github.com/Alej1405/Bolsillo_tracker_backend/actions/workflows/desplegar.yml/badge.svg)](https://github.com/Alej1405/Bolsillo_tracker_backend/actions/workflows/desplegar.yml)

<br>

![Python](https://img.shields.io/badge/Python-3.12-45596F?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.140-45596F?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-45596F?style=flat-square&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-45596F?style=flat-square)
![JWT](https://img.shields.io/badge/JWT-HS256-553D78?style=flat-square)

</div>

---

## Qué resuelve

Registrar un gasto debe costar dos toques. Todo lo demás —sumar, repartir, comparar
meses, decir cuánto queda disponible— lo hace esta API. **El cliente nunca calcula**:
pide un reporte y recibe el número final, listo para mostrar.

Los saldos no se guardan en una columna: se derivan de los movimientos. Así no existe
el estado clásico en que el saldo dice una cosa y las transacciones otra.

| | |
|---|---|
| **API en vivo** | [finance.srv1666598.hstgr.cloud](https://finance.srv1666598.hstgr.cloud/docs) |
| **Frontend** | [Bolsillo_tracker](https://github.com/Alej1405/Bolsillo_tracker) — repositorio aparte |
| **Base** | PostgreSQL 16, accesible solo por túnel SSH |

---

## Arquitectura

Cada petición baja por cinco capas y cada una tiene una sola responsabilidad. La regla
que las mantiene ordenadas: **una capa solo habla con la de abajo**. Un router jamás
consulta la base directamente.

```mermaid
flowchart TD
    C([Cliente]) -->|HTTP + JWT| R["routers/<br><i>reciben y validan</i>"]
    R --> S["schemas/<br><i>qué entra y qué sale</i>"]
    S --> SV["services/<br><i>las reglas de negocio</i>"]
    SV --> RP["repositories/<br><i>las consultas</i>"]
    RP --> M["models/<br><i>las tablas</i>"]
    M --> DB[("PostgreSQL")]

    style SV fill:#553d78,color:#fff,stroke:none
    style DB fill:#283445,color:#fff,stroke:none
    style R fill:#ece9f6,stroke:#7c628b
    style RP fill:#ece9f6,stroke:#7c628b
```

**Por qué importa la separación**: la regla "no puedes transferir a la misma cuenta"
vive en `services/`, no en el router. Si mañana esa operación se expone por otra vía,
la regla sigue aplicándose sin duplicar código.

```
app/
├── routers/       reciben HTTP, comprueban permisos, delegan
├── schemas/       contratos de entrada y salida (Pydantic)
├── services/      reglas de negocio  ← aquí se decide
├── repositories/  consultas a la base ← aquí se pregunta
├── models/        tablas (SQLAlchemy)
└── core/          base de datos, seguridad, errores, dependencias
db/                esquema SQL numerado y datos de ejemplo
serve.py           punto de entrada en el servidor
```

---

## Qué se puede hacer con la API

Autenticación **Bearer JWT**, válido 24 horas. Todas las rutas cuelgan de `/api/v1`.

### Empezar: crear cuenta y obtener el token

```bash
API=https://finance.srv1666598.hstgr.cloud/api/v1

curl -X POST $API/auth/register -H 'Content-Type: application/json' -d '{
  "full_name": "Ana Pérez",
  "email": "ana@ejemplo.com",
  "password": "unaClaveLarga123"
}'

# El login devuelve el access_token que usarás en todo lo demás
TOKEN=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"ana@ejemplo.com","password":"unaClaveLarga123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

### Crear un bolsillo y registrar un gasto

```bash
# Un bolsillo es una cuenta: cash, bank, card o savings
curl -X POST $API/accounts -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Mi efectivo","type":"cash","initial_balance":420.00,"currency":"USD"}'

# Un gasto necesita monto, cuenta, categoría y fecha
curl -X POST $API/transactions -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type":"expense","amount":12.75,"account_id":"<uuid>",
       "category_id":"<uuid>","occurred_at":"2026-08-25","note":"Almuerzo"}'
```

### Mover plata entre bolsillos

Una transferencia **no es un gasto**: no aparece en "en qué se fue la plata", porque el
dinero no salió de tu patrimonio, solo cambió de sitio. Por eso tiene su propia ruta.

```bash
curl -X POST $API/transfers -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"amount":100.00,"account_id":"<origen>","counter_account_id":"<destino>",
       "occurred_at":"2026-08-25","note":"Para el viaje"}'
```

### Los reportes: aquí es donde la API se gana el sueldo

```bash
curl -H "Authorization: Bearer $TOKEN" "$API/reports/dashboard"
curl -H "Authorization: Bearer $TOKEN" "$API/reports/summary?from=2026-08-01&to=2026-08-31"
curl -H "Authorization: Bearer $TOKEN" "$API/reports/by-category?from=2026-08-01&to=2026-08-31"
curl -H "Authorization: Bearer $TOKEN" "$API/reports/monthly?year=2026"
```

| Reporte | Qué devuelve | Detalle que evita trabajo al cliente |
|---|---|---|
| `dashboard` | Todo lo de la pantalla principal | Una sola petición en lugar de cuatro |
| `summary` | Ingresos, egresos, neto y ahorrado | El neto ya viene restado |
| `by-category` | En qué se fue la plata | El **porcentaje ya viene calculado** |
| `monthly` | Evolución del año | Devuelve **los 12 meses**, con ceros donde no hubo datos |
| `performance` | Cómo va tu dinero | Cada medida trae su **frase ya redactada** y su nivel |

Ese último punto es deliberado: si la API devolviera solo los meses con movimientos, cada
cliente tendría que rellenar los huecos para dibujar la gráfica. Se rellenan aquí, una vez.

`performance` va un paso más allá. Devuelve seis medidas de cómo va el dinero —cuánto tienes,
cuánto guardaste, de cada $100 cuánto se queda, cuánto te dura lo que tienes, cuánto gastas al
día y cómo te fue frente al periodo anterior— y cada una viene con tres cosas: el número
(`value`), una frase escrita para que la entienda cualquiera (`reading`) y un semáforo
(`level`: `bien`, `atencion` o `mal`) para pintarla sin tener que interpretarla:

```json
{
  "key": "cuanto_aguanta",
  "label": "Cuánto te dura lo que tienes",
  "value": 2.1,
  "unit": "meses",
  "reading": "Si dejaras de recibir dinero, lo que tienes te alcanza para 2,1 meses.",
  "level": "atencion"
}
```

Detrás son las métricas de siempre —patrimonio, tasa de ahorro, meses de colchón, gasto medio
diario, variación contra el periodo anterior— pero el nombre técnico no sale nunca a la
pantalla. Un niño de diez años y una persona de setenta tienen que poder leer la frase y saber
qué hacer con ella.

**Ahorro**: `net_worth` suma **todos** los bolsillos activos —el efectivo, el banco, la
tarjeta, la alcancía—, no solo los de tipo `savings`. Ahorrar no es tener una cuenta
etiquetada como ahorro: es lo que te queda sumando todo lo que tienes.

### Todas las rutas

<details>
<summary><b>Ver el catálogo completo (34 rutas)</b></summary>

| Módulo | Rutas |
|---|---|
| **auth** | `POST /auth/register` · `POST /auth/login` · `GET /auth/me` |
| **accounts** | `GET` · `POST` · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` · `POST /{id}/archive` · `POST /{id}/unarchive` |
| **categories** | `GET` (árbol) · `POST` · `PATCH /{id}` · `DELETE /{id}` (archiva) |
| **transactions** | `GET` (filtros y paginación) · `POST` · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` |
| **transfers** | `POST /transfers` |
| **reports** | `dashboard` · `summary` · `by-category` · `monthly` · `performance` |
| **users** | `PATCH /users/me` · `PATCH /users/me/password` · `POST /users/me/avatar` · `DELETE /users/me/avatar` · `DELETE /users/me` · y las de `super_admin` |

</details>

### La foto de perfil

```bash
curl -X POST "$API/users/me/avatar" \
  -H "Authorization: Bearer $TOKEN" \
  -F "archivo=@mi-foto.jpg"
```

La respuesta es la ficha del usuario con `avatar_url` puesto:
`/media/avatares/<id>-<sufijo>.jpg`. Es una ruta del servidor, no una URL completa: el
cliente la pega a la base de la API. `DELETE /users/me/avatar` la quita y deja `avatar_url`
en `null`, que es cuando la interfaz muestra las iniciales.

Tres decisiones detrás:

- **La imagen va al disco, no a la base.** En la base queda solo la dirección. Una foto
  dentro de una tabla la hace pesada, lenta de respaldar y obliga a leerla en cada consulta
  de usuario aunque nadie la mire.
- **El formato se comprueba en los bytes, no en el nombre.** Se leen los primeros bytes del
  archivo y se busca la firma de JPG, PNG o WEBP. Renombrar `virus.exe` a `foto.jpg` no
  cuesta nada; cambiar los bytes de cabecera sí. Máximo 2 MB.
- **Cada subida genera un nombre nuevo** con un sufijo aleatorio, y borra la foto anterior
  del disco. Si el archivo se llamara siempre igual, el navegador seguiría mostrando la foto
  vieja de su caché después de cambiarla.

---

## Cómo busca la API

Ninguna búsqueda recorre datos en Python: todas se resuelven en PostgreSQL, que es
quien tiene los índices. Lo que sigue es qué algoritmo usa cada una y por qué.

| Búsqueda | Dónde vive | Estructura que usa | Coste |
|---|---|---|---|
| Un movimiento por su id | `transaction_repository.get_by_id` | Índice B-tree de la clave primaria | O(log n) |
| Mis movimientos, por fecha | `transaction_repository.list_paginated` | Índice B-tree compuesto y parcial `ix_tx_user_date` | O(log n + k) |
| Texto dentro de la nota | `_aplicar_filtros`, rama `search` | Ninguna: recorrido secuencial | O(n) |
| Movimientos de un bolsillo | `_aplicar_filtros`, rama `account_id` | Dos índices combinados con mapa de bits | O(log n + k) |
| Movimientos de una categoría | `_aplicar_filtros`, rama `category_id` | Subconsulta de la familia + `ix_tx_category` | O(log n + k) |
| El árbol de categorías | `category_repository.list_tree` | Dos consultas, no una por padre | O(p + h) |
| Un nombre repetido | `category_repository.get_by_name` | Índice único sobre `lower(name)` | O(log n) |

`n` es el total de filas, `k` las que devuelve la página, `p` las categorías padre y `h` sus hijas.

### Búsqueda por índice: el camino normal

El listado de movimientos es lo que más se consulta, y por eso la base tiene un índice
hecho a su medida:

```sql
CREATE INDEX ix_tx_user_date ON transactions (user_id, occurred_at DESC)
    WHERE deleted_at IS NULL;
```

Un índice B-tree es un árbol ordenado: para encontrar un valor no mira fila por fila,
sino que baja por el árbol descartando la mitad en cada paso. Ese índice tiene además
dos decisiones que importan:

- **Es compuesto** (`user_id`, `occurred_at`). Como toda consulta empieza filtrando por
  usuario y sigue ordenando por fecha, el índice entrega las filas **ya ordenadas**: la
  base no tiene que ordenarlas después.
- **Es parcial** (`WHERE deleted_at IS NULL`). El borrado es lógico —la fila se queda en
  la tabla—, así que las borradas no entran al índice. Ocupa menos y se recorre más rápido.

El plan real lo confirma:

```
Limit
  ->  Index Scan using ix_tx_user_date on transactions
        Index Cond: (user_id = '…')
```

`Index Scan`: entra por el índice y toca solo las filas que devuelve.

### Búsqueda por texto: por qué esta sí recorre todo

Buscar en las notas se traduce a `note ILIKE '%mercado%'`, y esa consulta **no puede usar
un índice B-tree**. La razón es lo que hace el árbol: ordena las palabras por su comienzo,
igual que un diccionario. Un diccionario sirve para buscar "mercado", no para buscar
"todas las palabras que contengan 'erca' en algún lugar". El comodín del principio deja el
orden inservible.

El plan lo dice sin rodeos:

```
Seq Scan on transactions
  Filter: ((deleted_at IS NULL) AND (note ~~* '%mercado%') AND (user_id = '…'))
  Rows Removed by Filter: 64
```

`Seq Scan` es recorrido secuencial: lee las filas del usuario una por una y descarta las
que no coinciden. Con los volúmenes de una persona —cientos o pocos miles de movimientos—
es instantáneo y no vale la pena complicarlo. Si algún día una cuenta llegara a cientos de
miles de notas, el arreglo ya está identificado: un índice **GIN con `pg_trgm`**, que parte
cada texto en grupos de tres letras e indexa esos fragmentos, con lo que el comodín inicial
deja de estorbar.

```sql
-- No está aplicado: queda anotado para cuando el volumen lo pida.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_tx_note_trgm ON transactions USING gin (note gin_trgm_ops);
```

### Filtrar por categoría: expandir la familia, sin recursión

Al filtrar por una categoría padre deben entrar también sus hijas. En vez de recorrer un
árbol, se resuelve con una subconsulta:

```python
familia = select(Category.id).where(
    or_(Category.id == category_id, Category.parent_id == category_id)
)
stmt = stmt.where(Transaction.category_id.in_(familia))
```

No hay recursión porque **el árbol tiene dos niveles y solo dos**: padre e hija. Un nivel
de expansión cubre todos los casos. Si el modelo admitiera profundidad libre haría falta
un `WITH RECURSIVE`, y con él un coste mucho mayor por consulta.

### Un movimiento que cuenta para dos bolsillos

Una transferencia toca dos cuentas: la de origen (`account_id`) y la de destino
(`counter_account_id`). Al filtrar por un bolsillo, la fila debe aparecer si es cualquiera
de las dos, y eso es un `OR` sobre dos columnas, cada una con su índice
(`ix_tx_account`, `ix_tx_counter`). PostgreSQL no elige uno: usa los dos y combina los
resultados con un mapa de bits (`BitmapOr`) antes de ir a la tabla.

### El árbol de categorías: 2 consultas, no 18

`list_tree` pide los padres y usa `selectinload` para las hijas:

```python
select(Category).where(...).options(selectinload(Category.children))
```

`selectinload` trae **todas** las hijas en una segunda consulta (`WHERE parent_id IN (…)`).
Sin eso, el ORM pediría las hijas de cada padre por separado: con 17 categorías padre serían
18 viajes a la base en lugar de 2. Es el problema N+1, y esta es su solución.

### Nombres repetidos: buscar como busca el índice

Para saber si ya existe una categoría con ese nombre, la consulta compara
`lower(Category.name) == name.lower()`. No es capricho: el índice único de la base también
está definido sobre `lower(name)`, así que la búsqueda usa exactamente el mismo índice que
después impide el duplicado. Si la consulta comparara el nombre tal cual, el índice no
serviría y "Salud" y "salud" pasarían dos veces el control de la aplicación antes de que la
base rechazara el insert.

### Paginación

El listado pagina con `LIMIT` y `OFFSET`, y cuenta el total **antes** de recortar, sobre los
mismos filtros:

```python
total = db.scalar(select(func.count()).select_from(stmt.subquery()))
stmt = stmt.limit(page_size).offset((page - 1) * page_size)
```

`OFFSET` tiene un límite conocido: para llegar a la página 500 la base atraviesa las 499
anteriores y las descarta. En una aplicación personal, donde nadie pasa de las primeras
páginas, es la opción correcta por lo simple. La alternativa para volúmenes grandes es
paginar por cursor —"dame lo anterior a esta fecha"—, que no necesita saltar filas.

---

## Consultar la base directamente

La base **no acepta conexiones desde internet**: escucha solo en `127.0.0.1` del
servidor. Se entra por un túnel SSH, que publica el puerto en tu máquina.

```bash
ssh -N -L 5434:127.0.0.1:5432 vps_masha_miro
```

Con eso, `localhost:5434` es la base del servidor. En pgAdmin o DBeaver:

| Campo | Valor |
|---|---|
| Host | `127.0.0.1` |
| Puerto | `5434` |
| Base | `finance_tracker` |
| Usuario | `consulta` (solo lectura) |
| Contraseña | se entrega aparte, nunca por el repositorio |

### El modelo de datos

```mermaid
erDiagram
    users ||--o{ accounts : "tiene"
    users ||--o{ categories : "define"
    users ||--o{ transactions : "registra"
    accounts ||--o{ transactions : "origen"
    categories ||--o{ transactions : "clasifica"
    categories ||--o{ categories : "subcategoría de"
```

| Tabla | Guarda | Detalle |
|---|---|---|
| `users` | Personas | La contraseña nunca: solo su hash bcrypt |
| `accounts` | Bolsillos | `cash`, `bank`, `card`, `savings`. Se archivan, no se borran |
| `categories` | Árbol de categorías | `parent_id` permite subcategorías |
| `transactions` | Movimientos | `income`, `expense`, `transfer`. Borrado lógico con `deleted_at` |

Tres decisiones que conviene conocer antes de escribir cualquier consulta:

- **Nada se borra de verdad.** `deleted_at` en movimientos, `archived_at` en cuentas y
  categorías. Toda consulta debe filtrar `WHERE deleted_at IS NULL`, o contará cosas
  que el usuario ya eliminó.
- **Las transferencias usan dos columnas**: `account_id` (de dónde sale) y
  `counter_account_id` (a dónde llega). Al calcular saldos hay que mirar ambas.
- **Los montos son `numeric(14,2)`**, nunca `float`. Con dinero, el redondeo binario
  de los flotantes produce diferencias de centavos que no cuadran.

### Consultas listas para usar

Todas están probadas contra la base real.

**Saldo real de cada bolsillo** — el saldo no está guardado, se calcula:

```sql
SELECT a.name AS cuenta, a.type AS tipo,
       a.initial_balance
       + COALESCE(SUM(CASE WHEN t.type='income'  THEN t.amount
                           WHEN t.type='expense' THEN -t.amount END), 0)
       + COALESCE(SUM(CASE WHEN t.type='transfer' AND t.counter_account_id=a.id THEN  t.amount
                           WHEN t.type='transfer' AND t.account_id=a.id         THEN -t.amount END), 0)
       AS saldo
FROM accounts a
LEFT JOIN transactions t
  ON t.deleted_at IS NULL AND (t.account_id=a.id OR t.counter_account_id=a.id)
WHERE a.archived_at IS NULL
GROUP BY a.id, a.name, a.type, a.initial_balance
ORDER BY a.name;
```

**En qué se fue la plata este mes**, agrupando subcategorías bajo su padre:

```sql
SELECT COALESCE(p.name, c.name) AS categoria,
       SUM(t.amount) AS gastado,
       ROUND(100 * SUM(t.amount) / NULLIF(SUM(SUM(t.amount)) OVER (), 0), 1) AS porcentaje
FROM transactions t
JOIN categories c ON c.id = t.category_id
LEFT JOIN categories p ON p.id = c.parent_id
WHERE t.type = 'expense'
  AND t.deleted_at IS NULL
  AND t.occurred_at >= date_trunc('month', CURRENT_DATE)
GROUP BY COALESCE(p.name, c.name)
ORDER BY gastado DESC;
```

`SUM(SUM(...)) OVER ()` es el total de todas las filas: permite sacar el porcentaje sin
una segunda consulta.

**Cuánto entró y cuánto salió este mes:**

```sql
SELECT SUM(amount) FILTER (WHERE type='income')  AS entro,
       SUM(amount) FILTER (WHERE type='expense') AS salio,
       COALESCE(SUM(amount) FILTER (WHERE type='income'), 0)
       - COALESCE(SUM(amount) FILTER (WHERE type='expense'), 0) AS neto
FROM transactions
WHERE deleted_at IS NULL
  AND occurred_at >= date_trunc('month', CURRENT_DATE);
```

`FILTER` es de PostgreSQL y se lee mejor que un `CASE WHEN` dentro del `SUM`.

**Últimos movimientos, en lenguaje humano:**

```sql
SELECT t.occurred_at AS fecha, t.type AS tipo, c.name AS categoria,
       a.name AS cuenta, t.amount AS monto, t.note AS nota
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
LEFT JOIN accounts a   ON a.id = t.account_id
WHERE t.deleted_at IS NULL
ORDER BY t.occurred_at DESC, t.created_at DESC
LIMIT 20;
```

---

## Levantarlo en tu máquina

```bash
git clone git@github.com:Alej1405/Bolsillo_tracker_backend.git
cd Bolsillo_tracker_backend

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # y pon tus valores
```

Crear la base y cargar el esquema, en orden (los archivos van numerados por sus
dependencias: no puedes crear `transactions` antes que `accounts`):

```bash
createdb finance_tracker
for f in db/0*.sql; do psql -d finance_tracker -f "$f"; done
psql -d finance_tracker -f db/seed.sql    # categorías de ejemplo
```

```bash
uvicorn app.main:app --reload
```

La documentación interactiva queda en <http://localhost:8000/docs>: desde ahí se pueden
probar todas las rutas sin escribir una línea de código.

### Variables de entorno

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://usuario:clave@localhost:5432/finance_tracker` |
| `SECRET_KEY` | Firma los JWT. Genérala con `openssl rand -hex 32` |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_HOURS` | Validez del token (24) |
| `RESEND_API_KEY` | Clave del panel de Resend, para el correo saliente |
| `RESEND_FROM` | Remitente. Su dominio debe estar verificado en Resend |
| `MEDIA_DIR` | Carpeta de las fotos de perfil (`media`). En el servidor, un disco que sobreviva al despliegue |
| `AVATAR_MAX_MB` | Tope por foto (2) |

`.env` está en el `.gitignore` y **nunca** debe subirse.

---

## Despliegue

Cada push a `main` dispara [`.github/workflows/desplegar.yml`](.github/workflows/desplegar.yml):

```
push a main → compila → arranca la app → el VPS se sincroniza → reinicia → verifica /salud
```

El servidor **se actualiza a sí mismo desde este repositorio**. No se le copian archivos:
descarga `main`, instala dependencias y reinicia el servicio. La consecuencia es que lo
que corre en producción es, por construcción, exactamente lo que hay en `main`.

La clave de despliegue está restringida a ejecutar **un solo comando** y no puede abrir
terminal ni leer archivos. Los detalles, en [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md).

---

## Convenciones

- **El backend calcula, el cliente formatea.** Ningún consumidor suma ni promedia.
- **CRUD completo por módulo**: ninguno se cierra sin sus cuatro operaciones.
- **Programación orientada a objetos** en capas: servicios y repositorios son clases.
- **Nada se borra**: borrado lógico y archivado, siempre.
- **Dinero en `numeric`**, jamás en coma flotante.

---

## Equipo

Proyecto académico de la **Pontificia Universidad Católica del Ecuador**.
Backend: [@Alej1405](https://github.com/Alej1405).

<div align="center">
<br>
<sub>Hecho en Ecuador 🇪🇨</sub>
</div>
