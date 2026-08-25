"""reglas del crud para las cuentas de los usuarios"""

import math
import uuid
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.core.errors import NotFound, AccountNameTaken, AccountInUse
from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate, AccountUpdate

class AccountService:
    """reglas del negocio de las cuentas del usuario"""
    def __init__(self, repo: AccountRepository):
        self._repo = repo

    def list_accounts(self, user_id: uuid. UUID, include_archived: bool = False) -> dict:
        """las cuentas del usuario y el total, o se cuenta las archivadas"""
        cuentas = self._repo.list_by_user(user_id, include_archived)

        total = sum(
            (c.balance for c in cuentas if c.archived_at is None),
            Decimal("0.00"),
        )
        return {"items": cuentas, "total_balance": total}

    def get_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account :
        """Muestra las cuentas del usuario o lanza el Not Found"""
        cuenta = self._repo.get_by_id(user_id, account_id)
        if cuenta is None:
            raise NotFound("No se encontro la cuenta solicitada")
        return cuenta

    def create_account(self, user_id: uuid.UUID, datos: AccountCreate) -> Account:
        """Crea una cuenta para el usuario"""
        if self._repo.get_by_name(user_id, datos.name):
            raise AccountNameTaken("ya tienes una cuenta con ese nombre")

        return self._repo.create(
            user_id=user_id,
            name=datos.name,
            type=datos.type,
            initial_balance=datos.initial_balance,
            icon=datos.icon,
            color=datos.color,
        )

    def archive_account(self, user_id: uuid.UUID, account_id: uuid.UUID ) -> Account:
        """Oculta la cuenta sin borrar el historial"""
        return self._repo.archive(self.get_account(user_id, account_id))

    def update_account(self, user_id: uuid.UUID, account_id: uuid.UUID, datos:AccountUpdate) -> Account:
        cuenta = self.get_account(user_id, account_id)
        cambios = datos.model_dump(exclude_unset=True)

        nuevo_nombre = cambios.get("name")
        if nuevo_nombre and nuevo_nombre != cuenta.name:
            if self._repo.get_by_name(user_id, nuevo_nombre):
                raise AccountNameTaken("Ya tienes una cuenta con ese nombre")

        return self._repo.update(cuenta, cambios)

    def delete_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        cuenta = self.get_account(user_id, account_id)
        try:
            self._repo.delete(cuenta)
        except IntegrityError:
            raise AccountInUse("No se puede borrar una cuenta con movimiento, archivala en su lugar ")