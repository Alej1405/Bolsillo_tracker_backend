"""Acceso a datos de los ajustes del sitio y de TikTok.

Las dos configuraciones son una fila con id 1. `obtener` la crea si no existe,
para que el resto del codigo nunca tenga que comprobar si hay o no fila.

Ningun metodo hace commit.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sitio import SiteContact, TiktokConfig, TiktokVideo


class SitioRepository:
    def __init__(self, db: Session):
        self._db = db

    # ── contacto ─────────────────────────────────────────────────────────

    def contacto(self) -> SiteContact:
        """La fila de contacto. La crea vacia la primera vez."""
        fila = self._db.get(SiteContact, 1)
        if fila is None:
            fila = SiteContact(id=1)
            self._db.add(fila)
            self._db.flush()
        return fila

    def actualizar_contacto(self, cambios: dict) -> SiteContact:
        fila = self.contacto()
        for campo, valor in cambios.items():
            setattr(fila, campo, valor)
        self._db.flush()
        return fila

    # ── tiktok ───────────────────────────────────────────────────────────

    def tiktok(self) -> TiktokConfig:
        fila = self._db.get(TiktokConfig, 1)
        if fila is None:
            fila = TiktokConfig(id=1)
            self._db.add(fila)
            self._db.flush()
        return fila

    def actualizar_tiktok(self, cambios: dict) -> TiktokConfig:
        fila = self.tiktok()
        for campo, valor in cambios.items():
            setattr(fila, campo, valor)
        self._db.flush()
        return fila

    # ── videos ───────────────────────────────────────────────────────────

    def videos(self, solo_visibles: bool = True, limite: int = 12) -> list[TiktokVideo]:
        """Los videos guardados, del mas nuevo al mas viejo."""
        stmt = select(TiktokVideo)
        if solo_visibles:
            stmt = stmt.where(TiktokVideo.visible)
        stmt = stmt.order_by(TiktokVideo.published_at.desc().nullslast()).limit(limite)
        return list(self._db.scalars(stmt).all())

    def video_por_id(self, video_id: str) -> TiktokVideo | None:
        stmt = select(TiktokVideo).where(TiktokVideo.video_id == video_id)
        return self._db.scalars(stmt).first()

    def guardar_video(self, datos: dict) -> TiktokVideo:
        """Crea el video o actualiza el que ya estaba.

        Volver a sincronizar no duplica: `video_id` es UNIQUE y aqui se busca
        antes de insertar.
        """
        video = self.video_por_id(datos["video_id"])
        if video is None:
            video = TiktokVideo(**datos)
            self._db.add(video)
        else:
            for campo, valor in datos.items():
                setattr(video, campo, valor)
        self._db.flush()
        return video

    def borrar_video(self, video: TiktokVideo) -> None:
        self._db.delete(video)
        self._db.flush()

    def ocultar_video(self, video: TiktokVideo, visible: bool) -> TiktokVideo:
        video.visible = visible
        self._db.flush()
        return video
