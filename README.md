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

Ese último punto es deliberado: si la API devolviera solo los meses con movimientos, cada
cliente tendría que rellenar los huecos para dibujar la gráfica. Se rellenan aquí, una vez.

### Todas las rutas

<details>
<summary><b>Ver el catálogo completo (31 rutas)</b></summary>

| Módulo | Rutas |
|---|---|
| **auth** | `POST /auth/register` · `POST /auth/login` · `GET /auth/me` |
| **accounts** | `GET` · `POST` · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` · `POST /{id}/archive` |
| **categories** | `GET` (árbol) · `POST` · `PATCH /{id}` · `DELETE /{id}` (archiva) |
| **transactions** | `GET` (filtros y paginación) · `POST` · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` |
| **transfers** | `POST /transfers` |
| **reports** | `dashboard` · `summary` · `by-category` · `monthly` |
| **users** | `PATCH /users/me` · `PATCH /users/me/password` · `DELETE /users/me` · y las de `super_admin` |
| **infra** | `GET /salud` |

</details>

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
| Usuario | `equipo` (solo lectura) |
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
