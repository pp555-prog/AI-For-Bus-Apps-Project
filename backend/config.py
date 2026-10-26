from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM routing — OpenRouter (OpenAI-compatible API; routes to any model)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-oss-120b:free"
    OPENROUTER_VIDEO_MODEL: str = "bytedance/seedance-2.0"
    OPENROUTER_VIDEO_RESOLUTION: str = "720p"
    OPENROUTER_VIDEO_DURATION: int = 10
    OPENROUTER_VIDEO_ASPECT_RATIO: str = "16:9"
    OPENROUTER_MUSIC_MODEL: str = "google/lyria-3-pro-preview"
    OPENROUTER_AUDIO_MODEL: str = "google/gemini-2.5-flash"
    OPENROUTER_VISION_MODEL: str = "google/gemini-2.5-flash"
    FFMPEG_PATH: str = "ffmpeg"

    # Legacy / unused (kept so old .env files don't fail validation)
    ANTHROPIC_API_KEY: str = ""

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DATABASE_PATH: str = "./nocturne.db"
    N8N_CLOUD_WORKSPACE_URL: str = ""
    N8N_BOOKING_WEBHOOK: str = ""
    SUNO_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    HIGGSFIELD_API_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
