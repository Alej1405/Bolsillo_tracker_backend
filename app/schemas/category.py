"""Schemas de categorias.

CategoryRead se contiene a si misma (`children`), asi que la referencia va
entre comillas y se resuelve con model_rebuild() al final del archivo.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.category import CategoryKind


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: CategoryKind
    #si viene, la categoria es hija y su kind debe coincidir con el del padre
    parent_id: uuid.UUID | None = None
    icon: str | None = None
    color: str | None = None


class CategoryUpdate(BaseModel):
    """PATCH parcial: ni el kind ni el padre se cambian una vez creada."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    icon: str | None = None
    color: str | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: CategoryKind
    icon: str | None = None
    color: str | None = None
    #no es columna: sale de la property del modelo (user_id is None)
    is_system: bool
    parent_id: uuid.UUID | None = None
    archived_at: datetime | None = None
    children: list["CategoryRead"] = []


class CategoryTreeResponse(BaseModel):
    items: list[CategoryRead]


#sin esto, la referencia "CategoryRead" de children se queda sin resolver
CategoryRead.model_rebuild()
