"""Endpoints de los ajustes del sitio y de TikTok.

Lo publico y lo privado conviven aqui porque son el mismo dato visto desde dos
lados: la landing lee, el super_admin escribe.

  · GET  /site/contact         publico, lo lee la landing
  · PATCH /site/contact        solo super_admin
  · GET  /site/videos          publico, los videos de la seccion de TikToks
  · /site/tiktok/...           solo super_admin: credenciales, conexion y sincronizacion
"""

import secrets

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_sitio_service, require_super_admin
from app.models.user import User
from app.schemas.sitio import (
    ContactRead,
    ContactUpdate,
    TiktokAuthUrl,
    TiktokCredentials,
    TiktokStatus,
    TiktokSynced,
    VideoPorEnlace,
    VideoRead,
    VideoVisibility,
)
from app.services.sitio_service import SitioService

router = APIRouter(prefix="/site", tags=["site"])


# ── publico: lo que consume la landing ───────────────────────────────────

@router.get("/contact", response_model=ContactRead, summary="Datos de contacto (publico)")
def contacto(service: SitioService = Depends(get_sitio_service)):
    #sin sesion a proposito: la landing la ve cualquiera
    return service.contacto()


@router.get("/videos", response_model=list[VideoRead], summary="Videos de TikTok (publico)")
def videos(
    limite: int = Query(12, ge=1, le=50),
    service: SitioService = Depends(get_sitio_service),
):
    """Los que se muestran en la seccion de TikToks.

    Salen de la base y no de TikTok: la landing la ve cualquiera y la API tiene
    limites de uso. Ademas, si TikTok se cae, la seccion sigue en pie.
    """
    return service.videos_publicos(limite)


# ── administracion ───────────────────────────────────────────────────────

@router.patch(
    "/contact",
    response_model=ContactRead,
    summary="Cambiar los datos de contacto (solo super_admin)",
)
def actualizar_contacto(
    datos: ContactUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    #exclude_unset: solo lo que vino en el cuerpo. Sin esto, un PATCH con un
    #solo campo borraria los demas al mandarlos como None.
    actualizado = service.actualizar_contacto(datos.model_dump(exclude_unset=True))
    db.commit()
    return actualizado


@router.get(
    "/tiktok",
    response_model=TiktokStatus,
    summary="Estado de la conexion con TikTok (solo super_admin)",
)
def estado_tiktok(
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    return service.estado_tiktok()


@router.put(
    "/tiktok/credentials",
    response_model=TiktokStatus,
    summary="Guardar las credenciales de TikTok (solo super_admin)",
)
def credenciales(
    datos: TiktokCredentials,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    """Las llaves que da TikTok al registrar la aplicacion.

    El secreto no vuelve a salir por la API: el estado dice si esta puesto, no
    cuanto vale.
    """
    estado = service.guardar_credenciales(datos.client_key, datos.client_secret)
    db.commit()
    return estado


@router.get(
    "/tiktok/authorize",
    response_model=TiktokAuthUrl,
    summary="Empezar la autorizacion de TikTok (solo super_admin)",
)
def autorizar(
    redirect_uri: str = Query(..., description="La misma URL registrada en TikTok"),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    """Devuelve a donde hay que mandar al navegador para autorizar la cuenta.

    El `state` se genera aqui y se devuelve para que el frontend lo guarde y lo
    compare al volver: es lo que impide que alguien provoque la vuelta del flujo
    con un enlace preparado desde fuera.
    """
    state = secrets.token_urlsafe(24)
    return {"url": service.url_de_autorizacion(redirect_uri, state), "state": state}


@router.post(
    "/tiktok/callback",
    response_model=TiktokStatus,
    summary="Terminar la autorizacion de TikTok (solo super_admin)",
)
def callback(
    code: str = Query(..., description="El codigo que devuelve TikTok"),
    redirect_uri: str = Query(..., description="La misma que se uso al autorizar"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    estado = service.canjear_codigo(code, redirect_uri)
    db.commit()
    return estado


@router.post(
    "/tiktok/sync",
    response_model=TiktokSynced,
    summary="Traer los ultimos videos de TikTok (solo super_admin)",
)
def sincronizar(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    resultado = service.sincronizar()
    db.commit()
    return resultado


@router.delete(
    "/tiktok",
    response_model=TiktokStatus,
    summary="Desconectar la cuenta de TikTok (solo super_admin)",
)
def desconectar(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    estado = service.desconectar()
    db.commit()
    return estado


@router.get(
    "/tiktok/videos",
    response_model=list[VideoRead],
    summary="Todos los videos guardados (solo super_admin)",
)
def videos_admin(
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    """Incluye los escondidos, que la landing no muestra."""
    return service.todos_los_videos()


@router.post(
    "/tiktok/videos",
    response_model=VideoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un video pegando su enlace (solo super_admin)",
)
def agregar_video(
    datos: VideoPorEnlace,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    """El camino corto: no hace falta conectar la cuenta ni tener credenciales.

    El titulo y la portada salen del oEmbed publico de TikTok, que funciona con
    cualquier video publico sin autorizacion de nadie.
    """
    video = service.agregar_por_enlace(datos.url)
    db.commit()
    return video


@router.delete(
    "/tiktok/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar un video de la lista (solo super_admin)",
)
def quitar_video(
    video_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    """Lo borra de la web. En TikTok sigue donde estaba."""
    service.quitar_video(video_id)
    db.commit()


@router.patch(
    "/tiktok/videos/{video_id}",
    response_model=VideoRead,
    summary="Mostrar o esconder un video (solo super_admin)",
)
def visibilidad(
    video_id: str,
    datos: VideoVisibility,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
    service: SitioService = Depends(get_sitio_service),
):
    video = service.mostrar_video(video_id, datos.visible)
    db.commit()
    return video
