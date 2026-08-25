#import para hashear el password
import bcrypt

#import para el token key
from datetime import timedelta, datetime, timezone
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.errors import InvalidCredentials, TokenExpired

class PasswordHasher:
    def __init__ (self, rounds: int = 12):
        self._rounds = rounds

    def hash(self, password: str)-> str:
        salt = bcrypt.gensalt(rounds=self._rounds)
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify(self, password: str, password_hash:str ) -> bool:
        return bcrypt.checkpw(password.encode(), password_hash.encode())

class TokenManager:
    #emite y valida los tokens
    def __init__(self, secret_key: str, algorithm: str = "HS256", expire_hours: int = 24 ):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expire_hours = expire_hours

    def create_access_token(self, user_id: str) -> str:
        ahora = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "iat": ahora,
            "exp": ahora+timedelta(hours=self._expire_hours),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def read_access_token(self, token: str) -> str:
        """Valida la firma y la expiracion, y devuelve el id del usuario (el claim sub)."""
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except ExpiredSignatureError:
            #la libreria comprueba 'exp' sola: aqui solo lo traducimos al lenguaje del dominio
            raise TokenExpired("La sesion expiro. Vuelve a iniciar sesion.")
        except JWTError:
            #firma invalida, token manipulado o mal formado
            raise InvalidCredentials("Token invalido")

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidCredentials("Token invalido")
        return user_id