"""Endpoints de reportes. Solo lectura: ninguno hace commit.

/reports/dashboard existe para que la pantalla principal se pinte con UNA
peticion en vez de cinco.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_report_service
from app.models.category import CategoryKind
from app.models.user import User
from app.schemas.report import (
    PerformanceResponse,
    ByCategoryResponse,
    DashboardResponse,
    MonthlyResponse,
    SummaryResponse,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Ingresos, egresos, neto y ahorrado de un periodo",
)
def summary(
    desde: date = Query(alias="from", description="Fecha inicial inclusive"),
    hasta: date = Query(alias="to", description="Fecha final inclusive"),
    account_id: uuid.UUID | None = Query(None),
    usuario: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return service.summary(usuario.id, desde, hasta, account_id)


@router.get(
    "/by-category",
    response_model=ByCategoryResponse,
    summary="En que se fue la plata, agrupado por categoria padre",
)
def by_category(
    desde: date = Query(alias="from"),
    hasta: date = Query(alias="to"),
    kind: CategoryKind = Query(CategoryKind.EXPENSE),
    usuario: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return service.by_category(usuario.id, desde, hasta, kind)


@router.get(
    "/monthly",
    response_model=MonthlyResponse,
    summary="Evolucion mes a mes (siempre los 12 meses)",
)
def monthly(
    year: int = Query(default_factory=lambda: date.today().year, ge=2000, le=2100),
    usuario: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return service.monthly(usuario.id, year)


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Todo lo de la pantalla principal en una peticion",
)
def dashboard(
    usuario: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    return service.dashboard(usuario.id)


@router.get(
    "/performance",
    response_model=PerformanceResponse,
    summary="Como va tu dinero: cinco medidas, cada una explicada en una frase",
)
def performance(
    desde: date = Query(alias="from", description="Fecha inicial inclusive"),
    hasta: date = Query(alias="to", description="Fecha final inclusive"),
    usuario: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    """Rendimiento y ahorro, en lengua de todos los dias.

    Devuelve dos cifras y una lista de medidas. Cada medida trae su `reading`:
    la misma informacion dicha de forma que no haga falta saber finanzas para
    entenderla.

    La diferencia con `/summary`: `total_saved` de alli cuenta solo lo que se
    transfirio a una cuenta de tipo ahorro. Aqui `net_worth` es todo lo que la
    persona tiene junto —efectivo, banco, lo que sea—, que es lo que cualquiera
    llama "mi ahorro".
    """
    return service.performance(usuario.id, desde, hasta)
