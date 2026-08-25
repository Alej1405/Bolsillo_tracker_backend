"""Endpoints de movimientos y transferencias.

Dos routers en un archivo porque comparten servicio:
  · /transactions  ingresos y egresos
  · /transfers     mover dinero entre cuentas propias

El endpoint separado no es capricho: una transferencia no tiene categoria y
tiene dos cuentas, asi que su request es de otra forma. Mezclarlas obligaria
a validar "si es esto entonces aquello" en cada campo.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_transaction_service
from app.models.transaction import TransactionType
from app.models.user import User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionListPage,
    TransactionRead,
    TransactionUpdate,
    TransferCreate,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])
transfers_router = APIRouter(prefix="/transfers", tags=["transactions"])


@router.get(
    "",
    response_model=TransactionListPage,
    summary="Listar movimientos con filtros y paginacion",
)
def list_transactions(
    #"from" es palabra reservada en Python: el alias deja el nombre del contrato
    desde: date | None = Query(None, alias="from", description="Fecha inicial inclusive"),
    hasta: date | None = Query(None, alias="to", description="Fecha final inclusive"),
    tipos: list[TransactionType] | None = Query(None, alias="type"),
    account_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None, description="Si es padre, incluye sus hijas"),
    search: str | None = Query(None, description="Busca en la nota"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    usuario: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    return service.list_transactions(
        usuario.id,
        page=page,
        page_size=page_size,
        desde=desde,
        hasta=hasta,
        tipos=tipos,
        account_id=account_id,
        category_id=category_id,
        search=search,
    )


@router.post(
    "",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un ingreso o un egreso",
)
def create_transaction(
    datos: TransactionCreate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    movimiento = service.create_transaction(usuario.id, datos)
    db.commit()
    return movimiento


@router.get(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Ver un movimiento",
)
def get_transaction(
    transaction_id: uuid.UUID,
    usuario: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    return service.get_transaction(usuario.id, transaction_id)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Editar un movimiento (el tipo no se cambia)",
)
def update_transaction(
    transaction_id: uuid.UUID,
    datos: TransactionUpdate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    movimiento = service.update_transaction(usuario.id, transaction_id, datos)
    db.commit()
    return movimiento


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un movimiento (borrado logico)",
)
def delete_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    service.delete_transaction(usuario.id, transaction_id)
    db.commit()


@transfers_router.post(
    "",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Mover dinero entre dos cuentas propias",
)
def create_transfer(
    datos: TransferCreate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: TransactionService = Depends(get_transaction_service),
):
    #aqui se alimenta el fondo de ahorro: no es un gasto, es un cambio de cuenta
    movimiento = service.create_transfer(usuario.id, datos)
    db.commit()
    return movimiento
