"""Ajustes del sitio y la conexion con TikTok.

Dos cosas distintas en un servicio porque las dos son "lo que el super_admin
configura y la landing muestra": los datos de contacto y los videos.

La parte de TikTok habla con una API externa. Todo lo que sale a internet vive
aqui y no en el repositorio, que solo sabe de la base.
"""

from datetime import datetime, timedelta, timezone

import httpx

from app.core.errors import ValidationError
from app.models.sitio import SiteContact, TiktokConfig
from app.repositories.sitio_repository import SitioRepository

#Los tres extremos de la Display API. Estan aqui juntos para que se vea de un
#vistazo con quien habla el servidor.
TIKTOK_TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_AUTORIZAR = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_VIDEOS = "https://open.tiktokapis.com/v2/video/list/"
TIKTOK_USUARIO = "https://open.tiktokapis.com/v2/user/info/"

#Lo que se le pide a TikTok: leer el perfil y la lista de videos. Nada de
#publicar ni de borrar — la aplicacion solo muestra.
TIKTOK_PERMISOS = "user.info.basic,video.list"

#Los campos de cada video que interesan para la landing.
TIKTOK_CAMPOS = "id,title,cover_image_url,share_url,embed_link,duration,create_time"


class SitioService:
    """Lo que el administrador configura y la web muestra."""

    def __init__(self, repo: SitioRepository):
        self._repo = repo

    # ── contacto ─────────────────────────────────────────────────────────

    def contacto(self) -> SiteContact:
        """Los datos que enseña la landing. Publico: no exige sesion."""
        return self._repo.contacto()

    def actualizar_contacto(self, cambios: dict) -> SiteContact:
        """Solo lo que venga: un PATCH no borra lo que no menciona."""
        return self._repo.actualizar_contacto(cambios)

    # ── tiktok: configuracion ────────────────────────────────────────────

    def estado_tiktok(self) -> dict:
        """Como esta la conexion, sin soltar ningun secreto.

        Devuelve si hay credenciales y si la cuenta esta autorizada, nunca los
        valores: un secreto que sale por la API una vez ya esta fuera.
        """
        c = self._repo.tiktok()
        return {
            "configured": bool(c.client_key and c.client_secret),
            "connected": bool(c.access_token),
            "client_key": c.client_key,
            "display_name": c.display_name,
            "open_id": c.open_id,
            "expires_at": c.expires_at,
            "synced_at": c.synced_at,
            "videos": len(self._repo.videos(solo_visibles=False, limite=100)),
        }

    def guardar_credenciales(self, client_key: str, client_secret: str) -> dict:
        """Las llaves que da TikTok al registrar la aplicacion.

        Cambiarlas invalida la autorizacion anterior: los tokens que habia
        pertenecen a la aplicacion vieja, asi que se limpian para que el estado
        no diga "conectado" cuando ya no lo esta.
        """
        self._repo.actualizar_tiktok(
            {
                "client_key": client_key.strip(),
                "client_secret": client_secret.strip(),
                "access_token": None,
                "refresh_token": None,
                "expires_at": None,
                "open_id": None,
                "display_name": None,
            }
        )
        return self.estado_tiktok()

    def url_de_autorizacion(self, redirect_uri: str, state: str) -> str:
        """A donde mandar al administrador para que autorice la cuenta.

        `state` viaja de ida y vuelta sin que TikTok lo toque: al volver se
        comprueba que sea el mismo. Sirve para que nadie pueda provocar la
        vuelta del flujo desde fuera con un enlace preparado.
        """
        c = self._repo.tiktok()
        if not c.client_key:
            raise ValidationError("Falta la clave de la aplicacion de TikTok")

        from urllib.parse import urlencode

        parametros = urlencode(
            {
                "client_key": c.client_key,
                "scope": TIKTOK_PERMISOS,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        return f"{TIKTOK_AUTORIZAR}?{parametros}"

    # ── tiktok: el intercambio de llaves ─────────────────────────────────

    def canjear_codigo(self, code: str, redirect_uri: str) -> dict:
        """Cambia el codigo que devuelve TikTok por las dos llaves.

        El `access_token` sirve para pedir datos y dura horas; el
        `refresh_token` sirve para conseguir otro y dura mucho mas. Se guardan
        los dos: sin el segundo habria que volver a autorizar a mano cada dia.
        """
        c = self._repo.tiktok()
        self._exigir_credenciales(c)

        datos = self._pedir_token(
            {
                "client_key": c.client_key,
                "client_secret": c.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )
        self._guardar_tokens(datos)
        self._traer_perfil()
        return self.estado_tiktok()

    def renovar(self) -> TiktokConfig:
        """Pide un token nuevo con el de refresco. Silencioso, sin intervencion."""
        c = self._repo.tiktok()
        self._exigir_credenciales(c)
        if not c.refresh_token:
            raise ValidationError("TikTok todavia no esta conectado")

        datos = self._pedir_token(
            {
                "client_key": c.client_key,
                "client_secret": c.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": c.refresh_token,
            }
        )
        return self._guardar_tokens(datos)

    def desconectar(self) -> dict:
        """Olvida la autorizacion. Las credenciales de la aplicacion se quedan."""
        self._repo.actualizar_tiktok(
            {
                "access_token": None,
                "refresh_token": None,
                "expires_at": None,
                "open_id": None,
                "display_name": None,
                "synced_at": None,
            }
        )
        return self.estado_tiktok()

    # ── tiktok: los videos ───────────────────────────────────────────────

    def videos_publicos(self, limite: int = 12) -> list:
        """Lo que muestra la landing. Sale de la base, no de TikTok.

        Se guarda y se sirve desde aqui porque la landing la ve cualquiera y la
        API tiene limites de uso: mil visitas serian mil llamadas por el mismo
        dato, y el dia que TikTok corte, la web se queda sin seccion.
        """
        return self._repo.videos(solo_visibles=True, limite=limite)

    def todos_los_videos(self) -> list:
        """Los guardados, visibles o no. Para el panel del administrador."""
        return self._repo.videos(solo_visibles=False, limite=100)

    def sincronizar(self) -> dict:
        """Trae los ultimos videos de TikTok y los guarda.

        Renueva el token antes si esta a punto de caducar: pedirlo con uno
        vencido devuelve un error que no dice nada util al administrador.
        """
        c = self._repo.tiktok()
        self._exigir_credenciales(c)
        if not c.access_token:
            raise ValidationError("TikTok todavia no esta conectado")

        if c.expires_at and c.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
            c = self.renovar()

        try:
            with httpx.Client(timeout=20) as cliente:
                r = cliente.post(
                    TIKTOK_VIDEOS,
                    params={"fields": TIKTOK_CAMPOS},
                    headers={"Authorization": f"Bearer {c.access_token}"},
                    json={"max_count": 20},
                )
        except httpx.HTTPError as exc:
            raise ValidationError(f"No pudimos hablar con TikTok: {exc}") from exc

        cuerpo = self._leer(r)
        videos = (cuerpo.get("data") or {}).get("videos") or []

        for v in videos:
            self._repo.guardar_video(
                {
                    "video_id": str(v.get("id")),
                    "title": v.get("title"),
                    "cover_url": v.get("cover_image_url"),
                    "share_url": v.get("share_url"),
                    "embed_link": v.get("embed_link"),
                    "duration": v.get("duration"),
                    "published_at": (
                        datetime.fromtimestamp(v["create_time"], tz=timezone.utc)
                        if v.get("create_time")
                        else None
                    ),
                }
            )

        self._repo.actualizar_tiktok({"synced_at": datetime.now(timezone.utc)})
        return {"traidos": len(videos), **self.estado_tiktok()}

    def mostrar_video(self, video_id: str, visible: bool):
        """Esconde o vuelve a mostrar un video sin borrarlo ni resincronizar."""
        video = self._repo.video_por_id(video_id)
        if video is None:
            raise ValidationError("Ese video no esta guardado")
        return self._repo.ocultar_video(video, visible)

    # ── lo de dentro ─────────────────────────────────────────────────────

    @staticmethod
    def _exigir_credenciales(c: TiktokConfig) -> None:
        if not (c.client_key and c.client_secret):
            raise ValidationError(
                "Faltan las credenciales de TikTok. Ponlas en el panel antes de conectar"
            )

    def _pedir_token(self, datos: dict) -> dict:
        """La llamada al extremo de tokens. Los dos flujos la usan igual."""
        try:
            with httpx.Client(timeout=20) as cliente:
                r = cliente.post(
                    TIKTOK_TOKEN,
                    data=datos,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.HTTPError as exc:
            raise ValidationError(f"No pudimos hablar con TikTok: {exc}") from exc
        return self._leer(r)

    def _guardar_tokens(self, datos: dict) -> TiktokConfig:
        expira = datetime.now(timezone.utc) + timedelta(seconds=int(datos.get("expires_in", 0)))
        return self._repo.actualizar_tiktok(
            {
                "access_token": datos.get("access_token"),
                "refresh_token": datos.get("refresh_token"),
                "expires_at": expira,
                "open_id": datos.get("open_id"),
            }
        )

    def _traer_perfil(self) -> None:
        """El nombre de la cuenta autorizada, para que el panel diga cual es."""
        c = self._repo.tiktok()
        try:
            with httpx.Client(timeout=20) as cliente:
                r = cliente.get(
                    TIKTOK_USUARIO,
                    params={"fields": "open_id,display_name,avatar_url"},
                    headers={"Authorization": f"Bearer {c.access_token}"},
                )
            cuerpo = self._leer(r)
            usuario = (cuerpo.get("data") or {}).get("user") or {}
            self._repo.actualizar_tiktok({"display_name": usuario.get("display_name")})
        except Exception:
            #El nombre es un adorno del panel: si falla, la conexion sigue valida.
            pass

    @staticmethod
    def _leer(r: httpx.Response) -> dict:
        """Interpreta la respuesta de TikTok y convierte su error en uno nuestro.

        TikTok devuelve 200 con un `error` dentro del cuerpo en varios casos, asi
        que no basta con mirar el codigo HTTP.
        """
        try:
            cuerpo = r.json()
        except ValueError:
            raise ValidationError(f"TikTok respondio algo que no es JSON ({r.status_code})")

        error = cuerpo.get("error")
        #En el extremo de tokens el error viene plano; en los demas, como objeto.
        if isinstance(error, dict) and error.get("code") not in (None, "ok"):
            raise ValidationError(f"TikTok: {error.get('message') or error.get('code')}")
        if isinstance(error, str) and error:
            raise ValidationError(f"TikTok: {cuerpo.get('error_description') or error}")
        if r.status_code >= 400:
            raise ValidationError(f"TikTok respondio {r.status_code}")
        return cuerpo
