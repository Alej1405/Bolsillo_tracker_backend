"""Reglas de los reportes: darle forma a lo que suma PostgreSQL.

Tres decisiones que se ven aqui y conviene poder explicar:

  1. `total_saved` NO se resta del neto. El dinero que se fue al fondo de
     ahorro sigue siendo del usuario; solo cambio de cuenta. Se informa aparte
     porque es util saberlo, no porque sea un gasto.
  2. `monthly` devuelve SIEMPRE 12 meses. Los vacios van en "0.00" para que el
     grafico del frontend no tenga que rellenar huecos.
  3. Los porcentajes se calculan aqui, no en el navegador.
"""

import calendar
import uuid
from datetime import date
from decimal import Decimal

from app.models.category import CategoryKind
from app.models.transaction import TransactionType
from app.repositories.account_repository import AccountRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.transaction_repository import TransactionRepository

CERO = Decimal("0.00")

TIPO_POR_KIND = {
    CategoryKind.INCOME: TransactionType.INCOME,
    CategoryKind.EXPENSE: TransactionType.EXPENSE,
}


def _porcentaje(parte: Decimal, total: Decimal) -> float:
    """Cuanto representa `parte` de `total`, en porcentaje con un decimal."""
    if not total:
        return 0.0
    return round(float(parte) / float(total) * 100, 1)


def _mes_completo(cuando: date) -> tuple[date, date]:
    """Primer y ultimo dia del mes de esa fecha (ojo con febrero)."""
    ultimo = calendar.monthrange(cuando.year, cuando.month)[1]
    return cuando.replace(day=1), cuando.replace(day=ultimo)


class ReportService:
    def __init__(
        self,
        repo: ReportRepository,
        movimientos: TransactionRepository,
        cuentas: AccountRepository,
    ):
        self._repo = repo
        self._movimientos = movimientos
        self._cuentas = cuentas

    # ---------- summary ----------

    def summary(
        self,
        user_id: uuid.UUID,
        desde: date,
        hasta: date,
        account_id: uuid.UUID | None = None,
    ) -> dict:
        fila = self._repo.summary(user_id, desde, hasta, account_id)
        ingresos = Decimal(fila.total_income)
        egresos = Decimal(fila.total_expense)

        return {
            "period": {"from": desde, "to": hasta},
            "total_income": ingresos,
            "total_expense": egresos,
            #puede ser negativo: gastar mas de lo que entra es un resultado valido
            "net": ingresos - egresos,
            "total_saved": Decimal(fila.total_saved),
            "transaction_count": fila.transaction_count,
        }

    # ---------- by-category ----------

    def by_category(
        self,
        user_id: uuid.UUID,
        desde: date,
        hasta: date,
        kind: CategoryKind = CategoryKind.EXPENSE,
    ) -> dict:
        filas = self._repo.by_category(user_id, desde, hasta, TIPO_POR_KIND[kind])
        total = sum((Decimal(f.amount) for f in filas), CERO)

        #se agrupa por padre: la clave es el padre si la fila es una hija, y
        #la propia categoria si no tiene padre
        grupos: dict[uuid.UUID, dict] = {}

        for f in filas:
            es_hija = f.padre_id is not None
            clave = f.padre_id if es_hija else f.cat_id

            if clave not in grupos:
                grupos[clave] = {
                    "category": {
                        "id": f.padre_id if es_hija else f.cat_id,
                        "name": f.padre_name if es_hija else f.cat_name,
                        "icon": f.padre_icon if es_hija else f.cat_icon,
                        "color": f.padre_color if es_hija else f.cat_color,
                    },
                    "amount": CERO,
                    "transaction_count": 0,
                    "children": [],
                }

            grupo = grupos[clave]
            #el monto del padre incluye el de sus hijas
            grupo["amount"] += Decimal(f.amount)
            grupo["transaction_count"] += f.transaction_count

            if es_hija:
                grupo["children"].append(
                    {
                        "category": {
                            "id": f.cat_id,
                            "name": f.cat_name,
                            "icon": f.cat_icon,
                            "color": f.cat_color,
                        },
                        "amount": Decimal(f.amount),
                        "percentage": _porcentaje(Decimal(f.amount), total),
                        "transaction_count": f.transaction_count,
                    }
                )

        items = sorted(grupos.values(), key=lambda g: g["amount"], reverse=True)
        for grupo in items:
            grupo["percentage"] = _porcentaje(grupo["amount"], total)
            grupo["children"].sort(key=lambda h: h["amount"], reverse=True)

        return {
            "period": {"from": desde, "to": hasta},
            "kind": kind,
            "total": total,
            "items": items,
        }

    # ---------- monthly ----------

    def monthly(self, user_id: uuid.UUID, year: int) -> dict:
        filas = {f.month: f for f in self._repo.monthly(user_id, year)}

        items = []
        for numero in range(1, 13):
            etiqueta = f"{year}-{numero:02d}"
            fila = filas.get(etiqueta)

            ingresos = Decimal(fila.income) if fila else CERO
            egresos = Decimal(fila.expense) if fila else CERO
            items.append(
                {
                    "month": etiqueta,
                    "income": ingresos,
                    "expense": egresos,
                    "net": ingresos - egresos,
                    "saved": Decimal(fila.saved) if fila else CERO,
                }
            )

        return {"year": year, "items": items}

    # ---------- dashboard ----------

    def dashboard(self, user_id: uuid.UUID) -> dict:
        """Toda la pantalla principal en una sola peticion."""
        hoy = date.today()
        desde, hasta = _mes_completo(hoy)

        resumen = self.summary(user_id, desde, hasta)
        por_categoria = self.by_category(user_id, desde, hasta, CategoryKind.EXPENSE)

        cuentas = self._cuentas.list_by_user(user_id, include_archived=False)
        patrimonio = sum((c.balance or CERO for c in cuentas), CERO)

        return {
            "current_month": f"{hoy.year}-{hoy.month:02d}",
            "total_balance": patrimonio,
            "summary": {
                "total_income": resumen["total_income"],
                "total_expense": resumen["total_expense"],
                "net": resumen["net"],
                "total_saved": resumen["total_saved"],
            },
            "accounts": cuentas,
            #las 5 categorias donde mas se fue la plata este mes
            "top_expense_categories": [
                {"category": item["category"], "amount": item["amount"], "percentage": item["percentage"]}
                for item in por_categoria["items"][:5]
            ],
            "recent_transactions": self._movimientos.recent(user_id, limit=5),
        }
