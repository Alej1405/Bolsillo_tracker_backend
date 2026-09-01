"""Acceso a datos de las conversaciones de soporte.

Dos vistas del mismo dato: la del usuario, que solo ve sus hilos, y la del
administrador, que los ve todos. El filtro por user_id se aplica en los metodos
del usuario, nunca en los del admin.

Ningun metodo hace commit: eso es del endpoint.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.soporte import SupportMessage, SupportStatus, SupportThread
from app.repositories.consultas import paginar


class SoporteRepository:
    def __init__(self, db: Session):
        self._db = db

    # ── lectura ──────────────────────────────────────────────────────────

    def hilos_del_usuario(self, user_id: uuid.UUID) -> list[SupportThread]:
        """Los hilos de una persona, del mas movido al mas quieto."""
        stmt = (
            select(SupportThread)
            .where(SupportThread.user_id == user_id)
            .options(selectinload(SupportThread.messages))
            .order_by(SupportThread.updated_at.desc())
        )
        return list(self._db.scalars(stmt).unique().all())

    def listar(
        self, page: int, page_size: int, status: SupportStatus | None = None
    ) -> tuple[list[SupportThread], int]:
        """Todos los hilos, paginados. Solo para el administrador."""
        filtros = [SupportThread.status == status] if status else []

        total = self._db.scalar(
            select(func.count(SupportThread.id)).where(*filtros)
        ) or 0

        stmt = (
            select(SupportThread)
            .where(*filtros)
            .options(selectinload(SupportThread.messages))
            .order_by(SupportThread.updated_at.desc())
        )
        stmt = paginar(stmt, page, page_size)
        return list(self._db.scalars(stmt).unique().all()), total

    def get(self, thread_id: uuid.UUID) -> SupportThread | None:
        stmt = (
            select(SupportThread)
            .where(SupportThread.id == thread_id)
            .options(selectinload(SupportThread.messages))
        )
        return self._db.scalars(stmt).unique().first()

    def sin_responder(self) -> int:
        """Cuantos hilos esperan respuesta. Es el numero del panel."""
        stmt = select(func.count(SupportThread.id)).where(
            SupportThread.status == SupportStatus.ABIERTO
        )
        return self._db.scalar(stmt) or 0

    # ── escritura ────────────────────────────────────────────────────────

    def crear_hilo(
        self,
        subject: str,
        user_id: uuid.UUID | None = None,
        guest_name: str | None = None,
        guest_email: str | None = None,
    ) -> SupportThread:
        hilo = SupportThread(
            subject=subject,
            user_id=user_id,
            guest_name=guest_name,
            guest_email=guest_email,
        )
        self._db.add(hilo)
        self._db.flush()
        return hilo

    def agregar_mensaje(
        self,
        hilo: SupportThread,
        body: str,
        author_id: uuid.UUID | None,
        from_admin: bool,
    ) -> SupportMessage:
        """Suma un mensaje y mueve el estado del hilo.

        El estado lo decide quien escribe: si contesta el equipo queda
        `respondido`, y si vuelve a escribir la persona vuelve a `abierto`. Asi
        la bandeja del administrador se ordena sola por lo que falta contestar.
        """
        mensaje = SupportMessage(
            thread_id=hilo.id,
            body=body,
            author_id=author_id,
            from_admin=from_admin,
        )
        self._db.add(mensaje)
        hilo.status = SupportStatus.RESPONDIDO if from_admin else SupportStatus.ABIERTO
        self._db.flush()
        self._db.refresh(mensaje)
        #La coleccion del hilo ya venia cargada de la consulta, asi que no se
        #entera del mensaje nuevo. Se marca como caducada para que se relea al
        #devolver el hilo; sin esto la respuesta llega con un mensaje de menos.
        self._db.expire(hilo, ["messages"])
        return mensaje

    def cambiar_estado(self, hilo: SupportThread, status: SupportStatus) -> SupportThread:
        hilo.status = status
        self._db.flush()
        return hilo
