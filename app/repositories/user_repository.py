import uuid
from sqlalchemy import func, select

#importando atributos de sql
from sqlalchemy.orm import Session
#importando el modelo de Usuario
from app.models.user import User
from sqlalchemy import literal
from app.repositories.consultas import normalizado, paginar, parecido_a, relevancia

class UserRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_by_email(self, email: str)-> User | None:
        stmt = select(User).where(User.email == email)
        return self._db.scalars(stmt).first()
    
    #creando el usuario
    def create(self, full_name: str, email: str, password_hash: str) -> User:
        usuario = User(full_name=full_name, email=email, password_hash=password_hash) #crea el usuario con los datos en memoria
        self._db.add(usuario)                           #no hace el insert solo crea el pendiente
        self._db.flush()                                #hace el insert en la dbb y devuelve el id
        return usuario                                  #devuelve el objeto que creamos

    def list_paginated(
        self,
        page: int,
        page_size: int,
        is_active: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[User], int]:
        """
        Los usuarios que cumplen los filtros, y cuantos son en total.

        `q` busca a la vez en el nombre y en el correo, sin distinguir tildes
        ni mayusculas y perdonando erratas. La expresion es la misma que se
        indexo en db/11_busqueda.sql: nombre y correo concatenados, para que
        una sola comparacion cubra los dos campos.
        """
        filtros = []
        if is_active is not None:
            filtros.append(User.is_active == is_active)

        # nombre + correo, ya normalizados, igual que en el indice
        buscable = normalizado(User.full_name) + literal(" ") + normalizado(User.email)
        if q and q.strip():
            filtros.append(parecido_a(buscable, q.strip().lower()))

        total = self._db.scalar(select(func.count(User.id)).where(*filtros))

        stmt = select(User).where(*filtros)
        if q and q.strip():
            # lo mas parecido primero; a igual parecido, lo mas reciente
            stmt = stmt.order_by(
                relevancia(buscable, q.strip().lower()).desc(), User.created_at.desc()
            )
        else:
            stmt = stmt.order_by(User.created_at.desc())

        stmt = paginar(stmt, page, page_size)
        return list(self._db.scalars(stmt).all()), total

    def get_by_id(self, user_id: uuid.UUID, ) -> User | None :
        return self._db.get(User, user_id)

    def update_name(self, usuario: User, full_name: str) -> User:
        usuario.full_name = full_name
        self._db.flush()
        return usuario

    def update_password_hash(self, usuario: User, password_hash: str) -> User:
        usuario.password_hash = password_hash
        self._db.flush()
        return usuario

    def set_avatar(self, usuario: User, avatar_url: str | None) -> User:
        """Guarda la ruta de la foto. Con None la quita."""
        usuario.avatar_url = avatar_url
        self._db.flush()
        return usuario

    def set_active(self, usuario: User, is_active: bool) -> User:
        usuario.is_active = is_active
        self._db.flush()
        return usuario

    def delete(self, usuario: User) -> None:
        self._db.delete(usuario)
        self._db.flush()
        return