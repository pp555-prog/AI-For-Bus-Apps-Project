from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DATABASE_PATH: str = "./nocturne.db"
    SUNO_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    HIGGSFIELD_API_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
