from layout_module.llm_client import LLMClient
from layout_module.models import Room, SceneManifest
from layout_module.utils import save_manifest, load_manifest
from layout_module.asset_registry import load_categories
from layout_module.config import settings
from .input_interpreter_agent import InputInterpreterAgent, Interpretation, Intent
from .layout_planner_agent import LayoutPlannerAgent
from .scene_editor_agent import SceneEditorAgent
from texture_module import _run_texturing_on_manifest
from mesh_generator.generator import MeshGenerator
import uuid
import datetime
import time
from pathlib import Path
import os


class Orchestrator:
    def __init__(self, llm_mode, categories_path, texture_mode):
        self.llm_client = LLMClient(llm_mode=llm_mode)
        self.interpreter = InputInterpreterAgent(self.llm_client, category_path=categories_path)
        self.layout_planner = LayoutPlannerAgent(self.llm_client, categories=load_categories(categories_path))
        self.mesh_generator = MeshGenerator()
        self.texture_mode = texture_mode
        self.scene_editor = SceneEditorAgent(self.llm_client, categories_path)

    def handle_request(self, user_text: str, scene_id: str = None):
        start_time = time.time()
        interp: Interpretation = self.interpreter.interpret(user_text)
        print("INTERPRETATION:", interp.model_dump_json(indent=2))
        if interp.intent == Intent.GENERATE:
            room_dict = interp.room or {"w": "auto", "d": "auto", "h": "auto"}
            if room_dict.get("w") == "auto":
                room_defaults = {"w": 6.0, "d": 8.0, "h": 3.5}
            else:
                room_defaults = {"w": float(room_dict.get("w", 6.0)), "d": float(room_dict.get("d", 8.0)),
                                 "h": float(room_dict.get("h", 3.0))}
            room = Room(**room_defaults)
            req_list = []
            for o in interp.objects:
                for i in range(o.count):
                    req_list.append(o.category)
            relationships = interp.relationships or ""
            scene_id = scene_id or interp.scene_id or f"scene_{uuid.uuid4().hex[:2]}"
            res = self.layout_planner.plan(scene_id, room, req_list, relationships=relationships,
                                           style=interp.style or "default")
            if not res.get("ok"):
                # failed to produce valid layout
                return {"status": "error", "reason": "layout_generation_failed", "details": res.get("error")}
            print("LAYOUT: ", res)
            manifest = res["manifest"]

            # Generate assets (unique categories only) and annotate manifest
            unique_cats = {}
            for obj in manifest.objects:
                cat = obj.category
                if cat not in unique_cats:
                    print(f"Requesting generation for category: {cat}")
                    try:
                        asset_info = self.mesh_generator.generate_asset(cat, text=cat, scene_id=scene_id, reuse=True)
                        unique_cats[cat] = asset_info
                    except Exception as e:
                        print("Generation failed for", cat, e)
                        unique_cats[cat] = None

            # Attach asset_path & metadata to each placement instance
            for obj in manifest.objects:
                info = unique_cats.get(obj.category)
                if info:
                    obj_dict = obj.model_dump()
                    obj_dict["asset"] = info["mesh_path"]
                    obj_dict["metadata"] = info.get("metadata", {})
                else:
                    obj_dict = obj.model_dump()
                    obj_dict["asset"] = None
                    obj_dict["metadata"] = {}

            # Rebuild manifest.objects as list of dicts
            new_objs = []
            for obj in manifest.objects:
                info = unique_cats.get(obj.category)
                objd = obj.model_dump()
                if info:
                    objd["asset"] = info["mesh_path"]
                    objd["metadata"] = info.get("metadata", {})
                else:
                    objd["asset"] = None
                    objd["metadata"] = {}
                new_objs.append(objd)



            manifest_dict = manifest.model_dump()
            manifest_dict["objects"] = new_objs

            manifest_dict = _run_texturing_on_manifest(manifest_dict, texture_mode=self.texture_mode, scene_id=scene_id)
            end_time = time.time()
            elapsed_time = round(end_time - start_time, 2)
            manifest_dict["inference_time"] = elapsed_time
            # Save the manifest JSON
            out_path = save_manifest(manifest)  # note: this saves original manifest; prefer to save modified manifest
            # overwrite with modified manifest
            import json
            out_file = out_path.parent / out_path.name
            with open(out_file, "w") as f:
                json.dump(manifest_dict, f, indent=2)

            return {"status": "ok", "manifest_path": str(out_file)}

        elif interp.intent == Intent.EDIT:
            # require scene_id
            if not interp.scene_id:
                return {"status": "error", "reason": "no_scene_id_for_edit"}
            # load existing manifest
            existing_manifest = load_manifest(Path(settings.OUTPUT_DIR) / f"{interp.scene_id}_scene_manifest.json")
            edit_instruction = interp.raw_text if hasattr(interp, "raw_text") else interp.user_text
            edit_res = self.scene_editor.edit(existing_manifest.model_dump(), edit_instruction)
            if not edit_res.get("ok"):
                return {"status": "error", "reason": "edit_failed", "details": edit_res.get("error")}
            updated_manifest = edit_res["manifest"]
            if "metadata" not in updated_manifest:
                updated_manifest["metadata"] = {}
            if "provenance" not in updated_manifest["metadata"]:
                updated_manifest["metadata"]["provenance"] = []

            scene_dir = Path("raw_meshes") / interp.scene_id
            scene_dir.mkdir(parents=True, exist_ok=True)

            for obj in updated_manifest.get("objects", []):
                placement_id = obj.get("id")
                regenerate_flag = bool(obj.get("regenerate", False))
                texture_input = obj.get("retexture_input", None)

                if regenerate_flag:
                    prev_asset = obj.get("asset", None)
                    try:
                        # Use a higher temperature for regeneration to add variation
                        regen_info = self.mesh_generator.generate_asset(obj.get("category"), text=obj.get("category"),
                                                                        scene_id=interp.scene_id, reuse=False,
                                                                        temperature=0.15)
                        # Update object asset and metadata with new values
                        new_asset = regen_info.get("mesh_path")
                        new_meta = regen_info.get("metadata", {})
                        obj["asset"] = new_asset
                        obj["metadata"] = new_meta
                        # record provenance
                        updated_manifest["metadata"]["provenance"].append({
                            "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                            "placement_id": placement_id,
                            "action": "regenerated",
                            "category": obj.get("category"),
                            "prev_asset": prev_asset,
                            "new_asset": new_asset
                        })
                    except Exception as e:
                        # if generation failed, add error provenance and flag note on object
                        obj.setdefault("notes", "")
                        obj["notes"] += f" | regeneration_failed: {e}"
                        updated_manifest["metadata"]["provenance"].append({
                            "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                            "placement_id": placement_id,
                            "action": "regeneration_failed",
                            "error": str(e)
                        })


                # Record texture_input into object metadata and re apply textures
                if texture_input:
                    meta = obj.get("metadata", {}) or {}
                    meta["retexture_input"] = texture_input
                    obj["metadata"] = meta
                    updated_manifest = _run_texturing_on_manifest(updated_manifest.model_dump(), texture_mode=self.texture_mode,
                                                               scene_id=scene_id)
                    updated_manifest = SceneManifest.model_validate(updated_manifest)
                    # provenance record for texture request
                    updated_manifest["metadata"]["provenance"].append({
                        "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                        "placement_id": placement_id,
                        "action": "texture_requested",
                        "retexture_input": texture_input
                    })

            # save updated manifest
            scene_manifest_obj = SceneManifest.model_validate(updated_manifest)
            out_path = save_manifest(scene_manifest_obj)
            return {"status": "ok", "manifest_path": str(out_path)}