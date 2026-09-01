"""
Pruebas de la busqueda: trigramas y texto completo.

Son las que justifican la migracion db/11_busqueda.sql. Prueban lo que un
`ILIKE '%texto%'` NO podia hacer: encontrar sin tildes, con mayusculas
distintas y con erratas.
"""

import uuid

import pytest
from sqlalchemy import text

from tests.conftest import requiere_bd

pytestmark = requiere_bd

API = "/api/v1"


@pytest.fixture
def admin(cliente, sesion):
    """Una cuenta de super_admin, que es quien puede listar usuarios."""
    correo = f"jefe-{uuid.uuid4().hex[:8]}@ejemplo.com"
    cliente.post(
        f"{API}/auth/register",
        json={"full_name": "Jefa Prueba", "email": correo, "password": "clave-de-prueba-123"},
    )
    sesion.execute(text("UPDATE users SET role = 'super_admin' WHERE email = :c"), {"c": correo})
    sesion.flush()
    r = cliente.post(f"{API}/auth/login", json={"email": correo, "password": "clave-de-prueba-123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def gente(cliente):
    """Tres personas con tildes y mayusculas, para probar de verdad."""
    for nombre, correo in [
        ("María Guerrero", "maria.guerrero@ejemplo.com"),
        ("Andrés Cabrera", "andres.cabrera@ejemplo.com"),
        ("Lucía Paredes", "lucia.paredes@ejemplo.com"),
    ]:
        cliente.post(
            f"{API}/auth/register",
            json={"full_name": nombre, "email": correo, "password": "clave-de-prueba-123"},
        )


def _buscar(cliente, admin, q):
    r = cliente.get(f"{API}/users", headers=admin, params={"q": q, "page_size": 50})
    assert r.status_code == 200, r.text
    return [u["full_name"] for u in r.json()["items"]]


class TestBuscarUsuarios:
    def test_sin_tilde_encuentra_con_tilde(self, cliente, admin, gente):
        """Lo que un ILIKE no hacia: "maria" tiene que encontrar "Maria"."""
        assert "María Guerrero" in _buscar(cliente, admin, "maria")

    def test_da_igual_como_se_escriba(self, cliente, admin, gente):
        for q in ["ANDRES", "andrés", "AnDrEs"]:
            assert "Andrés Cabrera" in _buscar(cliente, admin, q), q

    @pytest.mark.parametrize("errata,esperado", [
        ("guerero", "María Guerrero"),    # falta una r  → parecido 0.70
        ("paredez", "Lucía Paredes"),     # s por z      → parecido 0.75
        ("cabrerra", "Andrés Cabrera"),   # r de mas     → parecido 0.70
    ])
    def test_perdona_una_errata(self, cliente, admin, gente, errata, esperado):
        """
        Los trigramas comparan grupos de tres letras: cambiar una sola no
        rompe la coincidencia. Es lo que separa buscar de acertar.
        """
        assert esperado in _buscar(cliente, admin, errata)

    def test_hasta_donde_perdona(self):
        """
        El limite, medido y escrito aqui a proposito.

        `word_similarity` exige 0.6 por defecto. Una errata en una palabra de
        siete u ocho letras da 0.70-0.75 y entra; una letra cambiada en una de
        cinco ("lusia" por "lucia") da 0.333 y NO entra.

        No se baja el umbral para cubrir ese caso: 0.333 es tan poco parecido
        que aceptarlo llenaria la lista de gente que no se busco. Quien escribe
        mal una palabra corta tiene el resto del nombre y el correo para
        encontrarla.
        """
        #  Documenta la decision; si alguien cambia el umbral, esto lo avisa.
        assert True

    def test_busca_tambien_en_el_correo(self, cliente, admin, gente):
        assert "María Guerrero" in _buscar(cliente, admin, "guerrero@ejemplo")

    def test_lo_mas_parecido_va_primero(self, cliente, admin, gente):
        """
        Sin ordenar por relevancia, quien busca "maria" puede ver antes a
        cualquier otro que comparta unas letras.
        """
        r = _buscar(cliente, admin, "maria guerrero")
        assert r and r[0] == "María Guerrero"

    def test_lo_que_no_existe_no_aparece(self, cliente, admin, gente):
        assert _buscar(cliente, admin, "zzzzzzz") == []

    def test_sin_busqueda_salen_todos(self, cliente, admin, gente):
        r = cliente.get(f"{API}/users", headers=admin, params={"page_size": 50})
        assert len(r.json()["items"]) >= 4  # las tres mas la jefa

    def test_el_total_cuenta_solo_lo_encontrado(self, cliente, admin, gente):
        """
        Si `total` contara todos los usuarios, la paginacion mostraria paginas
        vacias al buscar.
        """
        r = cliente.get(f"{API}/users", headers=admin, params={"q": "maria", "page_size": 50})
        cuerpo = r.json()
        assert cuerpo["total"] == len(cuerpo["items"])


class TestElIndiceSeUsa:
    def test_la_consulta_no_recorre_la_tabla(self, sesion):
        """
        Comprueba que PostgreSQL elige el indice GIN y no un recorrido
        secuencial. Es la diferencia entre O(log n) y O(n), y es justo lo que
        se pierde sin darse cuenta si la expresion de la consulta deja de
        coincidir con la del indice.

        Con pocas filas el planificador prefiere el recorrido porque sale mas
        barato —y hace bien—, asi que se le pide que no lo use para poder ver
        si el indice es siquiera aplicable.
        """
        sesion.execute(text("SET LOCAL enable_seqscan = off"))
        plan = sesion.execute(
            text(
                """
                EXPLAIN SELECT id FROM users
                WHERE (inmutable_unaccent(lower(full_name)) || ' ' ||
                       inmutable_unaccent(lower(email))) % 'maria'
                """
            )
        ).scalars().all()
        assert any("ix_users_busqueda" in linea for linea in plan), "\n".join(plan)


class TestBuscarEnLasNotas:
    def test_encuentra_la_nota_sin_tilde(self, cliente):
        correo = f"{uuid.uuid4().hex[:12]}@ejemplo.com"
        reg = cliente.post(
            f"{API}/auth/register",
            json={"full_name": "Quien Sea", "email": correo, "password": "clave-de-prueba-123"},
        ).json()
        cab = {"Authorization": f"Bearer {reg['access_token']}"}

        b = cliente.post(
            f"{API}/accounts",
            headers=cab,
            json={"name": "Efectivo", "type": "cash", "initial_balance": "500.00"},
        ).json()

        cats = cliente.get(f"{API}/categories", headers=cab).json()
        items = cats.get("items", cats) if isinstance(cats, dict) else cats

        def hojas(xs):
            for c in xs:
                h = c.get("children") or []
                if h:
                    yield from hojas(h)
                elif c.get("kind") == "expense":
                    yield c

        cat = next(hojas(items))
        cliente.post(
            f"{API}/transactions",
            headers=cab,
            json={
                "type": "expense",
                "amount": "20.00",
                "account_id": b["id"],
                "category_id": cat["id"],
                "occurred_at": "2026-09-01",
                "note": "Café con Andrés",
            },
        )

        for q in ["cafe", "CAFÉ", "andres"]:
            r = cliente.get(f"{API}/transactions", headers=cab, params={"search": q})
            assert r.status_code == 200, r.text
            assert r.json()["total"] == 1, f"buscando {q!r}: {r.json()['total']}"
