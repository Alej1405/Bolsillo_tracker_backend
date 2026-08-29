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

settings = Settings()