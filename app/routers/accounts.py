"""Endpoints de cuentas.

Todos exigen token: `usuario` sale de get_current_user y su `id` es lo unico
que se le pasa al servicio. El cliente nunca envia un user_id, asi que pedir
la cuenta de otro acaba en 404.

Dos formas de quitar una cuenta de en medio, a proposito:
  · POST /accounts/{id}/archive     la oculta y conserva su historial
  · DELETE /accounts/{id}           la borra, solo si no tiene movimientos

Y una para traerla de vuelta:
  · POST /accounts/{id}/unarchive   la saca del archivo
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_account_service, get_current_user
from app.models.user import User
from app.schemas.account import (
    AccountCreate,
    AccountListResponse,
    AccountRead,
    AccountUpdate,
)
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get(
    "",
    response_model=AccountListResponse,
    summary="Listar las cuentas del usuario con su saldo",
)
def list_accounts(
    include_archived: bool = Query(False, description="Incluir las cuentas archivadas"),
    usuario: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    #sin commit: leer no modifica nada
    return service.list_accounts(usuario.id, include_archived)


@router.post(
    "",
    response_model=AccountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una cuenta",
)
def create_account(
    datos: AccountCreate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    cuenta = service.create_account(usuario.id, datos)
    db.commit()
    return cuenta


@router.get(
    "/{account_id}",
    response_model=AccountRead,
    summary="Ver una cuenta",
)
def get_account(
    account_id: uuid.UUID,
    usuario: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    return service.get_account(usuario.id, account_id)


@router.patch(
    "/{account_id}",
    response_model=AccountRead,
    summary="Actualizar nombre, icono o color",
)
def update_account(
    account_id: uuid.UUID,
    datos: AccountUpdate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    cuenta = service.update_account(usuario.id, account_id, datos)
    db.commit()
    return cuenta


@router.post(
    "/{account_id}/archive",
    response_model=AccountRead,
    summary="Archivar una cuenta (conserva su historial)",
)
def archive_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    cuenta = service.archive_account(usuario.id, account_id)
    db.commit()
    return cuenta


@router.post(
    "/{account_id}/unarchive",
    response_model=AccountRead,
    summary="Desarchivar una cuenta (vuelve a contar en el patrimonio)",
)
def unarchive_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    cuenta = service.unarchive_account(usuario.id, account_id)
    db.commit()
    return cuenta


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar una cuenta sin movimientos",
)
def delete_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    #si la cuenta tiene transacciones, el servicio lanza AccountInUse -> 409 IN_USE
    service.delete_account(usuario.id, account_id)
    db.commit()
    #204: sin cuerpo, por eso no hay return
