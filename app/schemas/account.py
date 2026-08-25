#esquema de cuentas 
#importando modulos basicos
import uuid
from decimal import Decimal
from datetime import datetime

#importando la funcion de los tipo de cuenta
from app.models.account import AccountType

#importando el traductor de JSON
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError

class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    type: AccountType
    initial_balance: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    icon: str | None = None
    color: str | None = None

class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    icon: str | None = None
    color: str | None = None

class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:uuid.UUID
    name: str
    type: AccountType
    currency: str
    initial_balance: Decimal
    balance: Decimal
    icon: str | None
    color: str | None
    archived_at: datetime | None
    created_at: datetime

class AccountListResponse(BaseModel):
    items: list[AccountRead]
    total_balance: Decimal