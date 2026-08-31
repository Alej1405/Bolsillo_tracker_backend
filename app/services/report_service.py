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
from datetime import date, timedelta
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


def _plata(monto: Decimal) -> str:
    """Un monto como se lee en voz alta: $1.248,50.

    Miles con punto y decimales con coma, que es como se escribe en Ecuador.
    El backend guarda con punto decimal; esto es solo para las frases.
    """
    entero, decimales = f"{abs(monto):.2f}".split(".")
    grupos = [entero[max(i - 3, 0):i] for i in range(len(entero), 0, -3)][::-1]
    return f"${'.'.join(grupos)},{decimales}"


def _meses(cantidad: float) -> str:
    """'2,5 meses' o 'un mes', sin decimales cuando es redondo."""
    if cantidad == 1:
        return "un mes"
    texto = f"{cantidad:.1f}".replace(".0", "").replace(".", ",")
    return f"{texto} meses"


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

    # ── Rendimiento ──────────────────────────────────────────────────────

    def performance(self, user_id: uuid.UUID, desde: date, hasta: date) -> dict:
        """Cinco medidas de como va el dinero, cada una con su frase.

        La regla de esta pantalla: **el numero solo no sirve**. Una tasa de
        ahorro del 23% no le dice nada a quien nunca vio ese termino, asi que
        cada medida viaja con una `lectura` escrita en la lengua de todos los
        dias: "de cada 100 que te entran, guardas 23". Un nino de diez anos y
        una persona de ochenta tienen que entender la frase sin ayuda.

        Por eso tambien `nivel`: bien / atencion / mal. Es lo que permite que
        la pantalla pinte un color sin tener que saber que significa cada
        indicador.
        """
        rango = self._repo.totales_del_rango(user_id, desde, hasta)
        entro = Decimal(rango.income)
        salio = Decimal(rango.expense)
        guardado = entro - salio

        tengo = self._repo.patrimonio(user_id)
        gasto_normal = self._repo.gasto_medio_mensual(user_id)

        dias = max((hasta - desde).days + 1, 1)
        por_dia = (salio / dias).quantize(Decimal("0.01"))

        # Mismo numero de dias hacia atras, para comparar peras con peras.
        antes_hasta = desde - timedelta(days=1)
        antes_desde = antes_hasta - timedelta(days=dias - 1)
        antes = self._repo.totales_del_rango(user_id, antes_desde, antes_hasta)
        guardado_antes = Decimal(antes.income) - Decimal(antes.expense)
        cambio = guardado - guardado_antes

        return {
            "period": {"from": desde, "to": hasta},
            "saved_in_period": guardado,
            "net_worth": tengo,
            "metrics": [
                self._cuanto_tengo(tengo),
                self._cuanto_guarde(guardado, entro),
                self._de_cada_cien(guardado, entro),
                self._cuanto_aguanta(tengo, gasto_normal),
                self._gasto_diario(por_dia),
                self._comparado_con_antes(cambio, guardado_antes),
            ],
        }

    def _cuanto_tengo(self, tengo: Decimal) -> dict:
        """Lo que la persona llama 'mi ahorro': todo lo que tiene junto.

        No son solo las cuentas de tipo ahorro. Quien guarda su plata en el
        efectivo y en el banco tiene ahorro igual, y `total_saved` le decia
        que cero.
        """
        return {
            "key": "cuanto_tengo",
            "label": "Cuánto tienes guardado",
            "value": tengo,
            "unit": "USD",
            "reading": (
                f"Sumando todos tus bolsillos —el efectivo, el banco, todo— "
                f"tienes {_plata(tengo)}."
            ),
            "level": "bien" if tengo > 0 else "atencion",
        }

    def _cuanto_guarde(self, guardado: Decimal, entro: Decimal) -> dict:
        if entro == CERO and guardado == CERO:
            lectura = "Todavía no hay movimientos en estas fechas."
            nivel = "atencion"
        elif guardado >= CERO:
            lectura = f"Te quedaron {_plata(guardado)} sin gastar."
            nivel = "bien"
        else:
            lectura = (
                f"Gastaste {_plata(-guardado)} más de lo que te entró. "
                f"Saliste de lo que ya tenías guardado."
            )
            nivel = "mal"
        return {
            "key": "cuanto_guarde",
            "label": "Cuánto guardaste",
            "value": guardado,
            "unit": "USD",
            "reading": lectura,
            "level": nivel,
        }

    def _de_cada_cien(self, guardado: Decimal, entro: Decimal) -> dict:
        """La tasa de ahorro, dicha sin decir 'tasa de ahorro'."""
        if entro <= CERO:
            return {
                "key": "de_cada_cien",
                "label": "De cada $100 que te entran",
                "value": 0.0,
                "unit": "%",
                "reading": "Aún no registras ingresos, así que no hay nada que comparar.",
                "level": "atencion",
            }

        pct = _porcentaje(guardado, entro) if guardado > CERO else round(
            float(guardado) / float(entro) * 100, 1
        )
        guarda = max(int(round(pct)), 0)
        if pct < 0:
            lectura = (
                f"De cada $100 que te entran, gastas ${100 + abs(int(round(pct)))}. "
                f"Estás sacando de lo guardado."
            )
            nivel = "mal"
        elif pct < 10:
            lectura = f"De cada $100 que te entran, guardas ${guarda}. Es poco."
            nivel = "atencion"
        else:
            lectura = f"De cada $100 que te entran, guardas ${guarda}."
            nivel = "bien"

        return {
            "key": "de_cada_cien",
            "label": "De cada $100 que te entran",
            "value": pct,
            "unit": "%",
            "reading": lectura,
            "level": nivel,
        }

    def _cuanto_aguanta(self, tengo: Decimal, gasto_normal: Decimal) -> dict:
        """Meses de colchon. Es la medida que mas tranquiliza o mas alerta."""
        if gasto_normal <= CERO:
            return {
                "key": "cuanto_aguanta",
                "label": "Cuánto te dura lo que tienes",
                "value": 0.0,
                "unit": "meses",
                "reading": "Cuando lleves un mes registrando gastos podremos decírtelo.",
                "level": "atencion",
            }

        meses = round(float(tengo) / float(gasto_normal), 1)
        if meses < 1:
            lectura = "Lo que tienes no alcanza para un mes de tus gastos normales."
            nivel = "mal"
        elif meses < 3:
            lectura = (
                f"Si dejaras de recibir dinero, lo que tienes te alcanza "
                f"para {_meses(meses)}."
            )
            nivel = "atencion"
        else:
            lectura = (
                f"Si dejaras de recibir dinero, lo que tienes te alcanza "
                f"para {_meses(meses)}. Vas bien."
            )
            nivel = "bien"

        return {
            "key": "cuanto_aguanta",
            "label": "Cuánto te dura lo que tienes",
            "value": meses,
            "unit": "meses",
            "reading": lectura,
            "level": nivel,
        }

    def _gasto_diario(self, por_dia: Decimal) -> dict:
        return {
            "key": "gasto_diario",
            "label": "Lo que gastas al día",
            "value": por_dia,
            "unit": "USD",
            "reading": f"En promedio se te van {_plata(por_dia)} cada día.",
            "level": "bien",
        }

    def _comparado_con_antes(self, cambio: Decimal, antes: Decimal) -> dict:
        """Contra el mismo numero de dias anteriores, no contra 'el mes pasado'."""
        if cambio > CERO:
            lectura = f"Guardaste {_plata(cambio)} más que en el periodo anterior."
            nivel = "bien"
        elif cambio < CERO:
            lectura = f"Guardaste {_plata(-cambio)} menos que en el periodo anterior."
            nivel = "atencion"
        else:
            lectura = "Guardaste lo mismo que en el periodo anterior."
            nivel = "bien"

        return {
            "key": "comparado_con_antes",
            "label": "Comparado con antes",
            "value": cambio,
            "unit": "USD",
            "reading": lectura,
            "level": nivel,
        }
