"""Reglas de negocio de las categorias.

Tres cosas que decide esta capa:

  1. Las del sistema son de solo lectura. Son UNA fila compartida por todos los
     usuarios: si Maria pudiera archivar "Mascotas", desapareceria tambien para
     Carlos. Por eso editarlas o archivarlas responde 403.
  2. Solo dos niveles. El trigger de la base tambien lo impide, pero aqui se
     detecta antes y con un mensaje legible.
  3. Una categoria con movimientos no se archiva: 409 IN_USE, y el mensaje dice
     cuantos son.
"""

import uuid

from app.core.errors import (
    CategoryInUse,
    CategoryNameTaken,
    InvalidCategoryParent,
    NotFound,
    SystemCategoryReadOnly,
)
from app.models.category import Category, CategoryKind
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    def __init__(self, repo: CategoryRepository):
        self._repo = repo

    # ---------- lectura ----------

    def list_tree(
        self,
        user_id: uuid.UUID,
        kind: CategoryKind | None = None,
        include_archived: bool = False,
    ) -> dict:
        padres = self._repo.list_tree(user_id, kind, include_archived)

        if not include_archived:
            #el where filtro los PADRES; las hijas archivadas llegaron igual
            #con el selectinload, asi que se descartan aqui
            for padre in padres:
                padre.children = [h for h in padre.children if h.archived_at is None]

        return {"items": padres}

    def get_category(self, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
        categoria = self._repo.get_by_id(user_id, category_id)
        if categoria is None:
            raise NotFound("No se encontro la categoria solicitada")
        return categoria

    # ---------- escritura ----------

    def create_category(self, user_id: uuid.UUID, datos: CategoryCreate) -> Category:
        if datos.parent_id is not None:
            self._validar_padre(user_id, datos.parent_id, datos.kind)

        if self._repo.get_by_name(user_id, datos.name, datos.parent_id, datos.kind):
            raise CategoryNameTaken("Ya tienes una categoria con ese nombre ahi")

        return self._repo.create(
            user_id=user_id,
            name=datos.name,
            kind=datos.kind,
            parent_id=datos.parent_id,
            icon=datos.icon,
            color=datos.color,
        )

    def _validar_padre(
        self, user_id: uuid.UUID, parent_id: uuid.UUID, kind: CategoryKind
    ) -> Category:
        padre = self._repo.get_by_id(user_id, parent_id)

        if padre is None:
            raise InvalidCategoryParent("La categoria padre no existe")
        if padre.parent_id is not None:
            raise InvalidCategoryParent(
                f"'{padre.name}' ya es una subcategoria: solo se permiten dos niveles"
            )
        if padre.kind != kind:
            raise InvalidCategoryParent(
                f"'{padre.name}' es de otro tipo: una subcategoria hereda el tipo de su padre"
            )
        if padre.archived_at is not None:
            raise InvalidCategoryParent(f"'{padre.name}' esta archivada")
        return padre

    def update_category(
        self, user_id: uuid.UUID, category_id: uuid.UUID, datos: CategoryUpdate
    ) -> Category:
        categoria = self.get_category(user_id, category_id)
        self._exigir_propia(categoria)

        cambios = datos.model_dump(exclude_unset=True)

        nuevo_nombre = cambios.get("name")
        if nuevo_nombre and nuevo_nombre != categoria.name:
            repetida = self._repo.get_by_name(
                user_id, nuevo_nombre, categoria.parent_id, categoria.kind
            )
            if repetida:
                raise CategoryNameTaken("Ya tienes una categoria con ese nombre ahi")

        return self._repo.update(categoria, cambios)

    def archive_category(self, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
        """El DELETE del contrato archiva: la categoria tiene historial detras."""
        categoria = self.get_category(user_id, category_id)
        self._exigir_propia(categoria)

        usos = self._repo.count_transactions(category_id)
        if usos:
            raise CategoryInUse(
                f"No se puede archivar: {usos} movimiento(s) usan esta categoria"
            )

        hijas = self._repo.count_children(category_id)
        if hijas:
            raise CategoryInUse(
                f"Archiva primero sus {hijas} subcategoria(s)"
            )

        return self._repo.archive(categoria)

    @staticmethod
    def _exigir_propia(categoria: Category) -> None:
        if categoria.is_system:
            raise SystemCategoryReadOnly(
                "Las categorias precargadas son de todos los usuarios: no se editan "
                "ni se archivan. Crea la tuya."
            )
