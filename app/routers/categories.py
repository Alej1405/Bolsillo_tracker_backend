"""Endpoints de categorias.

GET devuelve el arbol completo, sin paginar: son pocas y el frontend las
necesita todas para llenar un <select>.

DELETE aqui ARCHIVA (a diferencia de /accounts, donde borra de verdad). Una
categoria siempre tiene historial detras: borrarla dejaria movimientos sin
clasificar.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_category_service, get_current_user
from app.models.category import CategoryKind
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryRead,
    CategoryTreeResponse,
    CategoryUpdate,
)
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get(
    "",
    response_model=CategoryTreeResponse,
    summary="El arbol de categorias: las propias y las del sistema",
)
def list_categories(
    kind: CategoryKind | None = Query(None, description="Filtrar por ingreso o egreso"),
    include_archived: bool = Query(False),
    usuario: User = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    return service.list_tree(usuario.id, kind, include_archived)


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una categoria propia (padre o subcategoria)",
)
def create_category(
    datos: CategoryCreate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    categoria = service.create_category(usuario.id, datos)
    db.commit()
    return categoria


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Actualizar nombre, icono o color",
)
def update_category(
    category_id: uuid.UUID,
    datos: CategoryUpdate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    #si es del sistema, el servicio lanza SystemCategoryReadOnly -> 403
    categoria = service.update_category(usuario.id, category_id, datos)
    db.commit()
    return categoria


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archivar una categoria",
)
def archive_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: CategoryService = Depends(get_category_service),
):
    #con movimientos detras responde 409 IN_USE
    service.archive_category(usuario.id, category_id)
    db.commit()
