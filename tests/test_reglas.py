"""
Pruebas unitarias: las reglas que protegen los datos.

No tocan la base ni la red. Prueban el contrato de entrada —lo que la API
acepta y lo que rechaza— que es la primera linea de defensa: si un dato
invalido pasa de aqui, ya esta dentro del sistema.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.transaction import TransactionCreate, TransactionUpdate, TransferCreate


def _base(**extra):
    """Un movimiento valido al que cada prueba le cambia una cosa."""
    datos = {
        "type": "expense",
        "amount": Decimal("12.75"),
        "account_id": uuid.uuid4(),
        "category_id": uuid.uuid4(),
        "occurred_at": date(2026, 9, 1),
    }
    datos.update(extra)
    return datos


class TestCrearMovimiento:
    def test_un_gasto_normal_se_acepta(self):
        m = TransactionCreate(**_base())
        assert m.amount == Decimal("12.75")
        assert m.type.value == "expense"

    def test_una_transferencia_no_se_crea_por_aqui(self):
        """
        Tiene su propio endpoint. Mezclarlas aqui permitiria registrar un
        movimiento entre bolsillos sin cuenta de destino, y ese movimiento
        restaria de un lado sin sumar al otro: dinero que desaparece.
        """
        with pytest.raises(ValidationError) as e:
            TransactionCreate(**_base(type="transfer"))
        assert "transfer" in str(e.value).lower()

    @pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-1"), Decimal("-0.01")])
    def test_el_monto_tiene_que_ser_positivo(self, monto):
        """
        El signo lo pone el TIPO, no el numero. Un gasto de -50 seria un gasto
        que suma, y ninguna pantalla lo mostraria como tal.
        """
        with pytest.raises(ValidationError):
            TransactionCreate(**_base(amount=monto))

    def test_no_se_admiten_mas_de_dos_decimales(self):
        """La plata tiene centavos, no milesimas."""
        with pytest.raises(ValidationError):
            TransactionCreate(**_base(amount=Decimal("10.999")))

    def test_la_nota_tiene_tope(self):
        with pytest.raises(ValidationError):
            TransactionCreate(**_base(note="x" * 501))

    def test_la_nota_es_opcional(self):
        assert TransactionCreate(**_base()).note is None


class TestEditarMovimiento:
    def test_el_tipo_no_esta_entre_lo_editable(self):
        """
        Un gasto no se convierte en ingreso editandolo: cambiaria el signo de
        un movimiento ya contado en saldos y reportes. Se borra y se anota de
        nuevo. El frontend lo dice con todas las letras en el formulario.
        """
        assert "type" not in TransactionUpdate.model_fields

    def test_es_parcial_de_verdad(self):
        """Mandar solo el monto no debe exigir el resto de campos."""
        u = TransactionUpdate(amount=Decimal("5.50"))
        assert u.amount == Decimal("5.50")
        assert u.account_id is None
        assert u.occurred_at is None

    def test_no_deja_poner_un_monto_invalido(self):
        with pytest.raises(ValidationError):
            TransactionUpdate(amount=Decimal("0"))


class TestTransferencia:
    def test_necesita_origen_y_destino(self):
        t = TransferCreate(
            amount=Decimal("100"),
            from_account_id=uuid.uuid4(),
            to_account_id=uuid.uuid4(),
            occurred_at=date(2026, 9, 1),
        )
        assert t.from_account_id != t.to_account_id

    def test_no_lleva_categoria(self):
        """Mover plata de un bolsillo propio a otro no es un gasto."""
        assert "category_id" not in TransferCreate.model_fields
