import json, uuid, time
import datetime
from typing import List, Dict, Any
from layout_module.llm_client import LLMClient
from layout_module.asset_registry import load_categories, categories_table_text
from layout_module.models import SceneManifest, Room, Placement
from layout_module.verifier import check_and_repair
from layout_module.config import settings
import re


class SceneEditorAgent:
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
                    obj.setdefault("retexture_input", None)

                # normalize into SceneManifest
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
