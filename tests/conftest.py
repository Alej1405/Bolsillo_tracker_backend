"""
Cimientos de las pruebas.

Dos niveles, y la diferencia importa:

  · Las pruebas UNITARIAS no tocan la base. Prueban las reglas de negocio de
    los servicios con dobles en lugar de repositorios. Corren siempre, en
    milisegundos, y son las que se ejecutan mientras se programa.

  · Las de INTEGRACION levantan la aplicacion entera contra una base real y
    hablan por HTTP, como lo haria el frontend. Necesitan PostgreSQL, porque
    la busqueda usa pg_trgm y unaccent: SQLite no los tiene y probar contra
    el no demostraria nada.

Si no hay PostgreSQL de pruebas, las de integracion se saltan con un aviso
claro en vez de fallar. Una prueba en rojo por falta de entorno enseña a
ignorar el rojo, y eso cuesta mas que no tenerla.

NUNCA se conectan a produccion: la URL sale de TEST_DATABASE_URL y, si apunta
a la base de produccion, se aborta.
"""

import os
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:5432/finance_tracker_test",
)

#  Salvaguarda: el nombre de la base de pruebas tiene que decir que lo es.
#  Sin esto, un despiste en la variable de entorno borra datos reales.
if "test" not in TEST_DATABASE_URL.rsplit("/", 1)[-1]:
    raise RuntimeError(
        "TEST_DATABASE_URL debe apuntar a una base cuyo nombre contenga 'test'. "
        f"Recibido: {TEST_DATABASE_URL!r}. Las pruebas crean y borran tablas."
    )


def _hay_postgres() -> bool:
    """Si no hay base de pruebas, las de integracion se saltan."""
    try:
        from sqlalchemy import create_engine, text

        motor = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        with motor.connect() as c:
            c.execute(text("SELECT 1"))
        motor.dispose()
        return True
    except Exception:
        return False


HAY_POSTGRES = _hay_postgres()

requiere_bd = pytest.mark.skipif(
    not HAY_POSTGRES,
    reason=(
        "No hay base de pruebas. Crea una y exporta TEST_DATABASE_URL:\n"
        "  createdb finance_tracker_test\n"
        "  export TEST_DATABASE_URL='postgresql+psycopg://postgres@localhost:5432/finance_tracker_test'"
    ),
)


@pytest.fixture(scope="session")
def motor():
    """
    La base de pruebas, construida con LAS MIGRACIONES DE VERDAD.

    No se usa `Base.metadata.create_all`: eso crea el esquema que describen los
    modelos de Python, que no es exactamente el que hay en produccion. Los
    tipos ENUM, los CHECK, los indices y las extensiones viven en los `.sql`, y
    probar contra un esquema distinto del real es probar otra cosa.

    De paso, esto verifica que las migraciones corren de principio a fin: si
    una esta rota, las pruebas no arrancan.
    """
    import subprocess

    from sqlalchemy import create_engine

    # psql necesita la URL en su propio formato, sin el driver de SQLAlchemy
    url_psql = TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

    migraciones = sorted(Path("db").glob("[0-9]*.sql"))
    assert migraciones, "no encuentro las migraciones en db/"

    #  Base limpia: cada corrida parte de cero para que el orden de las
    #  pruebas nunca cambie el resultado.
    subprocess.run(
        ["psql", url_psql, "-q", "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
        check=True,
        capture_output=True,
    )
    for sql in migraciones + [Path("db/seed.sql")]:
        if not sql.exists():
            continue
        r = subprocess.run(
            ["psql", url_psql, "-q", "-v", "ON_ERROR_STOP=1", "-f", str(sql)],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, "fallo " + sql.name + ":\n" + r.stderr[:600]

    motor = create_engine(TEST_DATABASE_URL)
    yield motor
    motor.dispose()


@pytest.fixture
def sesion(motor):
    """
    Una sesion por prueba, dentro de una transaccion que se revierte al final.

    Asi cada prueba ve la base limpia sin tener que recrear el esquema, que es
    lo lento. Es el patron estandar: abrir transaccion, correr la prueba
    dentro, deshacer.
    """
    from sqlalchemy.orm import sessionmaker

    conexion = motor.connect()
    trans = conexion.begin()
    Sesion = sessionmaker(bind=conexion)
    s = Sesion()
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        conexion.close()


@pytest.fixture
def cliente(sesion):
    """
    La API entera, hablando por HTTP contra la sesion de prueba.

    Sustituye `get_db` para que la aplicacion use la transaccion que se va a
    revertir, en vez de abrir la suya contra la base de verdad.
    """
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    def _db():
        yield sesion

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
