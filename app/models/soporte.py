"""Modelos de las conversaciones de soporte.

Un hilo agrupa los mensajes de una consulta. Puede ser de un usuario con cuenta
o de alguien que escribio desde el formulario de la landing sin tenerla: en ese
caso `user_id` es NULL y quedan su nombre y su correo.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID, ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SupportStatus(str, enum.Enum):
    ABIERTO = "abierto"
    RESPONDIDO = "respondido"
    CERRADO = "cerrado"


class SupportThread(Base):
    __tablename__ = "support_threads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    guest_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    guest_email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SupportStatus] = mapped_column(
        PGEnum(
            SupportStatus,
            name="support_status",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        server_default="abierto",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    #Los mensajes vienen en orden de llegada y se borran con el hilo.
    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="SupportMessage.created_at",
    )
    user = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<SupportThread {self.subject!r} {self.status}>"


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_threads.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #Si lo escribio el equipo. Se guarda y no se deduce del rol del autor porque
    #el rol puede cambiar despues, y entonces los mensajes viejos cambiarian de
    #lado en la conversacion.
    from_admin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    thread: Mapped[SupportThread] = relationship(back_populates="messages")
    author = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<SupportMessage {'equipo' if self.from_admin else 'usuario'}>"
