"""Modelo de categorias: en que se gasta y de donde viene el dinero.

Dos cosas la distinguen del resto de modelos:

  · user_id puede ser NULL. Eso significa "categoria del sistema": una fila
    compartida que ven todos los usuarios y que nadie edita ni archiva.
  · parent_id apunta a su PROPIA tabla. Solo se permiten dos niveles, y eso lo
    vigila el trigger tg_categories_hierarchy (un CHECK no puede consultar
    otras filas).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CategoryKind(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    #NULL = categoria del sistema, visible para todos
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    #NULL = es una categoria padre. RESTRICT: no se borra un padre con hijas
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    kind: Mapped[CategoryKind] = mapped_column(
        PGEnum(
            CategoryKind,
            name="category_kind",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    icon: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    color: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    #Relacion de la tabla consigo misma. remote_side va en el lado que apunta
    #al padre: le dice a SQLAlchemy cual de los dos extremos es el "uno".
    children: Mapped[list["Category"]] = relationship(
        back_populates="parent",
    )
    parent: Mapped["Category | None"] = relationship(
        back_populates="children",
        remote_side="Category.id",
    )

    @property
    def is_system(self) -> bool:
        """Precargada = no tiene dueno. Pydantic la lee como una columna mas."""
        return self.user_id is None

    def __repr__(self) -> str:
        return f"<Category {self.name} ({self.kind.value})>"
