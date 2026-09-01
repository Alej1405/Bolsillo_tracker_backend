"""Consultas de toda la plataforma, no de un usuario.

Es la diferencia con los demas repositorios: aqui NO se filtra por user_id
porque la pregunta es sobre el conjunto —cuanta gente hay, cuanto se registra—.
Quien puede hacerla la decide el router con require_super_admin.

Ningun metodo hace commit: aqui solo se lee.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.repositories.consultas import vivos


class AdminRepository:
    def __init__(self, db: Session):
        self._db = db

    # ── usuarios ─────────────────────────────────────────────────────────

    def usuarios(self) -> tuple[int, int]:
        """Cuantos hay en total y cuantos pueden entrar."""
        stmt = select(
            func.count(User.id),
            func.count(User.id).filter(User.is_active),
        )
        total, activos = self._db.execute(stmt).one()
        return total or 0, activos or 0

    def altas_desde(self, desde: date) -> int:
        """Cuentas creadas a partir de esa fecha, incluida."""
        stmt = select(func.count(User.id)).where(func.date(User.created_at) >= desde)
        return self._db.scalar(stmt) or 0

    # ── actividad ────────────────────────────────────────────────────────

    def movimientos(self, desde: date | None = None) -> int:
        """Movimientos vivos. Con `desde`, solo los de esa fecha en adelante."""
        filtros = [vivos()]
        if desde is not None:
            filtros.append(Transaction.occurred_at >= desde)
        return self._db.scalar(select(func.count(Transaction.id)).where(*filtros)) or 0

    def movido_en(self, desde: date, hasta: date) -> tuple[str, str]:
        """Cuanto entro y cuanto salio en toda la plataforma, en un rango.

        Las transferencias no se cuentan: mover plata de un bolsillo propio a
        otro no es dinero que entre ni salga del sistema, y sumarlas inflaria
        las dos cifras con el mismo importe.
        """
        suma = lambda tipo: func.coalesce(  # noqa: E731 - una expresion, no una funcion
            func.sum(Transaction.amount).filter(Transaction.type == tipo), 0
        )
        stmt = select(
            suma(TransactionType.INCOME),
            suma(TransactionType.EXPENSE),
        ).where(
            vivos(),
            Transaction.occurred_at >= desde,
            Transaction.occurred_at <= hasta,
        )
        entro, salio = self._db.execute(stmt).one()
        return str(entro), str(salio)

    def bolsillos(self) -> int:
        """Bolsillos sin archivar de toda la plataforma."""
        stmt = select(func.count(Account.id)).where(Account.archived_at.is_(None))
        return self._db.scalar(stmt) or 0

    def categorias_propias(self) -> int:
        """Las que crearon los usuarios. Las del sistema no cuentan."""
        stmt = select(func.count(Category.id)).where(Category.user_id.is_not(None))
        return self._db.scalar(stmt) or 0

    # ── uso ──────────────────────────────────────────────────────────────

    def usuarios_con_movimientos(self, desde: date) -> int:
        """Cuantas personas registraron algo desde esa fecha.

        Es la medida de uso real: registrarse es facil, volver no. La diferencia
        entre esto y el total de cuentas dice cuantas se quedaron vacias.
        """
        stmt = select(func.count(func.distinct(Transaction.user_id))).where(
            vivos(),
            Transaction.occurred_at >= desde,
        )
        return self._db.scalar(stmt) or 0

    def top_categorias(self, limite: int = 5) -> list:
        """Las categorias con mas gastos registrados en toda la plataforma."""
        stmt = (
            select(
                Category.name,
                func.count(Transaction.id).label("usos"),
            )
            .join(Transaction, Transaction.category_id == Category.id)
            .where(
                vivos(),
                Transaction.type == TransactionType.EXPENSE,
            )
            .group_by(Category.name)
            .order_by(func.count(Transaction.id).desc())
            .limit(limite)
        )
        return list(self._db.execute(stmt).all())
