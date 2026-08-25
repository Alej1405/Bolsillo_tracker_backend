#aqui configuramos el modelo del cliente 
#importando del orm 
import uuid
import enum

from datetime import datetime
#importando propiedades del orm
from sqlalchemy import Text, DateTime, text, func
#dialecto o interprete de postgress
from sqlalchemy.dialects.postgresql import UUID, CITEXT, ENUM as PGEnum
#propiedades del orm
from sqlalchemy.orm import Mapped, mapped_column

#importando la clase principal
from app.core.database import Base

#clase que define los roles de los usuarios y clientes
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    CLIENT = "client"

#descripcion de la tabla para poder modelar el usuario
class User(Base):
    __tablename__ = "users"

    #columnas de la tabla usuarios en postgres
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    email: Mapped[str] = mapped_column(
        CITEXT, unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        PGEnum(
            UserRole,
            name="user_role",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        server_default="client",
    )
    is_active: Mapped[bool] = mapped_column(
        server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self)-> str:
        return f"<User {self.email}>"

#probar que todo funciona
# if __name__ == "__main__":
#     print("tabla:", User.__tablename__)
#     print("columnas: ", [c.name for c in User.__table__.columns] )