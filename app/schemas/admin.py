"""Lo que devuelve /admin/stats.

Nombres en ingles como el resto del contrato. Los numeros son enteros salvo el
dinero, que viaja como Decimal por lo de siempre: el punto flotante redondea mal
los centavos.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AdminUsers(BaseModel):
    total: int
    active: int
    inactive: int
    new_last_7_days: int
    new_last_30_days: int
    #: Cuantos registraron algun movimiento en los ultimos 30 dias.
    active_last_30_days: int


class AdminActivity(BaseModel):
    transactions: int
    transactions_last_30_days: int
    accounts: int
    custom_categories: int


class AdminMonth(BaseModel):
    #"from" es palabra reservada en Python: mismo patron que Period en los
    #reportes —el atributo se llama distinto y el alias da la clave del JSON.
    desde: date = Field(alias="from")
    hasta: date = Field(alias="to")
    income: Decimal
    expense: Decimal

    model_config = ConfigDict(populate_by_name=True)


class AdminTopCategory(BaseModel):
    name: str
    count: int


class AdminStatsResponse(BaseModel):
    users: AdminUsers
    activity: AdminActivity
    this_month: AdminMonth
    top_expense_categories: list[AdminTopCategory]
