from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama defaults
    LLM_BASE_URL_OLLAMA: str = "http://localhost:11434/api/generate"
    LLM_MODEL: str = "gpt-oss:120b"
    LLM_BASE_URL_DEEPSEEK: str = "https://api.deepseek.com"
    DEEPSEEK_KEY: str = "sk-d3a04397262d4362b6cbd6fc6b6e5172"
    OUTPUT_DIR: Path = Path("./output")
    DEFAULT_CLEARANCE: float = 0.4  # meters - minimum walkway
    DEFAULT_WALL_CLEARANCE: float = 0.15

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
