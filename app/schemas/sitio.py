"""Lo que entra y sale de /site y /site/tiktok."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContactRead(BaseModel):
    """Lo que muestra la landing. Es publico: no exige sesion."""

    model_config = ConfigDict(from_attributes=True)

    phone: str | None = None
    email: str | None = None
    address: str | None = None
    schedule: str | None = None
    whatsapp: str | None = None
    instagram: str | None = None
    tiktok: str | None = None


class ContactUpdate(BaseModel):
    """Todos opcionales: un PATCH no borra lo que no menciona."""

    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=200)
    schedule: str | None = Field(default=None, max_length=120)
    whatsapp: str | None = Field(default=None, max_length=40)
    instagram: str | None = Field(default=None, max_length=120)
    tiktok: str | None = Field(default=None, max_length=120)


class TiktokCredentials(BaseModel):
    """Las llaves que da TikTok al registrar la aplicacion."""

    client_key: str = Field(min_length=4, max_length=200)
    client_secret: str = Field(min_length=4, max_length=200)


class TiktokStatus(BaseModel):
    """Como esta la conexion. Nunca incluye el secreto ni los tokens."""

    #: Si estan puestas las credenciales de la aplicacion.
    configured: bool
    #: Si hay una cuenta autorizada.
    connected: bool
    client_key: str | None = None
    display_name: str | None = None
    open_id: str | None = None
    expires_at: datetime | None = None
    synced_at: datetime | None = None
    videos: int = 0


class TiktokSynced(TiktokStatus):
    #: Cuantos videos trajo la ultima sincronizacion.
    traidos: int = 0


class TiktokAuthUrl(BaseModel):
    """A donde mandar al administrador para autorizar la cuenta."""

    url: str
    state: str


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    video_id: str
    title: str | None = None
    cover_url: str | None = None
    share_url: str | None = None
    embed_link: str | None = None
    duration: int | None = None
    published_at: datetime | None = None
    visible: bool = True


class VideoVisibility(BaseModel):
    visible: bool


class VideoPorEnlace(BaseModel):
    """Un video anadido pegando su enlace, sin conectar la cuenta."""

    url: str = Field(min_length=10, max_length=400)
