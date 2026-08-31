"""Schemas de los reportes.

Todos son de SALIDA: el frontend recibe el numero ya calculado y solo lo
formatea. Los montos son Decimal (Pydantic los serializa como string, sin
perder centavos) y los porcentajes son float, porque un porcentaje no es
dinero y no necesita precision exacta.
"""

import uuid
from datetime import date
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.account import AccountType
from app.models.category import CategoryKind
from app.schemas.transaction import TransactionRead


class Period(BaseModel):
    #"from" es palabra reservada en Python: el atributo se llama distinto y
    #el alias hace que el JSON salga como pide el contrato
    desde: date = Field(alias="from")
    hasta: date = Field(alias="to")

    model_config = ConfigDict(populate_by_name=True)


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    icon: str | None = None
    color: str | None = None


# --- GET /reports/summary ---

class SummaryTotals(BaseModel):
    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    total_saved: Decimal


class SummaryResponse(SummaryTotals):
    period: Period
    transaction_count: int


# --- GET /reports/by-category ---

class CategoryReportChild(BaseModel):
    category: CategoryBrief
    amount: Decimal
    percentage: float
    transaction_count: int


class CategoryReportItem(CategoryReportChild):
    children: list[CategoryReportChild] = []


class ByCategoryResponse(BaseModel):
    period: Period
    kind: CategoryKind
    total: Decimal
    items: list[CategoryReportItem]


# --- GET /reports/monthly ---

class MonthlyItem(BaseModel):
    month: str
    income: Decimal
    expense: Decimal
    net: Decimal
    saved: Decimal


class MonthlyResponse(BaseModel):
    year: int
    items: list[MonthlyItem]


# --- GET /reports/dashboard ---

class DashboardAccount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: AccountType
    balance: Decimal
    icon: str | None = None


class DashboardCategory(BaseModel):
    category: CategoryBrief
    amount: Decimal
    percentage: float


class DashboardResponse(BaseModel):
    current_month: str
    total_balance: Decimal
    summary: SummaryTotals
    accounts: list[DashboardAccount]
    top_expense_categories: list[DashboardCategory]
    recent_transactions: list[TransactionRead]


# ── Rendimiento ──────────────────────────────────────────────────────────


class Metric(BaseModel):
    """Una medida, con todo lo necesario para pintarla sin saber que significa.

    `reading` es la parte importante: la frase en lengua de todos los dias.
    Un numero suelto —23,4%— no le dice nada a quien nunca vio el termino
    "tasa de ahorro"; "de cada $100 que te entran, guardas $23" si.

    `level` traduce el numero a bien / atencion / mal para que la interfaz
    elija un color sin tener que interpretar cada indicador por su cuenta.
    """

    key: str
    label: str
    value: Decimal | float
    unit: str
    reading: str
    level: Literal["bien", "atencion", "mal"]


class PerformanceResponse(BaseModel):
    period: Period
    #: Lo que entro menos lo que salio en el rango. El ahorro del periodo.
    saved_in_period: Decimal
    #: La suma de todos los bolsillos activos. Lo que se tiene, aqui y ahora.
    net_worth: Decimal
    metrics: list[Metric]
