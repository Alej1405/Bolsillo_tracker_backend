"""Schemas de transacciones y transferencias.

La respuesta anida la cuenta y la categoria como OBJETOS, no como ids sueltos:
asi el frontend pinta la fila con lo que ya recibio, sin una peticion por fila.
Es lo que exige 03-contrato-api.md.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.account import AccountType
from app.models.category import CategoryKind
from app.models.transaction import TransactionType


# --- piezas anidadas (solo lectura) ---

class AccountMini(BaseModel):
    """La cuenta como la ve una fila del listado: lo justo para pintarla."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: AccountType
    icon: str | None = None


class CategoryParentMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class CategoryMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: CategoryKind
    icon: str | None = None
    color: str | None = None
    #si la categoria es hija, viene su padre; si es padre, es null
    parent: CategoryParentMini | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: TransactionType
    amount: Decimal
    currency: str
    occurred_at: date
    note: str | None = None
    account: AccountMini
    counter_account: AccountMini | None = None
    category: CategoryMini | None = None
    created_at: datetime
    updated_at: datetime


class TransactionListPage(BaseModel):
    items: list[TransactionRead]
    page: int
    page_size: int
    total: int
    total_pages: int


# --- entrada ---

class TransactionCreate(BaseModel):
    """Solo ingresos y egresos. Las transferencias van por POST /transfers."""

    type: TransactionType
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    account_id: uuid.UUID
    category_id: uuid.UUID
    occurred_at: date
    note: str | None = Field(default=None, max_length=500)

    @field_validator("type")
    @classmethod
    def no_transferencias(cls, valor: TransactionType) -> TransactionType:
        #el contrato lo pide explicito: transfer aqui es un error del cliente
        if valor is TransactionType.TRANSFER:
            raise ValueError("Las transferencias se crean en POST /transfers")
        return valor


class TransactionUpdate(BaseModel):
    """PATCH parcial. El `type` no esta: un egreso no se vuelve transferencia."""

    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    occurred_at: date | None = None
    note: str | None = Field(default=None, max_length=500)


class TransferCreate(BaseModel):
    """Mover dinero entre dos cuentas propias. Sin categoria: no es un gasto."""

    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    occurred_at: date
    note: str | None = Field(default=None, max_length=500)
