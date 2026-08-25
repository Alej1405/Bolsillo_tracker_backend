# Despliegue

Cada push a `main` actualiza la API en <https://finance.srv1666598.hstgr.cloud> sin
intervención manual.

```
push a main
   ↓
Actions · "Validar"        compila, arranca la app, revisa el SQL
   ↓                        (también en cada pull request)
Actions · "Publicar"       una orden por SSH: "actualízate"
   ↓                        (nunca desde un pull request)
VPS · script de despliegue  descarga main → instala → reinicia → verifica
```

## El servidor se sincroniza solo

A diferencia del frontend, donde basta copiar archivos estáticos, aquí hay que instalar
dependencias y reiniciar un servicio. Por eso **Actions no copia nada**: solo le dice al
servidor que se actualice, y el servidor descarga `main` de este repositorio por su cuenta.

Tiene una consecuencia valiosa: lo que corre en producción es, por construcción,
exactamente lo que hay en `main`. No existe la deriva típica de "alguien tocó un archivo
en el servidor y nadie se enteró" — el siguiente despliegue lo revierte.

El script vive en el VPS, en `/usr/local/sbin/desplegar-bolsillo-backend`, y hace:

1. Descarga el tarball de `main` desde GitHub.
2. **Comprueba que llegó completo** (`app/main.py`, `serve.py`, `requirements.txt`). Si
   falta algo, aborta **sin tocar lo que está corriendo**.
3. Copia el código conservando `.env` y `.venv`.
4. Instala las dependencias en el entorno virtual.
5. Reinicia `finance-tracker.service`.
6. Consulta `/salud` hasta cinco veces. Si la API no responde, el despliegue sale en rojo.

El paso 2 es el que evita el peor escenario: un tarball truncado dejaría la aplicación a
medias. Es preferible no desplegar a desplegar algo roto.

---

## Seguridad

El repositorio es público: cualquiera lee este workflow y cualquiera puede abrir un PR.

### La clave de despliegue solo sabe hacer una cosa

En `~/.ssh/authorized_keys` del servidor:

```
restrict,command="/usr/local/sbin/desplegar-bolsillo-backend" ssh-ed25519 AAAA…
```

| Restricción | Qué impide |
|---|---|
| `restrict` | Terminal, túneles de puertos, reenvío de agente, X11 |
| `command="…"` | Ejecutar cualquier otra cosa: el comando que envíe el cliente **se descarta** |

Comprobado en el servidor — se pidió leer el archivo de credenciales y el servidor
ejecutó el script de despliegue en su lugar:

```
$ ssh -i clave root@… 'cat /root/.credenciales/finance-tracker.env'
== Descargando main de Alej1405/Bolsillo_tracker_backend
```

Nunca llegó a ejecutarse el `cat`. Si la clave se filtrara, lo único que un atacante
podría hacer es forzar un redespliegue del código que ya está en `main`.

### El resto de capas

- **Trabajos separados**: el que usa los secretos lleva `if` sobre `event_name`, `ref` y
  `repository`. Un pull request se queda en la validación; un fork no puede desplegar.
- **Nada del servidor en el código**: host, usuario y huella están en Secrets, que GitHub
  no entrega a workflows de forks.
- **Acciones fijadas por SHA**, no por etiqueta: una etiqueta se puede reapuntar.
- **`StrictHostKeyChecking=yes`** con huella conocida, en vez del habitual `=no`, que
  acepta a cualquiera que responda en esa IP.
- **`permissions: contents: read`** — el workflow no puede escribir en el repositorio.
- La clave se borra del runner con `if: always()`.
- **`cancel-in-progress: false`**: cancelar a mitad dejaría el servicio reiniciándose.

---

## Secrets del repositorio

En **Settings → Secrets and variables → Actions**:

| Secreto | Valor | Obligatorio |
|---|---|---|
| `VPS_HOST` | `2.24.95.219` | Sí |
| `VPS_USUARIO` | `root` | Sí |
| `VPS_SSH_KEY` | Clave **privada** de despliegue, completa | Sí |
| `VPS_KNOWN_HOSTS` | `2.24.95.219 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAZAWOhAGBxE3y4nUi95dIMphe/MGEj6cZZBB6/37g3s` | Sí |
| `VPS_PUERTO` | Solo si el SSH no está en el 22 | No |

La huella se verificó preguntándosela al propio servidor por un canal ya autenticado,
no aceptando la que ofreció la red:

```
SHA256:92yLL7h/ymDr59+U4XBC69iz/tAqfUmIzOcGsxRT4Rw  (ED25519)
```

---

## La base de datos

PostgreSQL **no acepta conexiones desde internet**. Escucha solo en `127.0.0.1` y el
puerto 5432 está cerrado en el cortafuegos.

```
listen_addresses = 'localhost'
```

Antes escuchaba en `0.0.0.0` con tres reglas `hostssl … 0.0.0.0/0` en `pg_hba.conf`, que
permitían conectarse desde cualquier IP del mundo. Están anuladas y comentadas con la
fecha del cambio; los archivos originales quedaron respaldados junto a ellos
(`postgresql.conf.bak.*`, `pg_hba.conf.bak.*`).

Para entrar desde fuera, túnel SSH:

```bash
ssh -N -L 5434:127.0.0.1:5432 vps_masha_miro
```

En la Mac de Pablo eso lo mantiene levantado un agente de macOS,
`~/Library/LaunchAgents/com.mashaec.tunel-postgres-lab.plist`, que lo reabre solo si la
conexión se cae. pgAdmin apunta a `127.0.0.1:5434`.

---

## Rehacer la clave de despliegue

```bash
ssh-keygen -t ed25519 -N "" -C "actions-despliegue-backend" -f ./despliegue_backend

PUB=$(cat despliegue_backend.pub)
ssh vps_masha_miro "
  cp ~/.ssh/authorized_keys ~/.ssh/authorized_keys.bak.\$(date +%Y%m%d-%H%M%S)
  grep -v 'actions-despliegue-backend' ~/.ssh/authorized_keys > ~/.ssh/ak.tmp || true
  echo 'restrict,command=\"/usr/local/sbin/desplegar-bolsillo-backend\" $PUB' >> ~/.ssh/ak.tmp
  mv ~/.ssh/ak.tmp ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
"

cat despliegue_backend | pbcopy     # pegar en el secreto VPS_SSH_KEY
rm -f despliegue_backend despliegue_backend.pub
```

---

## Si algo falla

| Síntoma | Causa habitual |
|---|---|
| `Permission denied (publickey)` | `VPS_SSH_KEY` incompleta o sin salto de línea final |
| `Host key verification failed` | `VPS_KNOWN_HOSTS` vacío o la huella cambió |
| `ERROR: falta serve.py en el repositorio` | El archivo no está en `main`: la salvaguarda funcionó |
| `ERROR: la API no respondió` | Mira `journalctl -u finance-tracker -n 50` en el servidor |
| El despliegue pasa pero la API da 502 | El servicio no arrancó: casi siempre un fallo al importar |

Comprobaciones rápidas en el servidor:

```bash
systemctl status finance-tracker --no-pager
journalctl -u finance-tracker -n 50 --no-pager
curl -s http://127.0.0.1:8000/salud
```

Y para lanzar un despliegue a mano:

```bash
ssh vps_masha_miro /usr/local/sbin/desplegar-bolsillo-backend
```
