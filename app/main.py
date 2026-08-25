from fastapi import FastAPI
from app.routers import accounts, auth, categories, reports, transactions, users
from app.core.errors import DomainError

#control de cors
from fastapi.middleware.cors import CORSMiddleware

#importando los handler para el manejo de errores
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

#importando los handler desde el core.
from app.core.exception_handlers import http_handler, unhandled_handler, validation_handler, domain_handler

#montamos el app
app = FastAPI(title="Registro de gastos", version="1.0.0")

#permitir el consumo de la api manejando los cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

#agregamos la validacion de errores
app.add_exception_handler(RequestValidationError, validation_handler)
app.add_exception_handler(StarletteHTTPException, http_handler)
app.add_exception_handler(DomainError, domain_handler)
app.add_exception_handler(Exception, unhandled_handler)

#ejecutamos los routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(transactions.transfers_router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")