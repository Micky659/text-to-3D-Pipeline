from texture_module import generate_texture_image, apply_texture_to_obj, write_texturepaper_yaml, run_texturepaper_with_config, settings as texture_settings
import datetime
from pathlib import Path


def _run_texturing_on_manifest(manifest_dict: dict, texture_mode: str, scene_id: str):
    out_dir_scene = Path(texture_settings.OUTPUT_DIR) / scene_id
    out_dir_scene.mkdir(parents=True, exist_ok=True)

    for obj in manifest_dict.get("objects", []):
        tex_prompt = None
        # priority: object's texture_input (from edit) > style_hint + category
        if obj.get("retexture_input"):
            tex_prompt = obj["retexture_input"]
        elif obj.get("style_hint"):
            tex_prompt = f"{obj['style_hint']} texture for {obj['category']}"
        else:
            tex_prompt = f"{obj['category']} material texture"

        raw_asset = obj.get("asset")
        if not raw_asset:
            continue

        raw_asset_path = Path(raw_asset)
        out_dir = out_dir_scene / obj['category']
        out_dir.mkdir(parents=True, exist_ok=True)

        # generate texture image and map it
        if texture_mode == "gen_and_map":
            # fast generation
            img_path = generate_texture_image(prompt=tex_prompt, out_dir=out_dir)
            textured_obj = out_dir / f"{raw_asset_path.stem}_textured_{datetime.datetime.now().strftime('%m_%d__%H_%M_%S')}.obj"
            apply_texture_to_obj(str(raw_asset_path), str(img_path), str(textured_obj))
            # update manifest
            prev = obj.get("asset")
            obj["asset"] = str(textured_obj.resolve())
            obj_meta = obj.get("metadata", {}) or {}
            obj_meta["textured_by"] = "fast_gen_and_map"
            obj_meta["texture_image"] = str(img_path.resolve())
            obj["metadata"] = obj_meta
            manifest_dict["metadata"].setdefault("provenance", []).append({
                "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                "placement_id": obj.get("id"),
                "action": "textured",
                "method": "gen_and_map",
                "texture_image": str(img_path)
            })
        # run TEXTurePaper
        elif texture_mode == "diffusion":

            exp_name = f"{obj['category']}_{datetime.datetime.now().strftime('%m_%d__%H_%M_%S')}"
            # write yaml: text template uses style and object name
            text_template = f"A {obj.get('style_hint','') } {obj['category']}, {{}} view"
            cfg_path = write_texturepaper_yaml(exp_name, str(raw_asset_path), text_template, seed=42)
            res = run_texturepaper_with_config(cfg_path)
            # copy produced files into texture output folder
            mesh_obj = Path(res["mesh_obj"])
            albedo = res["albedo"]
            mtl = res["mtl"]
            final_mesh = out_dir / f"{obj['category']}_{datetime.datetime.now().strftime('%m_%d__%H_%M_%S')}_textured.obj"
            import shutil
            shutil.copy2(mesh_obj, final_mesh)
            if albedo:
                shutil.copy2(albedo, out_dir / Path(albedo).name)
            if mtl:
                shutil.copy2(mtl, out_dir / Path(mtl).name)
            prev = obj.get("asset")
            obj["asset"] = str(final_mesh.resolve())
            obj_meta = obj.get("metadata", {}) or {}
            obj_meta["textured_by"] = "TEXTurePaper"
            obj_meta["texture_image"] = str(albedo) if albedo else None
            obj["metadata"] = obj_meta
            manifest_dict["metadata"].setdefault("provenance", []).append({
                "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                "placement_id": obj.get("id"),
                "action": "textured",
                "method": "TEXTurePaper",
                "experiment": str(exp_name)
            })

    return manifest_dict
