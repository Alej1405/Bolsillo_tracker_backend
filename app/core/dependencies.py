"""Dependencias compartidas por todos los routers.

Aqui se arman los objetos que los endpoints necesitan (repositorios, servicios,
usuario autenticado) para que las rutas solo reciban, deleguen y respondan.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.errors import Forbidden, InvalidCredentials
from app.core.security import PasswordHasher, TokenManager
from app.models.user import User, UserRole
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.services.account_service import AccountService
from app.services.auth_service import AuthService
from app.services.category_service import CategoryService
from app.services.email_service import EmailService
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService

#auto_error=False para que la falta de token la manejemos nosotros y salga
#como 401 UNAUTHORIZED con el formato del contrato, no con el de FastAPI
bearer = HTTPBearer(auto_error=False)


def get_password_hasher() -> PasswordHasher:
    return PasswordHasher()


def get_token_manager() -> TokenManager:
    return TokenManager(
        settings.secret_key.get_secret_value(),
        settings.algorithm,
        settings.access_token_expire_hours,
    )


def get_email_service() -> EmailService:
    return EmailService(
        settings.resend_api_key.get_secret_value(),
        settings.resend_from,
    )


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> AuthService:
    return AuthService(repo, hasher)


def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> UserService:
    return UserService(repo, hasher)


def get_account_service(db: Session = Depends(get_db)) -> AccountService:
    return AccountService(AccountRepository(db))


def get_category_service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(CategoryRepository(db))


def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    #dos repositorios: los movimientos y las cuentas que hay que validar
    return TransactionService(TransactionRepository(db), AccountRepository(db))


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    return ReportService(
        ReportRepository(db), TransactionRepository(db), AccountRepository(db)
    )


def get_current_user(
    credenciales: HTTPAuthorizationCredentials | None = Depends(bearer),
    tokens: TokenManager = Depends(get_token_manager),
    repo: UserRepository = Depends(get_user_repository),
) -> User:
    """Lee el JWT del header Authorization y devuelve el usuario dueno del token.

    Es la puerta de entrada de todo endpoint protegido: si algo falla aqui,
    la peticion nunca llega al endpoint.
    """
    if credenciales is None:
        raise InvalidCredentials("No autorizado")

    user_id = tokens.read_access_token(credenciales.credentials)

    usuario = repo.get_by_id(user_id)
    if usuario is None:
        #el token es valido pero el usuario ya no existe (lo borro el admin)
        raise InvalidCredentials("No autorizado")

    if not usuario.is_active:
        #se dio de baja despues de que se emitiera el token
        raise InvalidCredentials("No autorizado")

    return usuario


def require_super_admin(usuario: User = Depends(get_current_user)) -> User:
    """Igual que get_current_user, pero exige rol super_admin."""
    if usuario.role != UserRole.SUPER_ADMIN:
        raise Forbidden("No tienes permiso para realizar esta operacion")
    return usuario
