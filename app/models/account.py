'''modelos de cuentas es una de las partes importantes, se creara donde se guarda el dinero y a donde se va'''

import uuid
import enum

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Text, DateTime, text, func, ForeignKey, Column, Table, select
from sqlalchemy.dialects.postgresql import UUID, CITEXT, ENUM as PGEnum, CHAR, NUMERIC
from sqlalchemy.orm import Mapped, mapped_column, column_property
from app.core.database import Base

class AccountType(str, enum.Enum):
    CASH = "cash"
    BANK = "bank"
    CARD = "card"
    SAVINGS = "savings"

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    type: Mapped[AccountType] = mapped_column(
        PGEnum(
            AccountType,
            name="account_type",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    currency: Mapped[str] = mapped_column(
        CHAR(3), server_default="USD"
    )
    initial_balance: Mapped[Decimal] = mapped_column(
        NUMERIC(14,2), server_default=text("0"), 
    )
    icon: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    color: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


    def __repr__(self)->str:
        return f"<Account {self.name}>"

account_balances = Table(
    "account_balances", Base.metadata,
    Column("account_id", UUID(as_uuid=True), primary_key=True),
    Column("balance", NUMERIC(14, 2)),
)

Account.balance = column_property(
    select(account_balances.c.balance)
    .where(account_balances.c.account_id == Account.id)
    .scalar_subquery()
)