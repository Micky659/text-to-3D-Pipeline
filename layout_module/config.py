from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl  # still available in v2


class Settings(BaseSettings):
    # Ollama defaults
    LLM_BASE_URL: str = "http://localhost:11434/api/generate"
    LLM_MODEL: str = "llama3.1:8b"
    OUTPUT_DIR: Path = Path("./output")
    DEFAULT_CLEARANCE: float = 0.6  # meters - minimum walkway

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
