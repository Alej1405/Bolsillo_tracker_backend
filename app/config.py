from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file = '.env',
        env_file_encoding = 'utf-8'
        )

    database_url: str
    secret_key: SecretStr
    algorithm: str = 'HS256'
    access_token_expire_hours: int = 24

    #correo saliente (Resend). La clave es SecretStr para que no salga impresa
    #en un traceback ni en un repr de Settings.
    resend_api_key: SecretStr
    #remitente. El dominio tiene que estar verificado en Resend o el envio se
    #rechaza con 403.
    resend_from: str = 'Bolsillo <hola@mashaec.net>'

    #carpeta donde se guardan las fotos de perfil. Fuera del codigo a proposito:
    #en el servidor apunta a un disco que sobrevive a cada despliegue.
    media_dir: str = 'media'
    #tope por foto. Una foto de perfil se ve en 200 px; 2 MB es de sobra y evita
    #que alguien suba un archivo de camara de 40 MB y llene el disco.
    avatar_max_mb: int = 2

settings = Settings()