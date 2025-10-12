from pathlib import Path
from pydantic_settings import BaseSettings

class MeshGenSettings(BaseSettings):
    # Paths to pre-trained weights
    AUTOENCODER_PATH: Path = Path("./mesh_generator/model_chk/mesh-encoder_16k_4_2.pt")
    TRANSFORMER_PATH: Path = Path("./mesh_generator/model_chk/mesh-transformer_16k_4_2.pt")

    OUTPUT_DIR: Path = Path("./raw_meshes")

    DEVICE: str = "cuda"

    # If True, generator will attempt to reuse an existing asset for the same category in a scene
    REUSE_IF_EXISTS: bool = True

    # Target face count for simplified collision mesh (Not needed imo)
    # Note to self: Remove collision mesh function
    COLLISION_TARGET_FACES: int = 200

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = MeshGenSettings()

