from app.core.errors import AccountDeactivated, EmailAlreadyExist, InvalidCredentials
from app.core.security import PasswordHasher
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserLogin

class AuthService:
    def __init__ (self, repo: UserRepository, hasher: PasswordHasher):
        self._repo = repo
        self._hasher = hasher

    def register(self, datos:UserCreate) -> User:
        #valida y crea un usuario si el emial no existe
        existente = self._repo.get_by_email(datos.email)
        if existente:
            if not existente.is_active:
                raise AccountDeactivated("Esta cuenta fue desactivada. Contacta al administrador")
            raise EmailAlreadyExist("El correo ya esta registrado")
        usuario = self._repo.create(full_name=datos.full_name, email=datos.email, password_hash=self._hasher.hash(datos.password))
        return usuario

    def login(self, datos: UserLogin) -> User:
        """Comprueba correo y contrasena. Devuelve el usuario o lanza InvalidCredentials.

        El mensaje es el mismo para "no existe el correo" y "la contrasena esta mal":
        distinguirlos permitiria averiguar que correos estan registrados.
        """
        usuario = self._repo.get_by_email(datos.email)
        if usuario is None:
            raise InvalidCredentials("Correo o contrasena incorrectos")

        if not self._hasher.verify(datos.password, usuario.password_hash):
            raise InvalidCredentials("Correo o contrasena incorrectos")

        if not usuario.is_active:
            raise AccountDeactivated("Esta cuenta fue desactivada. Contacta al administrador")

        return usuario