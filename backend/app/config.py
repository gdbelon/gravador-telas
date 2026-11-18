import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações da aplicação carregadas de variáveis de ambiente e/ou arquivo .env
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./processos.db"
    BASE_URL: str = "http://localhost:8000"
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
