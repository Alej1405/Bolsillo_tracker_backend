"""Endpoints del CRUD de usuarios.

Dos grupos, separados por quien puede usarlos:
  · /users/me      cualquier usuario autenticado, sobre su propia cuenta
                   (nombre, contrasena, foto y baja)
  · /users/{id}    solo super_admin, sobre cualquier cuenta

Los dos borrados son distintos a proposito: el usuario se da de baja
(is_active = false, reversible) y el super_admin borra de verdad (cascada).
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_user_service, require_super_admin
from app.models.user import User
from app.schemas.user import (
    PasswordChange,
    UserAdminRead,
    UserListPage,
    UserRead,
    UserStatusUpdate,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


# ── la cuenta propia ─────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=UserRead,
    summary="Actualizar el perfil propio",
)
def update_me(
    datos: UserUpdate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    actualizado = service.update_profile(usuario, datos.full_name)
    db.commit()
    return actualizado


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambiar la contrasena propia",
)
def change_my_password(
    datos: PasswordChange,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    service.change_password(usuario, datos.current_password, datos.new_password)
    db.commit()


@router.post(
    "/me/avatar",
    response_model=UserRead,
    summary="Subir la foto de perfil",
)
def upload_my_avatar(
    archivo: UploadFile = File(..., description="Imagen JPG, PNG o WEBP"),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    #se lee un byte mas del tope para poder distinguir "justo en el limite" de
    #"se pasa", sin llegar a cargar en memoria un archivo enorme.
    tope = settings.avatar_max_mb * 1024 * 1024
    contenido = archivo.file.read(tope + 1)
    actualizado = service.save_avatar(usuario, contenido)
    db.commit()
    return actualizado


@router.delete(
    "/me/avatar",
    response_model=UserRead,
    summary="Quitar la foto de perfil",
)
def delete_my_avatar(
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    actualizado = service.remove_avatar(usuario)
    db.commit()
    return actualizado


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Darse de baja (baja logica)",
)
def deactivate_me(
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    service.deactivate_self(usuario)
    db.commit()


# ── administracion ───────────────────────────────────────────────────────

@router.get(
    "",
    response_model=UserListPage,
    summary="Listar usuarios (solo super_admin)",
)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    is_active: bool | None = Query(None, description="Sin este filtro vienen activos e inactivos"),
    q: str | None = Query(
        None,
        max_length=100,
        description="Busca en nombre y correo. Ignora tildes y mayusculas, y tolera erratas.",
    ),
    _admin: User = Depends(require_super_admin),
    service: UserService = Depends(get_user_service),
):
    return service.list_users(page, page_size, is_active, q)


@router.get(
    "/{user_id}",
    response_model=UserAdminRead,
    summary="Ver un usuario (solo super_admin)",
)
def get_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_super_admin),
    service: UserService = Depends(get_user_service),
):
    return service.get_user(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserAdminRead,
    summary="Activar o desactivar una cuenta (solo super_admin)",
)
def set_user_status(
    user_id: uuid.UUID,
    datos: UserStatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: UserService = Depends(get_user_service),
):
    actualizado = service.set_active(user_id, datos.is_active)
    db.commit()
    return actualizado


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar definitivamente, en cascada (solo super_admin)",
)
def delete_user(
    user_id: uuid.UUID,
    confirm: bool = Query(False, description="Obligatorio: confirm=true"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: UserService = Depends(get_user_service),
):
    service.delete_forever(user_id, confirm)
    db.commit()
