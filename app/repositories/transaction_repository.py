"""Acceso a datos de transacciones.

Dos reglas que se cumplen en TODOS los metodos:
    · se filtra siempre por user_id (nadie ve movimientos de otro)
    · se filtra siempre deleted_at IS NULL (el borrado es logico)

Ningun metodo hace commit: eso es del endpoint.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.transaction import Transaction, TransactionType


class TransactionRepository:
    def __init__(self, db: Session):
        self._db = db

    # ---------- lectura ----------

    def _base(self, user_id: uuid.UUID) -> Select:
        """El punto de partida de toda consulta: mis movimientos, no borrados."""
        return select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )

    def _aplicar_filtros(
        self,
        stmt: Select,
        desde: date | None = None,
        hasta: date | None = None,
        tipos: list[TransactionType] | None = None,
        account_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        search: str | None = None,
    ) -> Select:
        if desde is not None:
            stmt = stmt.where(Transaction.occurred_at >= desde)
        if hasta is not None:
            stmt = stmt.where(Transaction.occurred_at <= hasta)
        if tipos:
            stmt = stmt.where(Transaction.type.in_(tipos))
        if account_id is not None:
            #una transferencia toca dos cuentas: la fila cuenta para ambas
            stmt = stmt.where(
                or_(
                    Transaction.account_id == account_id,
                    Transaction.counter_account_id == account_id,
                )
            )
        if category_id is not None:
            #si piden una categoria padre, entran tambien sus hijas
            familia = select(Category.id).where(
                or_(Category.id == category_id, Category.parent_id == category_id)
            )
            stmt = stmt.where(Transaction.category_id.in_(familia))
        if search:
            stmt = stmt.where(Transaction.note.ilike(f"%{search}%"))
        return stmt

    def list_paginated(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        **filtros,
    ) -> tuple[list[Transaction], int]:
        """Devuelve (las filas de esta pagina, el total que hay sin paginar)."""
        stmt = self._aplicar_filtros(self._base(user_id), **filtros)

        #el total se cuenta ANTES de limit/offset, sobre los mismos filtros
        total = self._db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        stmt = (
            stmt.options(joinedload(Transaction.category).joinedload(Category.parent))
            .order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        filas = list(self._db.scalars(stmt).unique().all())
        return filas, total

    def get_by_id(self, user_id: uuid.UUID, tx_id: uuid.UUID) -> Transaction | None:
        stmt = self._base(user_id).where(Transaction.id == tx_id).options(
            joinedload(Transaction.category).joinedload(Category.parent)
        )
        return self._db.scalars(stmt).unique().first()

    def recent(self, user_id: uuid.UUID, limit: int = 5) -> list[Transaction]:
        stmt = (
            self._base(user_id)
            .options(joinedload(Transaction.category).joinedload(Category.parent))
            .order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
            .limit(limit)
        )
        return list(self._db.scalars(stmt).unique().all())

    def count_by_category(self, category_id: uuid.UUID) -> int:
        """Cuantos movimientos vivos usan esta categoria (para el 409 IN_USE)."""
        stmt = select(func.count()).where(
            Transaction.category_id == category_id,
            Transaction.deleted_at.is_(None),
        )
        return self._db.scalar(stmt) or 0

    def find_visible_category(
        self, user_id: uuid.UUID, category_id: uuid.UUID
    ) -> Category | None:
        """La categoria si el usuario puede usarla: la suya o una del sistema.

        Vive aqui, y no en CategoryRepository, para que el servicio de
        transacciones pueda validar el kind sin depender del modulo de
        categorias.
        """
        stmt = select(Category).where(
            Category.id == category_id,
            or_(Category.user_id == user_id, Category.user_id.is_(None)),
        )
        return self._db.scalars(stmt).first()

    # ---------- escritura ----------

    def create(
        self,
        user_id: uuid.UUID,
        type: TransactionType,
        amount: Decimal,
        account_id: uuid.UUID,
        occurred_at: date,
        category_id: uuid.UUID | None = None,
        counter_account_id: uuid.UUID | None = None,
        note: str | None = None,
    ) -> Transaction:
        movimiento = Transaction(
            user_id=user_id,
            type=type,
            amount=amount,
            account_id=account_id,
            counter_account_id=counter_account_id,
            category_id=category_id,
            occurred_at=occurred_at,
            note=note,
        )
        self._db.add(movimiento)
        self._db.flush()
        #refresh para que vuelvan los server_default (currency, created_at)
        self._db.refresh(movimiento)
        return movimiento

    def update(self, movimiento: Transaction, cambios: dict) -> Transaction:
        for campo, valor in cambios.items():
            setattr(movimiento, campo, valor)
        self._db.flush()
        self._db.refresh(movimiento)
        return movimiento

    def soft_delete(self, movimiento: Transaction) -> None:
        """No borra la fila: la marca. El historial se conserva."""
        movimiento.deleted_at = func.now()
        self._db.flush()
