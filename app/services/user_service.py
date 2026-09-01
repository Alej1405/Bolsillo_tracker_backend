"""Reglas de negocio del CRUD de usuarios.

Separado de AuthService a proposito: aquel se ocupa de entrar al sistema
(registro y login), este de gestionar cuentas ya existentes.
"""

import math
import secrets
import uuid
from pathlib import Path

from app.config import settings
from app.core.errors import InvalidCredentials, NotFound, ValidationError
from app.core.security import PasswordHasher
from app.models.user import User
from app.repositories.user_repository import UserRepository

#Formatos que aceptamos, con la firma que lleva cada archivo en sus primeros
#bytes. Se mira la firma y no la extension ni el Content-Type porque los dos
#los escribe quien sube el archivo: renombrar "virus.exe" a "foto.jpg" no
#cuesta nada, cambiar los bytes de cabecera si.
FIRMAS: dict[bytes, str] = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
}

#Carpeta donde acaban las fotos, dentro de la de medios.
CARPETA_AVATARES = "avatares"


def _extension_de(contenido: bytes) -> str | None:
    """Formato real del archivo, leido de sus primeros bytes.

    WEBP no va por firma simple: empieza por "RIFF", cuatro bytes de tamano y
    luego "WEBP", asi que se comprueba aparte.
    """
    for firma, extension in FIRMAS.items():
        if contenido.startswith(firma):
            return extension
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return "webp"
    return None


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

    # ── foto de perfil ────────────────────────────────────────────────────

    def save_avatar(self, usuario: User, contenido: bytes) -> User:
        """Guarda la foto en disco y deja su ruta en la ficha del usuario.

        El nombre del archivo lleva un sufijo aleatorio y cambia en cada subida.
        Es a proposito: si se llamara siempre igual, el navegador seguiria
        mostrando la foto vieja de su cache despues de cambiarla.
        """
        tope = settings.avatar_max_mb * 1024 * 1024
        if len(contenido) > tope:
            raise ValidationError(
                f"La foto pesa mas de {settings.avatar_max_mb} MB"
            )
        if not contenido:
            raise ValidationError("El archivo llego vacio")

        extension = _extension_de(contenido)
        if extension is None:
            raise ValidationError("El archivo no es una imagen JPG, PNG ni WEBP")

        carpeta = Path(settings.media_dir) / CARPETA_AVATARES
        carpeta.mkdir(parents=True, exist_ok=True)

        nombre = f"{usuario.id}-{secrets.token_hex(4)}.{extension}"
        (carpeta / nombre).write_bytes(contenido)

        anterior = usuario.avatar_url
        actualizado = self._repo.set_avatar(usuario, f"/media/{CARPETA_AVATARES}/{nombre}")
        #el archivo viejo se borra despues de guardar el nuevo: si algo falla al
        #escribir, la persona conserva la foto que ya tenia.
        self._borrar_archivo(anterior)
        return actualizado

    def remove_avatar(self, usuario: User) -> User:
        """Quita la foto. Sin foto la interfaz muestra las iniciales."""
        anterior = usuario.avatar_url
        actualizado = self._repo.set_avatar(usuario, None)
        self._borrar_archivo(anterior)
        return actualizado

    @staticmethod
    def _borrar_archivo(avatar_url: str | None) -> None:
        """Borra del disco la foto que ya no se usa.

        Sin esto cada cambio de foto deja un archivo huerfano y la carpeta crece
        sola. El nombre se toma del final de la ruta y se comprueba que no
        contenga separadores: una ruta manipulada del tipo "../../.env" no puede
        salir de la carpeta de avatares.
        """
        if not avatar_url:
            return
        nombre = avatar_url.rsplit("/", 1)[-1]
        if not nombre or "/" in nombre or "\\" in nombre or nombre.startswith("."):
            return
        archivo = Path(settings.media_dir) / CARPETA_AVATARES / nombre
        archivo.unlink(missing_ok=True)

    def deactivate_self(self, usuario: User) -> None:
        """Baja LOGICA: conserva cuentas, transacciones e historial."""
        self._repo.set_active(usuario, False)

    # ── operaciones del super_admin ───────────────────────────────────────

    def list_users(
        self,
        page: int,
        page_size: int,
        is_active: bool | None = None,
        q: str | None = None,
    ) -> dict:
        """
        Una pagina del listado, con los totales ya calculados.

        `total` cuenta los que cumplen los filtros, busqueda incluida: es lo
        que hace que la paginacion sea correcta al buscar. Si contara todos,
        la interfaz mostraria paginas vacias.
        """
        items, total = self._repo.list_paginated(page, page_size, is_active, q)
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
