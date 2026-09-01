"""
Pruebas de integracion: la API entera, por HTTP, contra una base real.

Cada prueba recorre el camino completo —router, servicio, repositorio, base—
igual que lo haria el frontend. Es donde se ven los fallos que las unitarias
no pueden ver: una consulta mal armada, un permiso que falta, un saldo que no
se recalcula.
"""

import uuid

import pytest

from tests.conftest import requiere_bd

pytestmark = requiere_bd


API = "/api/v1"


def _registrar(cliente, correo: str | None = None, nombre: str = "Persona Prueba"):
    """Crea una cuenta y devuelve (cabeceras, cuerpo)."""
    correo = correo or f"{uuid.uuid4().hex[:12]}@ejemplo.com"
    r = cliente.post(
        f"{API}/auth/register",
        json={"full_name": nombre, "email": correo, "password": "clave-de-prueba-123"},
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    return {"Authorization": f"Bearer {cuerpo['access_token']}"}, cuerpo


def _bolsillo(cliente, cab, nombre="Efectivo", saldo="100.00"):
    r = cliente.post(
        f"{API}/accounts",
        headers=cab,
        json={"name": nombre, "type": "cash", "initial_balance": saldo},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _categoria_de(cliente, cab, tipo="expense"):
    r = cliente.get(f"{API}/categories", headers=cab)
    assert r.status_code == 200, r.text

    def hojas(items):
        for c in items:
            hijos = c.get("children") or []
            if hijos:
                yield from hojas(hijos)
            elif c.get("kind") == tipo:
                yield c

    cats = r.json()
    return next(hojas(cats.get("items", cats) if isinstance(cats, dict) else cats))


class TestAcceso:
    def test_sin_token_no_se_entra(self, cliente):
        assert cliente.get(f"{API}/accounts").status_code in (401, 403)

    def test_registrarse_y_entrar(self, cliente):
        correo = f"{uuid.uuid4().hex[:12]}@ejemplo.com"
        _, cuerpo = _registrar(cliente, correo)
        assert cuerpo["user"]["email"] == correo
        assert cuerpo["user"]["role"] == "client"

        r = cliente.post(
            f"{API}/auth/login", json={"email": correo, "password": "clave-de-prueba-123"}
        )
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_con_la_clave_mal_no_entra(self, cliente):
        correo = f"{uuid.uuid4().hex[:12]}@ejemplo.com"
        _registrar(cliente, correo)
        r = cliente.post(f"{API}/auth/login", json={"email": correo, "password": "otra"})
        assert r.status_code == 401

    def test_no_se_repite_el_correo(self, cliente):
        correo = f"{uuid.uuid4().hex[:12]}@ejemplo.com"
        _registrar(cliente, correo)
        r = cliente.post(
            f"{API}/auth/register",
            json={"full_name": "Otra", "email": correo, "password": "clave-de-prueba-123"},
        )
        assert r.status_code in (400, 409, 422)


class TestAislamientoEntreCuentas:
    def test_nadie_ve_los_bolsillos_de_otro(self, cliente):
        """
        La prueba que mas importa de todas: si esto falla, una persona ve el
        dinero de otra.
        """
        cab_a, _ = _registrar(cliente)
        cab_b, _ = _registrar(cliente)
        _bolsillo(cliente, cab_a, "Solo de A")

        de_b = cliente.get(f"{API}/accounts", headers=cab_b).json()["items"]
        assert all(b["name"] != "Solo de A" for b in de_b)

    def test_no_se_puede_leer_un_movimiento_ajeno(self, cliente):
        cab_a, _ = _registrar(cliente)
        cab_b, _ = _registrar(cliente)
        b = _bolsillo(cliente, cab_a)
        cat = _categoria_de(cliente, cab_a)
        r = cliente.post(
            f"{API}/transactions",
            headers=cab_a,
            json={
                "type": "expense",
                "amount": "10.00",
                "account_id": b["id"],
                "category_id": cat["id"],
                "occurred_at": "2026-09-01",
            },
        )
        tx = r.json()["id"]
        assert cliente.get(f"{API}/transactions/{tx}", headers=cab_b).status_code == 404


class TestMovimientosYSaldo:
    def test_un_gasto_baja_el_saldo(self, cliente):
        cab, _ = _registrar(cliente)
        b = _bolsillo(cliente, cab, saldo="100.00")
        cat = _categoria_de(cliente, cab)

        cliente.post(
            f"{API}/transactions",
            headers=cab,
            json={
                "type": "expense",
                "amount": "30.00",
                "account_id": b["id"],
                "category_id": cat["id"],
                "occurred_at": "2026-09-01",
            },
        )
        saldo = cliente.get(f"{API}/accounts", headers=cab).json()["total_balance"]
        assert float(saldo) == 70.0

    def test_borrar_es_logico_y_devuelve_el_saldo(self, cliente):
        """
        El borrado marca `deleted_at` y saca el movimiento de saldos, historial
        y reportes. Es lo que sostiene el "deshacer" del frontend.
        """
        cab, _ = _registrar(cliente)
        b = _bolsillo(cliente, cab, saldo="100.00")
        cat = _categoria_de(cliente, cab)

        tx = cliente.post(
            f"{API}/transactions",
            headers=cab,
            json={
                "type": "expense",
                "amount": "25.00",
                "account_id": b["id"],
                "category_id": cat["id"],
                "occurred_at": "2026-09-01",
            },
        ).json()["id"]

        assert float(cliente.get(f"{API}/accounts", headers=cab).json()["total_balance"]) == 75.0

        assert cliente.delete(f"{API}/transactions/{tx}", headers=cab).status_code == 204

        assert float(cliente.get(f"{API}/accounts", headers=cab).json()["total_balance"]) == 100.0
        assert cliente.get(f"{API}/transactions/{tx}", headers=cab).status_code == 404
        listado = cliente.get(f"{API}/transactions", headers=cab).json()
        assert all(i["id"] != tx for i in listado["items"])

    def test_editar_recalcula_el_saldo(self, cliente):
        cab, _ = _registrar(cliente)
        b = _bolsillo(cliente, cab, saldo="100.00")
        cat = _categoria_de(cliente, cab)
        tx = cliente.post(
            f"{API}/transactions",
            headers=cab,
            json={
                "type": "expense",
                "amount": "40.00",
                "account_id": b["id"],
                "category_id": cat["id"],
                "occurred_at": "2026-09-01",
            },
        ).json()["id"]

        r = cliente.patch(f"{API}/transactions/{tx}", headers=cab, json={"amount": "10.00"})
        assert r.status_code == 200
        assert float(cliente.get(f"{API}/accounts", headers=cab).json()["total_balance"]) == 90.0

    def test_una_transferencia_no_cambia_el_patrimonio(self, cliente):
        """Mover plata entre bolsillos propios no crea ni destruye dinero."""
        cab, _ = _registrar(cliente)
        origen = _bolsillo(cliente, cab, "Efectivo", "200.00")
        destino = _bolsillo(cliente, cab, "Ahorro", "0.00")

        antes = float(cliente.get(f"{API}/accounts", headers=cab).json()["total_balance"])
        r = cliente.post(
            f"{API}/transfers",
            headers=cab,
            json={
                "amount": "50.00",
                "from_account_id": origen["id"],
                "to_account_id": destino["id"],
                "occurred_at": "2026-09-01",
            },
        )
        assert r.status_code == 201, r.text
        despues = float(cliente.get(f"{API}/accounts", headers=cab).json()["total_balance"])
        assert antes == despues


class TestPermisosDeAdmin:
    def test_un_cliente_no_lista_usuarios(self, cliente):
        cab, _ = _registrar(cliente)
        assert cliente.get(f"{API}/users", headers=cab).status_code in (401, 403)

    def test_un_cliente_no_ve_las_estadisticas(self, cliente):
        cab, _ = _registrar(cliente)
        assert cliente.get(f"{API}/admin/stats", headers=cab).status_code in (401, 403)
