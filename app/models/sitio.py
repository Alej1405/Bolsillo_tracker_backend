"""Ajustes del sitio: lo que la landing muestra y el super_admin edita.

Las dos tablas tienen una sola fila con id fijo en 1. No hay varias sedes ni
varias cuentas de TikTok, y un CHECK en la base impide que aparezca una segunda.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, Text, func, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SiteContact(Base):
    """El telefono, el correo y la direccion que aparecen en la web."""

    __tablename__ = "site_contact"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(Text, nullable=True)
    instagram: Mapped[str | None] = mapped_column(Text, nullable=True)
    tiktok: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TiktokConfig(Base):
    """Las credenciales de TikTok y las llaves de la sesion autorizada.

    `client_secret`, `access_token` y `refresh_token` no salen nunca por la API:
    los endpoints dicen si estan puestos, no cuanto valen.
    """

    __tablename__ = "tiktok_config"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    client_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    open_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TiktokVideo(Base):
    """Un video traido de TikTok. Se guarda para no preguntar en cada visita."""

    __tablename__ = "tiktok_videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    video_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embed_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
