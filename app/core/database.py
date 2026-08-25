#aqui configuramos la conexion de la base de datos
# bloques de engenie para la base de datos
from sqlalchemy import create_engine
#importar la configuracion del evn
from app.config import settings
#importar la fabirca de sesion con orm
from sqlalchemy.orm import sessionmaker, DeclarativeBase

#forma minima solo con url 
#engine = create_engine(settings.database_url, echo=True)

#Bloque_1 forma completa controlando el tamano del pool
engine = create_engine(
    settings.database_url,
    pool_size=5,        #conexiones permanentes
    max_overflow=10,    #Conexiones temporales si hay picos de trafico
    echo=True,         #muestra el Sql por cosola es mas por control.
)

#bloque_2 creamos como se van a realizar las conexciones
SessionLocal = sessionmaker(
    bind=engine,                #a que motor se conecta
    autoflush=False,            #No envia el sql sin que yo lo pida.
    expire_on_commit=False,     #Evita que se los objetos se recarguen cuando el objeto se devuelve.
)

#Bloque_3
#clase principal que heredara propiedades a las demas
class Base(DeclarativeBase):
    pass

#bloque_4
#Ejecuta todo anterior y utiliza los generadores
def get_db():
    db = SessionLocal() #fabircar o crear la conexion
    #try finally garantiza que la conexion se cierre aun que exista errores
    try:
        yield db  #entrega la peticion pero en pausa hasta recibir confirmacion
    finally:
        db.close()