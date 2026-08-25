import logging

#importando modulos de fastapi
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.errors import DomainError

logger = logging.getLogger(__name__)

CODIGOS_POR_STATUS = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "BUSINESS_RULE",
    500: "INTERNAL_ERROR"
}

MENSAJES_POR_STATUS = {
    401: "No autorizado",
    403: "No tienes permiso para realizar esta operación",
    404: "No se encontró el recurso solicitado",
    405: "Método no permitido",
}

def _cuerpo(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}

async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details =[
        {"field": ".".join(str(p) for p in error["loc"][1:]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=400,
        content=_cuerpo("VALIDATION_ERROR", "Los datos no son validos", details)
    )

async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = CODIGOS_POR_STATUS.get(exc.status_code, "INTERNAL_ERROR")
    mensaje = MENSAJES_POR_STATUS.get(exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_cuerpo(code, mensaje)
    )

async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=_cuerpo("INTERNAL_ERROR", "Error inesperado intenta luego")
    )

async def domain_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.status,
        content=_cuerpo(exc.code, str(exc)),
    )