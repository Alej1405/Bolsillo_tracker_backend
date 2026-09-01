"""Estadisticas de la plataforma. Solo super_admin.

Un endpoint y una sola pregunta: como va Bolsillo. Todo lo que muestra el panel
de administracion sale de aqui, para que la pantalla no encadene peticiones.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_admin_service, require_super_admin
from app.models.user import User
from app.schemas.admin import AdminStatsResponse
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Estado de la plataforma (solo super_admin)",
)
def stats(
    _admin: User = Depends(require_super_admin),
    service: AdminService = Depends(get_admin_service),
):
    #sin commit: leer no modifica nada
    return service.estadisticas()
