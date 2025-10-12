from pathlib import Path
from pydantic_settings import BaseSettings

class TextureSettings(BaseSettings):
    OUTPUT_DIR: Path = Path("./textured_assets")
    FAST_MODEL_ID: str = "dream-textures/texture-diffusion"  # diffusers model id
    DEVICE: str = "cuda"
    # TEXTurePaper (Path to the external codebase for the repo)
    TEXTUREPAPER_RUN_CMD: str = r"C:/Users/koth_ak/Akshat's Thesis/TEXTurePaper/.venv/Scripts/python.exe-./scripts/run_texture.py"
    TEXTUREPAPER_EXPERIMENTS_DIR: Path = Path("C:/Users/koth_ak/Akshat's Thesis/TEXTurePaper/experiments")
    WORKDIR: str = "C:/Users/koth_ak/Akshat's Thesis/TEXTurePaper"
    CFG_DIR: str = "C:/Users/koth_ak/Akshat's Thesis/TEXTurePaper/configs/text_guided"

settings = TextureSettings()
