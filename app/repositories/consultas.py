"""
Piezas de consulta que usan varios repositorios.

Existe por una razon concreta: `Transaction.deleted_at IS NULL` estaba escrito
en cinco archivos y ocho sitios distintos. Es la condicion que sostiene el
borrado logico de toda la aplicacion, y basta con que UNO de esos sitios se
olvide para que un movimiento borrado reaparezca en un reporte, en un saldo o
en las estadisticas del panel de administracion.

Eso no se nota al escribirlo: se nota cuando las cifras no cuadran y nadie sabe
por que. Aqui esta una vez y se importa.
"""

from sqlalchemy import Select, String, func, literal, or_
from sqlalchemy.sql.elements import ColumnElement

from app.models.transaction import Transaction


def vivos() -> ColumnElement[bool]:
    """
    El filtro del borrado logico.

    Se usa en TODA consulta que lea movimientos. Un movimiento borrado conserva
    su fila —el historial no se pierde— pero deja de contar en saldos, reportes
    y estadisticas, y eso solo se cumple si nadie se salta esta condicion.
    """
    return Transaction.deleted_at.is_(None)


def paginar(consulta: Select, page: int, page_size: int) -> Select:
    """
    Aplica el salto y el limite de una pagina.

    El calculo `(page - 1) * page_size` estaba repetido en tres repositorios,
    y en uno de ellos con un espacio de mas dentro del parentesis: la clase de
    detalle que delata que se copio a mano.

    `page` empieza en 1, no en 0, porque es lo que ve quien consume la API.
    """
    return consulta.offset((page - 1) * page_size).limit(page_size)


# =============================================================================
#  Busqueda
# =============================================================================
#  Migracion db/11_busqueda.sql. Las dos funciones de abajo tienen que producir
#  EXACTAMENTE la misma expresion que se indexo alli: si difieren en una sola
#  llamada, PostgreSQL no puede usar el indice y vuelve a recorrer la tabla
#  entera sin avisar de nada.
# =============================================================================


def normalizado(columna):
    """
    Minusculas y sin tildes, igual que el indice.

    Es lo que permite que "maria" encuentre "Maria" y "alimentacion" encuentre
    "Alimentacion": la comparacion se hace sobre el texto ya normalizado a
    ambos lados.
    """
    #  `type_=String` no es decoracion: sin el, SQLAlchemy trata el resultado
    #  como tipo desconocido, el `+` deja de significar concatenacion y el
    #  operador de trigramas no se puede componer con un OR.
    return func.inmutable_unaccent(
        func.lower(func.coalesce(columna, "")), type_=String
    )


def parecido_a(expresion, texto: str) -> ColumnElement[bool]:
    """
    Coincidencia por trigramas: tolera tildes, mayusculas y erratas.

    El operador `%` de pg_trgm compara los grupos de tres letras de las dos
    cadenas y devuelve verdadero si comparten los suficientes. A diferencia de
    `ILIKE '%texto%'`, esta condicion SI usa el indice GIN.

    Se combina con `ILIKE` por un caso que los trigramas resuelven mal: los
    textos de una o dos letras no llegan a formar trigramas propios, y una
    busqueda de "ma" no devolveria nada. Con el `OR`, lo corto sigue
    funcionando aunque para eso recorra.
    """
    #  `bool_op` y no `op`: SQLAlchemy no sabe que el `%` de pg_trgm devuelve
    #  un booleano, y sin decirselo compone el OR con un operando de tipo text
    #  y PostgreSQL rechaza la consulta entera.
    #  `self_group()` pone los parentesis. Sin el, PostgreSQL lee
    #      a || ' ' || (b % 'texto')
    #  porque `%` liga mas fuerte que `||`, y el WHERE acaba recibiendo un
    #  texto donde esperaba un booleano. Es el mismo tropiezo que hay que
    #  evitar al escribir la consulta a mano en SQL.
    agrupada = expresion.self_group()

    #  El texto BUSCADO tambien se normaliza. Parece obvio y es el fallo mas
    #  facil de cometer: la columna esta sin tildes y la busqueda llega con
    #  ellas, asi que "andres" encuentra y "andrés" no. Los dos lados o
    #  ninguno.
    aguja = func.inmutable_unaccent(func.lower(literal(texto)), type_=String)

    #  `%>` y no `%`: compara con la PALABRA mas parecida dentro del texto, no
    #  con el texto entero. Sobre "maria guerrero maria.guerrero@ejemplo.com"
    #  la similitud de "lusia" contra toda la cadena queda por debajo del
    #  umbral solo porque la cadena es larga; contra cada palabra, no.
    return or_(agrupada.bool_op("%>")(aguja), agrupada.ilike(func.concat("%", aguja, "%")))


def relevancia(expresion, texto: str):
    """
    Cuanto se parece, de 0 a 1. Sirve para ordenar: primero lo mas parecido.

    Sin esto la lista sale en el orden que tenga la tabla, y quien busca
    "maria" puede ver a "Mario" antes que a "Maria".
    """
    #  `word_similarity` para que case con la condicion de arriba: ordenar por
    #  una medida distinta de la que filtra da resultados en desorden.
    return func.word_similarity(
        func.inmutable_unaccent(func.lower(literal(texto)), type_=String), expresion
    )
