"""Reglas de negocio del CRUD de usuarios.

Separado de AuthService a proposito: aquel se ocupa de entrar al sistema
(registro y login), este de gestionar cuentas ya existentes.
"""

import math
import uuid

from app.core.errors import InvalidCredentials, NotFound, ValidationError
from app.core.security import PasswordHasher
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    """Alta, consulta, modificacion y baja de usuarios."""

    def __init__(self, repo: UserRepository, hasher: PasswordHasher):
        self._repo = repo
        self._hasher = hasher

    # ── operaciones sobre la cuenta propia ────────────────────────────────

    def update_profile(self, usuario: User, full_name: str) -> User:
        """Cambia el nombre. El correo no se toca: es la identidad de acceso."""
        return self._repo.update_name(usuario, full_name)

    def change_password(self, usuario: User, actual: str, nueva: str) -> None:
        """Cambia la contrasena exigiendo la actual.

        Se pide aunque el usuario ya este autenticado: si alguien deja la sesion
        abierta, no debe poder cambiar la clave y quedarse con la cuenta.
        """
        if not self._hasher.verify(actual, usuario.password_hash):
            raise InvalidCredentials("La contrasena actual no es correcta")

        if self._hasher.verify(nueva, usuario.password_hash):
            raise ValidationError("La contrasena nueva debe ser distinta de la actual")

        self._repo.update_password_hash(usuario, self._hasher.hash(nueva))

    def deactivate_self(self, usuario: User) -> None:
        """Baja LOGICA: conserva cuentas, transacciones e historial."""
        self._repo.set_active(usuario, False)

    # ── operaciones del super_admin ───────────────────────────────────────

    def list_users(
        self, page: int, page_size: int, is_active: bool | None = None
    ) -> dict:
        """Una pagina del listado, con los totales ya calculados."""
        items, total = self._repo.list_paginated(page, page_size, is_active)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if page_size else 0,
        }

    def get_user(self, user_id: uuid.UUID) -> User:
        usuario = self._repo.get_by_id(user_id)
        if usuario is None:
            raise NotFound("No se encontro el usuario solicitado")
        return usuario

    def set_active(self, user_id: uuid.UUID, is_active: bool) -> User:
        """Activa o desactiva una cuenta. Unico camino de vuelta para quien se dio de baja."""
        return self._repo.set_active(self.get_user(user_id), is_active)

    def delete_forever(self, user_id: uuid.UUID, confirm: bool) -> None:
        """Borrado REAL en cascada: arrastra cuentas, categorias y transacciones.

        Exige confirm=true para que un clic accidental en un listado no destruya
        el historial de una persona.
        """
        if not confirm:
            raise ValidationError(
                "Para borrar definitivamente hay que enviar confirm=true"
            )
        self._repo.delete(self.get_user(user_id))
