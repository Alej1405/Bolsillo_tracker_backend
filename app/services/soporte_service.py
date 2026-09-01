"""Reglas de las conversaciones de soporte.

Quien escribe decide el estado del hilo, y eso ordena la bandeja del
administrador sin que nadie tenga que marcar nada a mano.
"""

import math
import uuid

from app.core.errors import Forbidden, NotFound, ValidationError
from app.models.soporte import SupportStatus, SupportThread
from app.models.user import User
from app.repositories.soporte_repository import SoporteRepository


class SoporteService:
    """Abrir consultas, responderlas y cerrarlas."""

    def __init__(self, repo: SoporteRepository):
        self._repo = repo

    # ── quien usa la aplicacion ──────────────────────────────────────────

    def abrir(self, usuario: User, subject: str, body: str) -> SupportThread:
        """Una consulta nueva de alguien con cuenta."""
        hilo = self._repo.crear_hilo(subject=subject.strip(), user_id=usuario.id)
        self._repo.agregar_mensaje(hilo, body.strip(), usuario.id, from_admin=False)
        return hilo

    def abrir_como_invitado(
        self, nombre: str, correo: str, subject: str, body: str
    ) -> SupportThread:
        """Una consulta desde el formulario de la landing, sin cuenta.

        Es el mismo hilo que abriria un usuario: se responde igual y aparece en
        la misma bandeja. Lo unico distinto es que no hay a quien enlazarlo, asi
        que se guardan el nombre y el correo que dejo.
        """
        hilo = self._repo.crear_hilo(
            subject=subject.strip(),
            guest_name=nombre.strip(),
            guest_email=correo.strip(),
        )
        self._repo.agregar_mensaje(hilo, body.strip(), author_id=None, from_admin=False)
        return hilo

    def mis_hilos(self, usuario: User) -> list[SupportThread]:
        return self._repo.hilos_del_usuario(usuario.id)

    def responder(self, usuario: User, thread_id: uuid.UUID, body: str) -> SupportThread:
        """Escribir en un hilo propio.

        Un hilo cerrado no se reabre escribiendo: quien lo cerro fue el equipo
        porque el asunto termino, y colar mensajes en una conversacion cerrada
        haria que no la viera nadie. Para algo nuevo, un hilo nuevo.
        """
        hilo = self._hilo_visible(usuario, thread_id)
        if hilo.status == SupportStatus.CERRADO:
            raise ValidationError(
                "Esta conversacion esta cerrada. Abre una nueva para un asunto distinto"
            )
        self._repo.agregar_mensaje(hilo, body.strip(), usuario.id, from_admin=False)
        return hilo

    def ver(self, usuario: User, thread_id: uuid.UUID) -> SupportThread:
        return self._hilo_visible(usuario, thread_id)

    def _hilo_visible(self, usuario: User, thread_id: uuid.UUID) -> SupportThread:
        """El hilo, si es de esa persona. Si es de otra, 403 y no 404.

        Se distingue a proposito de "no existe": el recurso existe, lo que no
        hay es permiso, y confundirlos deja al usuario buscando un hilo que si
        esta ahi.
        """
        hilo = self._repo.get(thread_id)
        if hilo is None:
            raise NotFound("No encontramos esa conversacion")
        if hilo.user_id != usuario.id:
            raise Forbidden("Esa conversacion no es tuya")
        return hilo

    # ── quien administra ─────────────────────────────────────────────────

    def listar(self, page: int, page_size: int, status: SupportStatus | None = None) -> dict:
        items, total = self._repo.listar(page, page_size, status)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if page_size else 0,
            #Lo que falta por contestar, para el aviso del panel.
            "pending": self._repo.sin_responder(),
        }

    def ver_como_admin(self, thread_id: uuid.UUID) -> SupportThread:
        hilo = self._repo.get(thread_id)
        if hilo is None:
            raise NotFound("No encontramos esa conversacion")
        return hilo

    def responder_como_admin(
        self, admin: User, thread_id: uuid.UUID, body: str
    ) -> SupportThread:
        hilo = self.ver_como_admin(thread_id)
        self._repo.agregar_mensaje(hilo, body.strip(), admin.id, from_admin=True)
        return hilo

    def cerrar(self, thread_id: uuid.UUID) -> SupportThread:
        return self._repo.cambiar_estado(self.ver_como_admin(thread_id), SupportStatus.CERRADO)

    def reabrir(self, thread_id: uuid.UUID) -> SupportThread:
        return self._repo.cambiar_estado(self.ver_como_admin(thread_id), SupportStatus.ABIERTO)
