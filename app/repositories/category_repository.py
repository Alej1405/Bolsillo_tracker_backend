"""Acceso a datos de categorias.

La diferencia con AccountRepository: aqui el usuario NO solo ve lo suyo.
Ve sus categorias y ademas las del sistema (user_id NULL), que son de todos.
Ese OR se repite en cada consulta y por eso vive en _visibles().

Ningun metodo hace commit.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.category import Category, CategoryKind
from app.models.transaction import Transaction
from app.repositories.consultas import vivos


class CategoryRepository:
    def __init__(self, db: Session):
        self._db = db

    def _visibles(self, user_id: uuid.UUID):
        """Las mias o las del sistema. `.is_(None)` porque NULL = NULL es falso."""
        return or_(Category.user_id == user_id, Category.user_id.is_(None))

    def list_tree(
        self,
        user_id: uuid.UUID,
        kind: CategoryKind | None = None,
        include_archived: bool = False,
    ) -> list[Category]:
        """Solo los padres; sus hijas vienen cargadas.

        selectinload trae TODAS las hijas en una segunda consulta, no una por
        padre. Con lazy por defecto esto serian 17 consultas en vez de 2.
        """
        filtros = [self._visibles(user_id), Category.parent_id.is_(None)]
        if kind is not None:
            filtros.append(Category.kind == kind)
        if not include_archived:
            filtros.append(Category.archived_at.is_(None))

        stmt = (
            select(Category)
            .where(*filtros)
            .options(selectinload(Category.children))
            .order_by(Category.name)
        )
        return list(self._db.scalars(stmt).unique().all())

    def get_by_id(self, user_id: uuid.UUID, category_id: uuid.UUID) -> Category | None:
        stmt = select(Category).where(
            Category.id == category_id, self._visibles(user_id)
        )
        return self._db.scalars(stmt).first()

    def get_by_name(
        self,
        user_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None,
        kind: CategoryKind,
    ) -> Category | None:
        """Busca un duplicado con las mismas reglas que los indices UNIQUE.

        Solo entre las PROPIAS: que exista "Salud" del sistema no impide que el
        usuario cree la suya.
        """
        filtros = [
            Category.user_id == user_id,
            func.lower(Category.name) == name.lower(),
        ]
        if parent_id is None:
            #los indices de la base distinguen padre e hija: el de raiz incluye kind
            filtros += [Category.parent_id.is_(None), Category.kind == kind]
        else:
            filtros.append(Category.parent_id == parent_id)

        return self._db.scalars(select(Category).where(*filtros)).first()

    def count_transactions(self, category_id: uuid.UUID) -> int:
        """Movimientos vivos que usan esta categoria (para el 409 IN_USE)."""
        stmt = select(func.count()).where(
            Transaction.category_id == category_id,
            vivos(),
        )
        return self._db.scalar(stmt) or 0

    def count_children(self, category_id: uuid.UUID) -> int:
        """Hijas sin archivar. Archivar un padre con hijas vivas las dejaria huerfanas."""
        stmt = select(func.count()).where(
            Category.parent_id == category_id,
            Category.archived_at.is_(None),
        )
        return self._db.scalar(stmt) or 0

    def create(
        self,
        user_id: uuid.UUID,
        name: str,
        kind: CategoryKind,
        parent_id: uuid.UUID | None = None,
        icon: str | None = None,
        color: str | None = None,
    ) -> Category:
        categoria = Category(
            user_id=user_id,
            name=name,
            kind=kind,
            parent_id=parent_id,
            icon=icon,
            color=color,
        )
        self._db.add(categoria)
        self._db.flush()
        self._db.refresh(categoria)
        return categoria

    def update(self, categoria: Category, cambios: dict) -> Category:
        for campo, valor in cambios.items():
            setattr(categoria, campo, valor)
        self._db.flush()
        return categoria

    def archive(self, categoria: Category) -> Category:
        categoria.archived_at = func.now()
        self._db.flush()
        self._db.refresh(categoria)
        return categoria
