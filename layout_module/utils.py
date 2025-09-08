import json
from pathlib import Path
from .config import settings
from .models import SceneManifest

def save_manifest(manifest: SceneManifest, out_dir: Path = None):
    out_dir = out_dir or settings.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{manifest.scene_id}_scene_manifest.json"
    with open(out_path, "w") as f:
        f.write(manifest.model_dump_json(indent=2))
    return out_path

def load_manifest(path: Path):
    with open(path, "r") as f:
        data = json.load(f)
    return SceneManifest.model_validate(data)
