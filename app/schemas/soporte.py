"""Lo que entra y sale de /support.

El contrato en ingles como el resto. Los textos que ve la persona van en
español, pero eso es cosa del frontend.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.soporte import SupportStatus


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    #: Si lo escribio el equipo. Es lo que decide de que lado va en pantalla.
    from_admin: bool
    created_at: datetime


class ThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    status: SupportStatus
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead] = []


class ThreadAdminRead(ThreadRead):
    """Lo mismo, y ademas de quien es. Solo para el administrador."""

    user_id: uuid.UUID | None = None
    guest_name: str | None = None
    guest_email: str | None = None


class ThreadCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=1, max_length=4000)


class GuestThreadCreate(ThreadCreate):
    """Lo que manda el formulario de contacto de la landing.

    Pide nombre y correo porque quien escribe puede no tener cuenta, y sin una
    forma de contestarle el mensaje no sirve de nada.
    """

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ThreadListPage(BaseModel):
    items: list[ThreadAdminRead]
    page: int
    page_size: int
    total: int
    total_pages: int
    #: Cuantos esperan respuesta. Es el numero que enseña el panel.
    pending: int
