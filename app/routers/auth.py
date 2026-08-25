"""Endpoints de autenticacion: registro, inicio de sesion y perfil propio.

Los routers solo reciben, delegan y responden. Los errores de negocio suben
como DomainError y los traduce domain_handler.

Las fabricas de dependencias (get_auth_service, get_token_manager) se movieron
a app/core/dependencies.py porque ahora las usan dos routers.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_auth_service, get_current_user, get_token_manager
from app.core.security import TokenManager
from app.models.user import User
from app.schemas.user import RegisterResponse, UserCreate, UserLogin, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _respuesta_con_token(usuario: User, tokens: TokenManager) -> RegisterResponse:
    """Arma la respuesta comun de register y login (misma forma segun el contrato)."""
    return RegisterResponse(
        user=UserRead.model_validate(usuario),
        access_token=tokens.create_access_token(usuario.id),
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una cuenta",
)
def register(
    datos: UserCreate,
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
    tokens: TokenManager = Depends(get_token_manager),
):
    usuario = service.register(datos)
    db.commit()
    return _respuesta_con_token(usuario, tokens)


@router.post(
    "/login",
    response_model=RegisterResponse,
    summary="Iniciar sesion",
)
def login(
    datos: UserLogin,
    service: AuthService = Depends(get_auth_service),
    tokens: TokenManager = Depends(get_token_manager),
):
    #sin commit: iniciar sesion no modifica nada en la base
    return _respuesta_con_token(service.login(datos), tokens)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Perfil del usuario autenticado",
)
def me(usuario: User = Depends(get_current_user)):
    #get_current_user ya hizo todo el trabajo: leer el token, validarlo y cargar el usuario
    return usuario
