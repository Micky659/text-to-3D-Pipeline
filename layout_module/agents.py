import json, uuid, time
import datetime
from typing import List, Dict, Any
from .llm_client import LLMClient
from .prompts import build_prompt
from .asset_registry import load_categories, categories_table_text
from .models import SceneManifest, Room, Placement
from .verifier import check_and_repair
from .verifier import check_collisions, check_out_of_bounds
from .config import settings
import re

class LayoutPlannerAgent:
    def __init__(self, llm: LLMClient, categories: Dict = None, max_retries: int = 5):
        self.llm = llm
        self.categories = categories or load_categories()
        self.categories_table = categories_table_text(self.categories)
        self.max_retries = max_retries

    def plan(self, scene_id: str, room: Room, request_list: List[str],
             relationships: str = "", style: str = "modern", clearance: float = None) -> Dict[str, Any]:
        clearance = clearance or settings.DEFAULT_CLEARANCE
        prompt = build_prompt(room.w, room.d, room.h, self.categories_table, ", ".join(request_list), relationships, style, clearance)
        attempt = 0
        last_error = None
        while attempt < self.max_retries:
            attempt += 1
            raw = self.llm.generate(prompt, max_tokens=1200, temperature=0, model="deepseek-reasoner")
            if raw.startswith("```json"):
                raw = raw[7:][:-3].strip()
            # try parse JSON array
            try:
                arr = json.loads(raw)
                print(arr)
                placements = []
                for item in arr:
                    # normalize fields, fill missing id/style_hint
                    if "id" not in item:
                        item["id"] = f"{item.get('category','obj')}_{uuid.uuid4().hex[:6]}"
                    item.setdefault("anchor", "floor_center")
                    item.setdefault("rotation_yaw", 0.0)
                    item.setdefault("style_hint", "")
                    placements.append(item)
            except Exception as e:
                # invalid LLM output -> ask LLM to output strictly JSON only in next iteration
                last_error = {"type":"parse_error","message":str(e),"raw": raw}
                # augment prompt with explicit instruction and retry
                prompt += "\n\nNOTE: Your last response could not be parsed as JSON. Please reply with valid JSON array only."
                continue

            # run deterministic checks and repairs
            placements_copy = [dict(p) for p in placements]  # ensure mutable
            placements_checked, repairs, success, violations = check_and_repair(placements_copy, room.w, room.d, 0.1)
            # Build manifest
            manifest = SceneManifest(scene_id=scene_id, room=room, objects=[Placement(**p) for p in placements_checked], metadata={"scene_init_time":datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "provenance":[]})
            # attach repairs to provenance
            if success:
                for r in repairs:
                    manifest.add_provenance(
                        {"timestamp": r.get("timestamp", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                         "placement_id": r.get("placement_id"), "violation": r.get("violation"),
                         "attempted_fix": r.get("attempted_fix")})
                return {"ok": True, "manifest": manifest}
            # else failure: prepare error details and re-request LLM with constraints
            last_error = {"type":"verifier_failure", "violations": violations}
            # add a strict instruction to the prompt: describe violations and request a new layout avoiding them
            prompt = ("\n\nThe deterministic verifier reports layout violations:\n" +
                       json.dumps(last_error, indent=2) +
                       "\n\nOld layout:\n" +
                       manifest.model_dump_json(indent=2) +
                       "\nPlease produce a new JSON array layout that avoids the reported violations. Keep placements within the room and maintain clearance. Output JSON array only.")
            # loop and retry
        # Exhausted retries
        return {"ok": False, "error": last_error}

class SceneEditorAgent:
    """
    Edit an existing SceneManifest according to textual instruction.
    The LLM must return a JSON object:
    { "manifest": <full scene manifest JSON (same schema as SceneManifest)>, "modules_to_run": ["assembly","mesh_gen"] }
    """
    def __init__(self, llm: LLMClient, categories: Dict = None, max_retries: int = 3):
        self.llm = llm
        self.categories = categories or load_categories()
        self.max_retries = max_retries

    EDIT_PROMPT_TEMPLATE = """You are a Scene Editor. Given an existing scene manifest and an edit instruction, return a JSON object with key:
- "manifest": the updated scene manifest (same schema as the original).

Important:
- For every object in the manifest["objects"] array, include two fields:
    "regenerate": true|false
    "retexture_input": null | "short one-line prompt for retexturing"
- regenerate=true means the mesh asset should be regenerated.
- texture_input, if provided as a string, the object will be retextured as instructed.
- If only assembly changes are needed, set regenerate=false and texture_input=null for all objects.

Input manifest:
{manifest}

Edit instruction:
{instruction}

Rules:
- Understand the edit instruction and make the required changes.
- Return JSON only.
- Do not modify unrelated fields.
- If an automated change could break clearance/space, attempt to fix placement or indicate the expected fix in manifest.notes.
"""

    def edit(self, manifest_json: Dict[str, Any], instruction: str, clearance: float = None):
        clearance = clearance or settings.DEFAULT_CLEARANCE
        attempt = 0
        prompt = self.EDIT_PROMPT_TEMPLATE.format(manifest=json.dumps(manifest_json, indent=2), instruction=instruction)
        last_error = None
        while attempt < self.max_retries:
            attempt += 1
            raw = self.llm.generate(prompt, max_tokens=1600, temperature=0.0)
            try:
                parsed = json.loads(raw)
                new_manifest = parsed.get("manifest")

                for obj in new_manifest.get("objects", []):
                    obj.setdefault("regenerate", False)
                    obj.setdefault("texture_input", None)

                # normalize into SceneManifest (use pydantic validation if desired)
                # run deterministic checks & repairs
                # convert to internal placements
                room = new_manifest["room"]
                rm = Room(**room)
                placements = new_manifest["objects"]
                placements_checked, repairs, success, violations = check_and_repair(placements, rm.w, rm.d, clearance)
                # attach provenance
                if "metadata" not in new_manifest:
                    new_manifest["metadata"] = {}
                prov = new_manifest["metadata"].get("provenance", [])
                for r in repairs:
                    prov.append({"timestamp": r.get("timestamp"), "placement_id": r.get("placement_id"), "violation": r.get("violation"), "attempted_fix": r.get("attempted_fix")})
                new_manifest["metadata"]["provenance"] = prov
                if success:
                    return {"ok": True, "manifest": new_manifest}
                # else augment prompt with verifier details to ask for corrected manifest
                last_error = {"type":"verifier_failure","violations":violations,"repairs":repairs}
                prompt += ("\n\nThe deterministic verifier reported these problems with the manifest you returned:\n" +
                           json.dumps(last_error, indent=2) +
                           "\nPlease output a corrected manifest JSON that resolves these issues. Ensure each object still includes regenerate and retexture_input fields.")
                continue
            except Exception as e:
                last_error = {"type":"parse_error","message":str(e),"raw": raw}
                prompt += "\n\nNOTE: Your last response could not be parsed. Reply with valid JSON only."
                continue
        return {"ok": False, "error": last_error}
