from texture_module import generate_texture_image, apply_texture_to_obj, write_texturepaper_yaml, run_texturepaper_with_config, settings as texture_settings
import datetime
from pathlib import Path
import shutil


def _retexture_single_mesh(obj: dict, texture_mode: str, scene_id: str):
    """
    Retexture a single mesh object and update its asset path to the textured version.
    Modifies obj["asset"] in-place with the textured asset path from texture module.
    Returns provenance entry for tracking.
    """
    tex_prompt = None
    # priority: object's retexture_input (from edit) > style_hint + category
    out_dir_scene = Path(texture_settings.OUTPUT_DIR) / scene_id
    out_dir_scene.mkdir(parents=True, exist_ok=True)

    if obj.get("retexture_input"):
        tex_prompt = obj["retexture_input"]
    elif obj.get("style_hint"):
        tex_prompt = f"{obj['style_hint']} texture for {obj['category']}"
    else:
        tex_prompt = f"{obj['category']} material texture"

    raw_asset = obj.get("asset")
    if not raw_asset:
        return None

    raw_asset_path = Path(raw_asset)
    out_dir = out_dir_scene / obj['category'] / raw_asset_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    provenance_entry = {
        "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
        "placement_id": obj.get("id"),
        "action": "textured",
    }

    if texture_mode == "gen_and_map":
        img_path = generate_texture_image(prompt=tex_prompt, out_dir=out_dir)
        textured_obj = out_dir / f"{raw_asset_path.stem}_textured.obj"
        apply_texture_to_obj(str(raw_asset_path), str(img_path), str(textured_obj))

        # Update asset to textured path from texture module
        textured_asset_path = str(textured_obj.resolve())
        obj["asset"] = textured_asset_path

        obj_meta = obj.get("metadata", {}) or {}
        obj_meta["textured_by"] = "fast_gen_and_map"
        obj_meta["texture_image"] = str(img_path.resolve())
        obj["metadata"] = obj_meta

        provenance_entry.update({
            "method": "gen_and_map",
            "texture_image": str(img_path),
            "textured_asset": textured_asset_path
        })

    elif texture_mode == "diffusion":
        exp_name = f"{obj['category']}_{datetime.datetime.now().strftime('%m_%d__%H_%M_%S')}"
        text_template = f"A {obj.get('style_hint', '')} {obj['category']}, {{}} view"
        cfg_path = write_texturepaper_yaml(exp_name, str(raw_asset_path), text_template, seed=42)
        res = run_texturepaper_with_config(cfg_path)

        mesh_obj = Path(res["mesh_obj"])
        albedo = res["albedo"]
        mtl = res["mtl"]
        final_mesh = out_dir / f"{obj['category']}_{datetime.datetime.now().strftime('%m_%d__%H_%M_%S')}_textured.obj"

        shutil.copy2(mesh_obj, final_mesh)
        if albedo:
            shutil.copy2(albedo, out_dir / Path(albedo).name)
        if mtl:
            shutil.copy2(mtl, out_dir / Path(mtl).name)

        # Update asset to textured path from texture module
        textured_asset_path = str(final_mesh.resolve())
        obj["asset"] = textured_asset_path

        obj_meta = obj.get("metadata", {}) or {}
        obj_meta["textured_by"] = "TEXTurePaper"
        obj_meta["texture_image"] = str(albedo) if albedo else None
        obj["metadata"] = obj_meta

        provenance_entry.update({
            "method": "TEXTurePaper",
            "experiment": str(exp_name),
            "textured_asset": textured_asset_path
        })

    return provenance_entry, obj


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
        out_dir = out_dir_scene / obj['category'] / raw_asset_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        # generate texture image and map it
        if texture_mode == "gen_and_map":
            # fast generation
            img_path = generate_texture_image(prompt=tex_prompt, out_dir=out_dir)
            textured_obj = out_dir / f"{raw_asset_path.stem}_textured.obj"
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
