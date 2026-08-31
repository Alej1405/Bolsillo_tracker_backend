#aqui gestionamos el esquema de los datos es decir lo que recibimos y los que entregamos
#importando los atributos necesario
import uuid
from datetime import datetime

#importando la funcion de roles
from app.models.user import UserRole

#importando paydantic, el trductor de jason
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, ValidationError

#funcion que valida los password, para reutilizar
def _validar_password(v: str) ->str:
    #validamos si tiene almenos una letra
    if not any(c.isalpha() for c in v):
        raise ValueError("Debe contener al menos una letra")

    #validamos que al menos tenga un nuemro
    if not any(c.isdigit() for c in v):
        raise ValueError("Debe contener al menos un numero")
    
    return v

#lo que llega del navegador, lo que entra
class UserCreate(BaseModel):
    full_name: str = Field(max_length=120, min_length=2)
    email: EmailStr
    password: str = Field(max_length=72, min_length=8)
    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str)-> str:
        return _validar_password(v)

#lo que llega en el login: sin reglas de formato, solo se compara contra el hash
class UserLogin(BaseModel):
    email: EmailStr
    password: str

#lo que sale, la respuesta que se envia
class UserRead(BaseModel):
    #permite que los datos sean compatibles y los objetos se puedan leer
    model_config = ConfigDict(from_attributes=True)

    #Datos del diccionario u objeto que vamos a entregar
    full_name: str
    email: EmailStr
    role: UserRole
    id: uuid.UUID
    created_at: datetime
    #ruta de la foto, relativa al servidor ("/media/avatares/xxx.jpg"). Es None
    #mientras no suba ninguna, y entonces la interfaz muestra las iniciales.
    avatar_url: str | None = None

#clase que actualiza el usuario
class UserUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)

#cambiar de contrasena
class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)
    @field_validator("new_password")
    @classmethod
    def validar_password(cls, v:str) -> str:
        return _validar_password(v)

#clase que heredada de user read y agrega un campo
class UserAdminRead(UserRead):
    is_active:  bool

#clase para ver el estado de una actualizacion
class UserStatusUpdate(BaseModel):
    is_active: bool

#clase que lista a los usuarios
class UserListPage(BaseModel):
    items: list[UserAdminRead]
    page: int
    page_size: int
    total: int
    total_pages: int

#clase que envia la respuesta del registro al frontend
class RegisterResponse(BaseModel):
    user: UserRead
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400

#probando que el esquema funcione---------------------------------------------------
if __name__ == "__main__":
    import uuid
    from datetime import datetime

    datos_ok = {
        "full_name": "Ana Perez",
        "email": "ana@ejemplo.com",
        "password": "unaClaveSegura123",
    }

    print("=" * 60)
    print("1) UserCreate — caso valido")
    print("=" * 60)
    usuario = UserCreate(**datos_ok)
    print("  OK ->", usuario.full_name, "|", usuario.email)

    print()
    print("=" * 60)
    print("2) UserCreate — casos que DEBEN fallar")
    print("=" * 60)
    casos_malos = [
        ("nombre muy corto", {**datos_ok, "full_name": "A"}),
        ("email invalido", {**datos_ok, "email": "no-es-correo"}),
        ("password corta", {**datos_ok, "password": "abc123"}),
        ("password sin numero", {**datos_ok, "password": "claveseguraaa"}),
        ("password sin letra", {**datos_ok, "password": "123456789"}),
    ]
    for descripcion, datos in casos_malos:
        try:
            UserCreate(**datos)
            print(f"  {descripcion:<22} -> PASO (no deberia)")
        except ValidationError as e:
            error = e.errors()[0]
            print(f"  {descripcion:<22} -> {error['loc'][0]}: {error['msg']}")

    print()
    print("=" * 60)
    print("3) UserRead — leer desde un objeto (from_attributes)")
    print("=" * 60)

    class UsuarioFalso:
        """Imita un objeto User de SQLAlchemy, con hash incluido."""

        id = uuid.uuid4()
        full_name = "Ana Perez"
        email = "ana@ejemplo.com"
        password_hash = "$2b$12$" + "x" * 53
        role= "client"
        created_at = datetime.now()

    salida = UserRead.model_validate(UsuarioFalso())
    print(salida.model_dump_json(indent=2))
    print("  password_hash en la salida?", "password_hash" in salida.model_dump())

    print()
    print("=" * 60)
    print("4) RegisterResponse — respuesta completa")
    print("=" * 60)
    respuesta = RegisterResponse(user=salida, access_token="eyJhbGciOiJIUzI1NiIs...")
    print(respuesta.model_dump_json(indent=2))
