"""Endpoints de soporte.

Tres grupos, separados por quien los usa:
  · POST /support/contact          cualquiera, sin sesion — el formulario de la web
  · /support/me                    quien tiene cuenta, sobre sus consultas
  · /support (y /support/{id}/...) solo super_admin, sobre todas
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_soporte_service, require_super_admin
from app.models.soporte import SupportStatus
from app.models.user import User
from app.schemas.soporte import (
    GuestThreadCreate,
    MessageCreate,
    ThreadAdminRead,
    ThreadCreate,
    ThreadListPage,
    ThreadRead,
)
from app.services.soporte_service import SoporteService

router = APIRouter(prefix="/support", tags=["support"])


# ── sin sesion: el formulario de la landing ──────────────────────────────

@router.post(
    "/contact",
    response_model=ThreadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Escribir desde el formulario de contacto (sin cuenta)",
)
def contact(
    datos: GuestThreadCreate,
    db: Session = Depends(get_db),
    service: SoporteService = Depends(get_soporte_service),
):
    hilo = service.abrir_como_invitado(datos.name, datos.email, datos.subject, datos.body)
    db.commit()
    return hilo


# ── la propia cuenta ─────────────────────────────────────────────────────

@router.get("/me", response_model=list[ThreadRead], summary="Mis consultas")
def mis_hilos(
    usuario: User = Depends(get_current_user),
    service: SoporteService = Depends(get_soporte_service),
):
    #sin commit: leer no modifica nada
    return service.mis_hilos(usuario)


@router.post(
    "/me",
    response_model=ThreadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir una consulta",
)
def abrir(
    datos: ThreadCreate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: SoporteService = Depends(get_soporte_service),
):
    hilo = service.abrir(usuario, datos.subject, datos.body)
    db.commit()
    return hilo


@router.get("/me/{thread_id}", response_model=ThreadRead, summary="Ver una consulta mia")
def ver_mi_hilo(
    thread_id: uuid.UUID,
    usuario: User = Depends(get_current_user),
    service: SoporteService = Depends(get_soporte_service),
):
    return service.ver(usuario, thread_id)


@router.post(
    "/me/{thread_id}/messages",
    response_model=ThreadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Responder en una consulta mia",
)
def responder(
    thread_id: uuid.UUID,
    datos: MessageCreate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
    service: SoporteService = Depends(get_soporte_service),
):
    hilo = service.responder(usuario, thread_id, datos.body)
    db.commit()
    return hilo


# ── administracion ───────────────────────────────────────────────────────

@router.get("", response_model=ThreadListPage, summary="Todas las consultas (solo super_admin)")
def listar(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    estado: SupportStatus | None = Query(None, alias="status"),
    _admin: User = Depends(require_super_admin),
    service: SoporteService = Depends(get_soporte_service),
):
    return service.listar(page, page_size, estado)


@router.get(
    "/{thread_id}",
    response_model=ThreadAdminRead,
    summary="Ver una consulta (solo super_admin)",
)
def ver(
    thread_id: uuid.UUID,
    _admin: User = Depends(require_super_admin),
    service: SoporteService = Depends(get_soporte_service),
):
    return service.ver_como_admin(thread_id)


@router.post(
    "/{thread_id}/reply",
    response_model=ThreadAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="Responder una consulta (solo super_admin)",
)
def responder_admin(
    thread_id: uuid.UUID,
    datos: MessageCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
    service: SoporteService = Depends(get_soporte_service),
):
    hilo = service.responder_como_admin(admin, thread_id, datos.body)
    db.commit()
    return hilo


@router.post(
    "/{thread_id}/close",
    response_model=ThreadAdminRead,
    summary="Cerrar una consulta (solo super_admin)",
)
def cerrar(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SoporteService = Depends(get_soporte_service),
):
    hilo = service.cerrar(thread_id)
    db.commit()
    return hilo


@router.post(
    "/{thread_id}/reopen",
    response_model=ThreadAdminRead,
    summary="Reabrir una consulta (solo super_admin)",
)
def reabrir(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SoporteService = Depends(get_soporte_service),
):
    hilo = service.reabrir(thread_id)
    db.commit()
    return hilo
