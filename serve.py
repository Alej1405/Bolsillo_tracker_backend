"""
serve.py — punto de entrada del despliegue en el VPS.

No forma parte del backend: envuelve la aplicación de `app/main.py` y le añade
lo único que cambia entre "correr en mi Mac" y "correr en el servidor".

Aquí se despliega SOLO el backend. El frontend vive en otro lado y consume
esta API por su URL pública; por eso el CORS de `main.py` (allow_origins=["*"])
sí importa en este despliegue.

El código de `app/` queda intacto. Si algún día no quieres este envoltorio,
apuntas uvicorn a `app.main:app` y listo.
"""

import os

from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.core.database import SessionLocal, engine
from app.main import app

# `database.py` crea el engine con echo=True, que es lo correcto mientras
# desarrollas pero en el servidor escribe cada SELECT al log y llena el disco.
# Se apaga aquí y se puede volver a encender sin tocar el código:
# basta poner SQL_ECHO=1 en el entorno del servicio.
engine.echo = os.getenv("SQL_ECHO", "0").lower() in ("1", "true", "si")


@app.get("/salud", tags=["infraestructura"])
def salud():
    """Comprueba que el proceso responde y que la base contesta."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - aquí sí queremos cualquier fallo
        return {"estado": "degradado", "base_de_datos": str(exc)}
    return {"estado": "ok", "base_de_datos": "ok"}


@app.get("/", include_in_schema=False)
def raiz():
    """La raíz no sirve una web: este despliegue es solo la API."""
    return RedirectResponse(url="/docs")
