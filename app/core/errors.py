class DomainError(Exception):
    "error del domininio"
    code = "INTERNAL_ERROR"
    status = 500

class EmailAlreadyExist(DomainError):
    "ya existe el email"
    code = "CONFLICT"
    status = 409


class AccountDeactivated(DomainError):
    "cuenta desactivada"
    code = "ACCOUNT_DEACTIVATED"
    status = 409


class InvalidCredentials(DomainError):
    "correo o contrasena incorrectos"
    code = "UNAUTHORIZED"
    status = 401


class TokenExpired(DomainError):
    "el token vencio, hay que volver a iniciar sesion"
    code = "TOKEN_EXPIRED"
    status = 401


class Forbidden(DomainError):
    "el recurso existe pero es de otro usuario o exige otro rol"
    code = "FORBIDDEN"
    status = 403


class NotFound(DomainError):
    "el recurso no existe"
    code = "NOT_FOUND"
    status = 404


class ValidationError(DomainError):
    "datos mal formados que no cubre pydantic"
    code = "VALIDATION_ERROR"
    status = 400

#------- account

class AccountNameTaken(DomainError):
    "ya existe una cuenta con ese nombre para este usuario"
    code = "CONFLICT"
    status = 409

class AccountInUse(DomainError):
    "la cuenta tiene movimientos y no se puede borrar"
    code = "IN_USE"
    status = 409


class BusinessRule(DomainError):
    "los datos son validos pero rompen una regla del negocio"
    code = "BUSINESS_RULE"
    status = 422


# --- categorias ---

class SystemCategoryReadOnly(DomainError):
    "las categorias precargadas son de todos, nadie las edita ni las archiva"
    code = "FORBIDDEN"
    status = 403


class CategoryNameTaken(DomainError):
    "ya existe una categoria con ese nombre bajo el mismo padre"
    code = "CONFLICT"
    status = 409


class CategoryInUse(DomainError):
    "la categoria tiene transacciones y no se puede archivar"
    code = "IN_USE"
    status = 409


class InvalidCategoryParent(DomainError):
    "el padre no existe, ya es una subcategoria, o es de otro kind"
    code = "BUSINESS_RULE"
    status = 422