# mesh_generator/generator.py
import torch
from pathlib import Path
from .config import settings
from .utils import save_obj_from_coords, load_mesh, compute_metadata
from .data_scripts import mesh_render
import os
import shutil
import time
import glob
import trimesh

class MeshGenerator:
    def __init__(self,
                 autoencoder_path: Path = None,
                 transformer_path: Path = None,
                 device: str = None):
        self.autoencoder_path = autoencoder_path or settings.AUTOENCODER_PATH
        self.transformer_path = transformer_path or settings.TRANSFORMER_PATH
        self.device = (device or settings.DEVICE)
        self._loaded = False
        self._load_models()

    def _load_models(self):
        # Lazy import of repo model classes, assumes model code is importable from your project
        from mesh_generator.model_scripts.autoencoder import MeshAutoencoder
        from mesh_generator.model_scripts.transformer import MeshTransformer

        print("Loading autoencoder from", self.autoencoder_path)
        ae_pkg = torch.load(str(self.autoencoder_path), map_location=self.device)
        # configure autoencoder with same args used in training; if different, adjust accordingly
        self.autoencoder = MeshAutoencoder(
            decoder_dims_through_depth=(128,) * 6 + (192,) * 12 + (256,) * 24 + (384,) * 6,
            codebook_size=16384,
            dim_codebook=192,
            dim_area_embed=16,
            dim_coor_embed=16,
            dim_normal_embed=16,
            dim_angle_embed=8,
            attn_decoder_depth=4,
            attn_encoder_depth=2
        ).to(self.device)
        self.autoencoder.load_state_dict(ae_pkg['model'])
        self.autoencoder.eval()

        print("Loading transformer from", self.transformer_path)
        tr_pkg = torch.load(str(self.transformer_path), map_location=self.device)
        # instantiate transformer (params must match saved model)
        self.transformer = MeshTransformer(
            self.autoencoder,
            dim=768,
            coarse_pre_gateloop_depth=3,
            fine_pre_gateloop_depth=3,
            attn_depth=12,
            attn_heads=12,
            max_seq_len=4602,
            condition_on_text=True,
            gateloop_use_heinsen=False,
            dropout=0.0,
            text_condition_model_types="bge",
            text_condition_cond_drop_prob=0.0
        ).to(self.device)
        self.transformer.load_state_dict(tr_pkg['model'])
        self.transformer.eval()
        self._loaded = True

    def _ensure_scene_dir(self, scene_id: str) -> Path:
        out_dir = Path(settings.OUTPUT_DIR) / str(scene_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _find_existing_asset(self, scene_dir: Path, category: str):
        # Look for files named {category}*.glb or .obj
        patt = str(scene_dir / f"{category}*")
        for ext in [".glb", ".gltf", ".obj", ".ply"]:
            files = sorted(glob.glob(patt + ext))
            if files:
                return Path(files[0])
        # try json fallback
        return None

    def generate_asset(self, category: str, text: str = None, scene_id: str = "default_scene",
                       reuse: bool = True, temperature: float = 0.0) -> dict:
        """
        Generate a mesh asset for `category` (optionally guiding with `text`), store it in raw_meshes/{scene_id}/
        Returns a dict with keys: asset_path (glb), metadata (dict), collision_path (optional)
        """
        if not self._loaded:
            self._load_models()

        scene_dir = self._ensure_scene_dir(scene_id)
        # If reuse requested, check existing
        if reuse and settings.REUSE_IF_EXISTS:
            found = self._find_existing_asset(scene_dir, category)
            if found:
                # compute metadata if not present or load sidecar json
                try:
                    mesh = load_mesh(found)
                    metadata = compute_metadata(mesh)
                    return {"asset_path": str(found.resolve()), "metadata": metadata}
                except Exception:
                    # continue to regenerate if reading fails
                    pass

        # call transformer to generate (the transformer API from repo example)
        txt = text or category
        with torch.no_grad():
            print(f"Generating category='{category}' text='{txt}' ...")
            # the repository's transformer.generate returns coordinates used by mesh_render.save_rendering
            raw_mesh = self.transformer.generate(texts=[txt], temperature=temperature)
            # raw_mesh is a coords object or list; try to save to OBJ
            timestamp = int(time.time() * 1000)
            out_obj = scene_dir / f"{category}_{timestamp}.obj"
            # saved = save_obj_from_coords([raw_mesh], out_obj)
            mesh_render.save_rendering(str(out_obj), [raw_mesh])
            # if not saved:
            #     # if failed to create obj, still create sidecar JSON and return
            #     # but attempt to load fallback json (save_obj_from_coords wrote .json)
            #     fallback_json = out_obj.with_suffix(".json")
            #     if fallback_json.exists():
            #         return {"asset_path": str(fallback_json.resolve()), "metadata": {"note": "coords_json_saved"}}
            #     raise RuntimeError("Failed to save generated mesh to OBJ or JSON.")

        # load created mesh
        mesh = load_mesh(out_obj)
        # compute metadata
        metadata = compute_metadata(mesh)

        # create collision mesh (simplify)
        try:
            target = settings.COLLISION_TARGET_FACES
            if len(mesh.faces) > target:
                collision = mesh.simplify_quadratic_decimation(target)
            else:
                collision = mesh.copy()
            collision_path = scene_dir / f"{category}_{timestamp}_collision.obj"
            collision.export(str(collision_path))
        except Exception as e:
            collision_path = None

        # convert/save glb
        try:
            glb_path = scene_dir / f"{category}_{timestamp}.glb"
            mesh.export(str(glb_path))
        except Exception as e:
            # fallback to OBJ if glb export fails
            glb_path = out_obj

        return {
            "asset_path": str(glb_path.resolve()),
            "metadata": metadata,
            "collision_path": str(collision_path.resolve()) if collision_path else None
        }
