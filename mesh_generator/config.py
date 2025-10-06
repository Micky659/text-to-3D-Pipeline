# mesh_generator/config.py
from pathlib import Path
from pydantic_settings import BaseSettings

class MeshGenSettings(BaseSettings):
    # Paths to pre-trained weights (edit to match your layout)
    AUTOENCODER_PATH: Path = Path("./mesh_generator/model_chk/mesh-encoder_16k_4_2.pt")
    TRANSFORMER_PATH: Path = Path("./mesh_generator/model_chk/mesh-transformer_16k_4_2.pt")

    # Where to put raw generated meshes organized by scene
    OUTPUT_DIR: Path = Path("./raw_meshes")

    # device: "cuda" or "cpu"
    DEVICE: str = "cuda"

    # If True, generator will attempt to reuse an existing asset for the same category in a scene
    REUSE_IF_EXISTS: bool = True

    # Target face count for simplified collision mesh (approx)
    COLLISION_TARGET_FACES: int = 200

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = MeshGenSettings()

