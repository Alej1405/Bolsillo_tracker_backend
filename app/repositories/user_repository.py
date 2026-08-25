import uuid
from sqlalchemy import func, select

#importando atributos de sql
from sqlalchemy.orm import Session
#importando el modelo de Usuario
from app.models.user import User

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

    def list_paginated(self, page: int, page_size: int, is_active: bool | None = None) -> tuple[list[User], int] :
        """devuelve el total de los usuarios que cumplen con los filtros"""
        filtros = []
        if is_active is not None:
            filtros.append(User.is_active == is_active)

        total = self._db.scalar(select(func.count(User.id)).where(*filtros))

        stmt = (
            select(User)
            .where(*filtros)
            .order_by(User.created_at.desc())
            .limit(page_size)
            .offset( (page - 1) * page_size)
        )
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

    def set_active(self, usuario: User, is_active: bool) -> User:
        usuario.is_active = is_active
        self._db.flush()
        return usuario

    def delete(self, usuario: User) -> None:
        self._db.delete(usuario)
        self._db.flush()
        return