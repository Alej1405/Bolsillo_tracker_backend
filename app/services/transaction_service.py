"""Reglas de negocio de los movimientos.

Aqui viven las tres cosas que ni la base ni Pydantic pueden comprobar solas:
  1. que la cuenta y la categoria sean del usuario y esten activas
  2. que el kind de la categoria case con el tipo del movimiento
     (una categoria de egreso en un ingreso no tiene sentido)
  3. que la fecha no sea futura

El servicio nunca lanza HTTPException: lanza excepciones de dominio y el
handler las traduce.
"""

import math
import uuid
from datetime import date

from app.core.errors import BusinessRule, NotFound, ValidationError
from app.models.account import Account
from app.models.category import Category, CategoryKind
from app.models.transaction import Transaction, TransactionType
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransferCreate,
)

#que kind de categoria corresponde a cada tipo de movimiento
KIND_POR_TIPO = {
    TransactionType.INCOME: CategoryKind.INCOME,
    TransactionType.EXPENSE: CategoryKind.EXPENSE,
}


class TransactionService:
    def __init__(self, repo: TransactionRepository, cuentas: AccountRepository):
        self._repo = repo
        self._cuentas = cuentas

    # ---------- validaciones compartidas ----------

    def _cuenta_usable(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        cuenta = self._cuentas.get_by_id(user_id, account_id)
        if cuenta is None:
            raise NotFound("No se encontro la cuenta indicada")
        if cuenta.archived_at is not None:
            raise BusinessRule("No se puede mover dinero en una cuenta archivada")
        return cuenta

    def _categoria_usable(
        self, user_id: uuid.UUID, category_id: uuid.UUID, tipo: TransactionType
    ) -> Category:
        categoria = self._repo.find_visible_category(user_id, category_id)
        if categoria is None:
            raise NotFound("No se encontro la categoria indicada")
        if categoria.archived_at is not None:
            raise BusinessRule("Esa categoria esta archivada")

        esperado = KIND_POR_TIPO[tipo]
        if categoria.kind != esperado:
            raise BusinessRule(
                f"'{categoria.name}' es una categoria de "
                f"{'ingreso' if categoria.kind == CategoryKind.INCOME else 'egreso'}"
                f" y este movimiento es un "
                f"{'ingreso' if tipo == TransactionType.INCOME else 'egreso'}"
            )
        return categoria

    @staticmethod
    def _fecha_usable(cuando: date) -> date:
        if cuando > date.today():
            raise BusinessRule("La fecha del movimiento no puede ser futura")
        return cuando

    # ---------- lectura ----------

    def list_transactions(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        **filtros,
    ) -> dict:
        filas, total = self._repo.list_paginated(user_id, page, page_size, **filtros)
        return {
            "items": filas,
            "page": page,
            "page_size": page_size,
            "total": total,
            #ceil para que 51 resultados de 50 en 50 sean 2 paginas, no 1
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    def get_transaction(self, user_id: uuid.UUID, tx_id: uuid.UUID) -> Transaction:
        movimiento = self._repo.get_by_id(user_id, tx_id)
        if movimiento is None:
            raise NotFound("No se encontro el movimiento solicitado")
        return movimiento

    # ---------- escritura ----------

    def create_transaction(
        self, user_id: uuid.UUID, datos: TransactionCreate
    ) -> Transaction:
        """Un ingreso o un egreso. Las transferencias van por create_transfer."""
        self._cuenta_usable(user_id, datos.account_id)
        self._categoria_usable(user_id, datos.category_id, datos.type)
        self._fecha_usable(datos.occurred_at)

        return self._repo.create(
            user_id=user_id,
            type=datos.type,
            amount=datos.amount,
            account_id=datos.account_id,
            category_id=datos.category_id,
            occurred_at=datos.occurred_at,
            note=datos.note,
        )

    def create_transfer(self, user_id: uuid.UUID, datos: TransferCreate) -> Transaction:
        """Mover dinero entre dos cuentas propias.

        Ahorrar es esto, no un egreso: el dinero cambia de cuenta pero sigue
        siendo del usuario, y por eso no lleva categoria ni resta del neto.
        """
        if datos.from_account_id == datos.to_account_id:
            raise BusinessRule("El origen y el destino no pueden ser la misma cuenta")

        origen = self._cuenta_usable(user_id, datos.from_account_id)
        destino = self._cuenta_usable(user_id, datos.to_account_id)

        if origen.currency != destino.currency:
            raise BusinessRule("Las dos cuentas deben estar en la misma moneda")

        self._fecha_usable(datos.occurred_at)

        return self._repo.create(
            user_id=user_id,
            type=TransactionType.TRANSFER,
            amount=datos.amount,
            account_id=origen.id,
            counter_account_id=destino.id,
            occurred_at=datos.occurred_at,
            note=datos.note,
        )

    def update_transaction(
        self, user_id: uuid.UUID, tx_id: uuid.UUID, datos: TransactionUpdate
    ) -> Transaction:
        movimiento = self.get_transaction(user_id, tx_id)
        cambios = datos.model_dump(exclude_unset=True)

        if "account_id" in cambios:
            self._cuenta_usable(user_id, cambios["account_id"])

        if "category_id" in cambios:
            if movimiento.type == TransactionType.TRANSFER:
                #el CHECK de la base lo rechazaria igual, pero el mensaje seria ilegible
                raise ValidationError("Una transferencia no lleva categoria")
            if cambios["category_id"] is None:
                raise ValidationError("Un ingreso o egreso necesita categoria")
            self._categoria_usable(user_id, cambios["category_id"], movimiento.type)

        if "occurred_at" in cambios:
            self._fecha_usable(cambios["occurred_at"])

        return self._repo.update(movimiento, cambios)

    def delete_transaction(self, user_id: uuid.UUID, tx_id: uuid.UUID) -> None:
        """Borrado logico: desaparece de saldos y reportes, no del historial."""
        self._repo.soft_delete(self.get_transaction(user_id, tx_id))
