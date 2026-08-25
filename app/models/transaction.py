"""Modelo de transacciones: cada movimiento de dinero del usuario.

Tres tipos en una sola tabla, con formas distintas que la base ya vigila:
  · income / expense -> llevan category_id y NO llevan counter_account_id
  · transfer         -> lleva counter_account_id y NO lleva category_id

Esos dos CHECK (ck_tx_flow_shape y ck_tx_transfer_shape) viven en
db/05_transactions.sql. Aqui no se repiten: si el servicio se equivoca, la
base rechaza el INSERT.

El borrado es logico (deleted_at). La vista account_balances ya ignora las
filas borradas, asi que un movimiento eliminado deja de contar en el saldo
sin desaparecer del historial.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import CHAR, ENUM as PGEnum, NUMERIC, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.account import Account
from app.models.category import Category


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[TransactionType] = mapped_column(
        PGEnum(
            TransactionType,
            name="transaction_type",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(NUMERIC(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="USD")

    #cuenta de origen. En un ingreso es la cuenta que recibe el dinero
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    #solo en transferencias: la cuenta que recibe
    counter_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )

    #fecha del movimiento (la pone el usuario), distinta de created_at
    occurred_at: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #borrado logico: la fila se queda, deja de contar
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #Hay DOS caminos de transactions a accounts, asi que SQLAlchemy no puede
    #adivinar cual usa cada relacion: foreign_keys se lo dice.
    #lazy="joined" trae la cuenta y la categoria en la MISMA consulta; sin eso
    #el listado dispararia una consulta por fila (N+1).
    account: Mapped[Account] = relationship(
        foreign_keys=[account_id], lazy="joined"
    )
    counter_account: Mapped[Account | None] = relationship(
        foreign_keys=[counter_account_id], lazy="joined"
    )
    #la categoria trae ademas su padre, porque el contrato lo anida
    category: Mapped[Category | None] = relationship(
        foreign_keys=[category_id], lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<Transaction {self.type.value} {self.amount}>"
