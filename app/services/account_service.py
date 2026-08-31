"""reglas del crud para las cuentas de los usuarios"""

import math
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.core.errors import NotFound, AccountNameTaken, AccountInUse
from app.models.account import Account
from app.models.category import CategoryKind
from app.models.transaction import TransactionType
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.account import AccountCreate, AccountUpdate

#Nombre de la categoria del sistema donde caen los saldos de apertura, y el
#texto de la nota. Estan aqui y no repartidos por el codigo porque la migracion
#de db/07_saldo_apertura.sql usa exactamente los mismos.
CATEGORIA_APERTURA = "Saldo inicial"
NOTA_APERTURA = "Saldo con el que abriste este bolsillo"


class AccountService:
    """reglas del negocio de las cuentas del usuario"""
    def __init__(self, repo: AccountRepository, movimientos: TransactionRepository):
        self._repo = repo
        self._movimientos = movimientos

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
        """Crea una cuenta para el usuario.

        Si se abre con saldo, ese saldo entra como un ingreso de verdad: una
        fila en transactions, no solo un numero en la cuenta. Antes se guardaba
        aparte y los reportes decian "entro 0" mientras el bolsillo mostraba su
        dinero, porque los ingresos se leen de los movimientos.

        Abrir en cero no registra nada: no hay ningun dinero que contar.
        """
        if self._repo.get_by_name(user_id, datos.name):
            raise AccountNameTaken("ya tienes una cuenta con ese nombre")

        cuenta = self._repo.create(
            user_id=user_id,
            name=datos.name,
            type=datos.type,
            initial_balance=datos.initial_balance,
            icon=datos.icon,
            color=datos.color,
        )

        if datos.initial_balance > 0:
            self._registrar_apertura(cuenta)

        return cuenta

    def _registrar_apertura(self, cuenta: Account) -> None:
        """El ingreso que deja el saldo con el que se abre un bolsillo.

        La fecha es hoy porque el bolsillo se abre hoy. La categoria es del
        sistema y se busca por nombre: un ingreso sin categoria no lo acepta la
        tabla, y elegirla no es decision del usuario en este caso.
        """
        categoria = self._movimientos.find_system_category(
            CATEGORIA_APERTURA, CategoryKind.INCOME
        )
        #Sin la categoria del sistema no hay donde poner el movimiento. Se avisa
        #en vez de fallar con un error de base incomprensible: falta correr
        #db/07_saldo_apertura.sql en esta base.
        if categoria is None:
            raise NotFound(
                f"Falta la categoria del sistema «{CATEGORIA_APERTURA}»"
            )

        self._movimientos.create(
            user_id=cuenta.user_id,
            type=TransactionType.INCOME,
            amount=cuenta.initial_balance,
            account_id=cuenta.id,
            category_id=categoria.id,
            occurred_at=date.today(),
            note=NOTA_APERTURA,
        )

    def archive_account(self, user_id: uuid.UUID, account_id: uuid.UUID ) -> Account:
        """Oculta la cuenta sin borrar el historial"""
        return self._repo.archive(self.get_account(user_id, account_id))

    def unarchive_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        """Saca la cuenta del archivo y la vuelve a contar en el patrimonio.

        No hay nada que validar antes: archivar no destruye nada, asi que
        deshacerlo tampoco puede chocar con nada. Si el nombre se repitiera
        con otra cuenta creada mientras estaba archivada, el UNIQUE de la
        tabla lo impide y sube como IntegrityError.
        """
        return self._repo.unarchive(self.get_account(user_id, account_id))

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