"""Consultas agregadas para los reportes.

Todo se suma en PostgreSQL, no en Python y menos en el navegador: una formula
repetida en dos sitios acaba dando dos numeros distintos, y los float de
JavaScript descuadran centavos. Es la regla de 04-convenciones.md.

Estos metodos devuelven filas crudas (Row); darles forma es del servicio.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.orm import Session, aliased

from app.models.account import Account, AccountType
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType

CERO = Decimal("0.00")


class ReportRepository:
    def __init__(self, db: Session):
        self._db = db

    def _vivas(self, user_id: uuid.UUID) -> list:
        """Las condiciones que toda consulta de reporte comparte."""
        return [
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        ]

    def _suma_si(self, tipo: TransactionType):
        """SUM que solo cuenta las filas de un tipo. El resto suma 0."""
        return func.coalesce(
            func.sum(case((Transaction.type == tipo, Transaction.amount), else_=0)),
            0,
        )

    def _es_ahorro(self):
        """La condicion 'esta transferencia entra a una cuenta de ahorro'.

        destino.type = savings. Se apoya en el join con la cuenta destino que
        arman los metodos que la usan.
        """
        return and_(
            Transaction.type == TransactionType.TRANSFER,
            Account.type == AccountType.SAVINGS,
        )

    def summary(
        self,
        user_id: uuid.UUID,
        desde: date,
        hasta: date,
        account_id: uuid.UUID | None = None,
    ):
        """Ingresos, egresos, neto, ahorrado y cuantos movimientos hubo."""
        destino = aliased(Account)

        filtros = self._vivas(user_id) + [
            Transaction.occurred_at >= desde,
            Transaction.occurred_at <= hasta,
        ]
        if account_id is not None:
            filtros.append(
                or_(
                    Transaction.account_id == account_id,
                    Transaction.counter_account_id == account_id,
                )
            )

        #el ahorro es la transferencia cuyo DESTINO es una cuenta savings
        ahorrado = func.coalesce(
            func.sum(
                case(
                    (
                        and_(
                            Transaction.type == TransactionType.TRANSFER,
                            destino.type == AccountType.SAVINGS,
                        ),
                        Transaction.amount,
                    ),
                    else_=0,
                )
            ),
            0,
        )

        stmt = (
            select(
                self._suma_si(TransactionType.INCOME).label("total_income"),
                self._suma_si(TransactionType.EXPENSE).label("total_expense"),
                ahorrado.label("total_saved"),
                func.count().label("transaction_count"),
            )
            .select_from(Transaction)
            .outerjoin(destino, Transaction.counter_account_id == destino.id)
            .where(*filtros)
        )
        return self._db.execute(stmt).one()

    def by_category(
        self, user_id: uuid.UUID, desde: date, hasta: date, tipo: TransactionType
    ):
        """Suma por categoria, trayendo tambien el padre de cada una.

        No agrupa por padre aqui: devuelve la hoja con su padre al lado y el
        servicio arma el arbol. Hacerlo en SQL exigiria dos consultas o un
        GROUPING SETS, y el volumen de un proyecto asi no lo justifica.
        """
        padre = aliased(Category)

        stmt = (
            select(
                Category.id.label("cat_id"),
                Category.name.label("cat_name"),
                Category.icon.label("cat_icon"),
                Category.color.label("cat_color"),
                padre.id.label("padre_id"),
                padre.name.label("padre_name"),
                padre.icon.label("padre_icon"),
                padre.color.label("padre_color"),
                func.sum(Transaction.amount).label("amount"),
                func.count().label("transaction_count"),
            )
            .select_from(Transaction)
            .join(Category, Transaction.category_id == Category.id)
            .outerjoin(padre, Category.parent_id == padre.id)
            .where(
                *self._vivas(user_id),
                Transaction.type == tipo,
                Transaction.occurred_at >= desde,
                Transaction.occurred_at <= hasta,
            )
            #agrupar por la PK basta: PostgreSQL sabe que el resto depende de ella
            .group_by(Category.id, padre.id)
            .order_by(func.sum(Transaction.amount).desc())
        )
        return self._db.execute(stmt).all()

    def monthly(self, user_id: uuid.UUID, year: int):
        """Un renglon por mes con datos. Los meses vacios los rellena el servicio."""
        destino = aliased(Account)
        mes = func.to_char(Transaction.occurred_at, "YYYY-MM")

        ahorrado = func.coalesce(
            func.sum(
                case(
                    (
                        and_(
                            Transaction.type == TransactionType.TRANSFER,
                            destino.type == AccountType.SAVINGS,
                        ),
                        Transaction.amount,
                    ),
                    else_=0,
                )
            ),
            0,
        )

        stmt = (
            select(
                mes.label("month"),
                self._suma_si(TransactionType.INCOME).label("income"),
                self._suma_si(TransactionType.EXPENSE).label("expense"),
                ahorrado.label("saved"),
            )
            .select_from(Transaction)
            .outerjoin(destino, Transaction.counter_account_id == destino.id)
            .where(
                *self._vivas(user_id),
                func.extract("year", Transaction.occurred_at) == year,
            )
            .group_by(mes)
            .order_by(mes)
        )
        return self._db.execute(stmt).all()

    # ── Rendimiento ──────────────────────────────────────────────────────
    #
    # Lo que sigue responde a una queja concreta: `total_saved` solo cuenta
    # las transferencias que entran a una cuenta de tipo savings, asi que
    # quien ahorra dejando la plata quieta en el banco o en el efectivo ve
    # un cero que no es verdad.
    #
    # Aqui se miden las dos cosas por separado, porque son distintas:
    #   · lo GUARDADO en el periodo  = lo que entro menos lo que salio
    #   · lo que TIENES ahora        = la suma de todos los bolsillos vivos
    #
    # La primera es un resultado del mes; la segunda es una foto del momento.

    def patrimonio(self, user_id: uuid.UUID) -> Decimal:
        """La suma de todos los bolsillos activos. Es 'cuanto tengo'.

        Sale de la vista account_balances, la misma que alimenta el saldo de
        cada cuenta, para que no haya dos formulas del mismo numero. Las
        archivadas no cuentan: estan fuera del patrimonio a proposito.
        """
        stmt = select(
            func.coalesce(func.sum(Account.balance), 0)
        ).where(
            Account.user_id == user_id,
            Account.archived_at.is_(None),
        )
        return Decimal(self._db.execute(stmt).scalar_one() or 0)

    def totales_del_rango(self, user_id: uuid.UUID, desde: date, hasta: date):
        """Entradas, salidas y numero de movimientos de un rango.

        Es `summary` sin el ahorro ni el join con la cuenta destino: el
        rendimiento no necesita esa parte y el join sobra.
        """
        stmt = (
            select(
                self._suma_si(TransactionType.INCOME).label("income"),
                self._suma_si(TransactionType.EXPENSE).label("expense"),
                func.count().label("count"),
            )
            .select_from(Transaction)
            .where(
                *self._vivas(user_id),
                Transaction.occurred_at >= desde,
                Transaction.occurred_at <= hasta,
            )
        )
        return self._db.execute(stmt).one()

    def gasto_medio_mensual(self, user_id: uuid.UUID, meses: int = 6) -> Decimal:
        """Cuanto se gasta en un mes normal, mirando los ultimos N meses.

        Se usa para saber cuantos meses aguanta el dinero guardado. Se toma un
        promedio y no el ultimo mes porque un mes con una compra grande daria
        una respuesta alarmista, y uno de vacaciones una tranquilizadora.

        Solo cuentan los meses que tuvieron algun gasto: dividir para 6 cuando
        la persona lleva dos meses usando la app parte el promedio a la mitad.
        """
        mes = func.date_trunc("month", Transaction.occurred_at)
        gastos_por_mes = (
            select(func.sum(Transaction.amount).label("total"))
            .where(
                *self._vivas(user_id),
                Transaction.type == TransactionType.EXPENSE,
                Transaction.occurred_at >= func.current_date() - func.cast(
                    func.concat(meses, " months"), INTERVAL
                ),
            )
            .group_by(mes)
            .subquery()
        )
        stmt = select(func.coalesce(func.avg(gastos_por_mes.c.total), 0))
        return Decimal(self._db.execute(stmt).scalar_one() or 0)
