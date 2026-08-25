import uuid
from decimal import Decimal
from sqlalchemy import func, select

#importando atributos de sql
from sqlalchemy.orm import Session
from app.models.account import Account, AccountType

#clase account gestion integral de las cuentas
class AccountRepository:
    def __init__(self, db: Session):
        self._db = db

    def list_by_user(self, user_id: uuid.UUID, include_archived: bool=False) -> list[Account]:
        #filtro para saber de quien son las cuentas
        filtros = [Account.user_id == user_id]

        #condicion que puede agregar filtros segun el usuario pida
        if not include_archived:
            filtros.append(Account.archived_at.is_(None))

        #la consulta con el query
        stmt = (
            select(Account)
            .where(*filtros)
            .order_by(Account.name)
        )

        #ejecutar el query
        return list(self._db.scalars(stmt).all())

    def get_by_id(self, user_id: uuid.UUID,  account_id: uuid.UUID) -> Account | None:
        stmt = (
            select(Account).where(Account.id == account_id, Account.user_id == user_id)
        )
        return self._db.scalars(stmt).first()

    def get_by_name(self, user_id: uuid.UUID,  name: str) -> Account | None:
        stmt = select(Account).where(Account.user_id == user_id, Account.name == name)
        return self._db.scalars(stmt).first()

    def create(self, user_id: uuid.UUID, name: str, type: AccountType, initial_balance: Decimal, icon: str | None, color: str | None ) -> Account:
        account = Account(
            user_id = user_id,
            name = name,
            type = type,
            initial_balance = initial_balance,
            icon = icon,
            color = color,
        )
        self._db.add(account)
        self._db.flush()
        return account

    def update(self, cuenta: Account, cambios: dict) -> Account:
        for campo, valor in cambios.items():
            setattr(cuenta, campo, valor)
        self._db.flush()
        return cuenta

    def archive(self, cuenta: Account) -> Account:
        cuenta.archived_at = func.now()
        self._db.flush()
        return cuenta

    def delete(self, cuenta: Account) -> None:
        self._db.delete(cuenta)
        self._db.flush()
