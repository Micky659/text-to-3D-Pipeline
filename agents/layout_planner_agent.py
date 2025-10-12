import json, uuid, time
import datetime
from typing import List, Dict, Any
from layout_module.llm_client import LLMClient
from layout_module.asset_registry import load_categories, categories_table_text
from layout_module.models import SceneManifest, Room, Placement
from layout_module.verifier import check_and_repair
from layout_module.config import settings
import re


class LayoutPlannerAgent:
    def __init__(self, llm: LLMClient, categories: Dict = None, max_retries: int = 20):
        self.llm = llm
        self.categories = categories or load_categories()
        self.categories_table = categories_table_text(self.categories)
        self.max_retries = max_retries

    BASE_LAYOUT_PROMPT = """You are a scene layout planner. Produce a JSON array of object placements for a room.
    IMPORTANT:
    - First, think step-by-step about how you will place the objects to satisfy all constraints. Consider the room dimensions, clearances, and relationships. Then, provide the final JSON output.
    - Output MUST be valid JSON and nothing else.
    - Each object entry must include these fields:
        id (string), category (string), bbox [w,d,h] in meters, position [x,y,z] in meters (x right, y up, z forward) (Make sure the objects dont collide with each other and are within the room boundaries and respect the clearance policy),
        rotation_yaw (degrees, 0 = +X), anchor ('floor_center'|'center'|'bottom_back'),
        style_hint (single short sentence: e.g. "light-wood, low-gloss", or "matte-gray fabric, worn edges"),
        notes (optional).
    - Position of each object should satisfy the user request and relationship constraints 
    - Use the provided bbox or suggest new if needed.
    - The bbox you provide is the expected bounding box (w,d,h) that will be used to scale generated mesh if required (be realistic).
    - Keep style_hint to a single short phrase that the texture pipeline can use.

    Room dimensions: W={w:.2f}m, D={d:.2f}m, H={h:.2f}m.
    Clearance policy: maintain at least {clearance:.2f}m clearance between objects and between objects and walls.
    Scene style: {style}

    Rules:
    1) Place the requested items: {request_list}
    2) Ensure key relationships: {relationships}
    3) Consider the item's metadata: {categories_table}
    4) Object placement and dimension should not go out of bounds of the room or collide with other object placements.
    5) Do not put objects intersecting walls or each other.

    Return JSON format only. Example output:
    {{"id":"sofa_0","category":"sofa","bbox":[2.0,0.95,0.85],"position":[1.5,0,1.2],"rotation_yaw":0,"anchor":"floor_center","style_hint":"mid-gray fabric, tufted","notes":"faces coffee_table"}}"""

    def plan(self, scene_id: str, room: Room, request_list: List[str],
             relationships: str = "", style: str = "modern", clearance: float = None) -> Dict[str, Any]:
        clearance = clearance or settings.DEFAULT_CLEARANCE
        prompt = self.BASE_LAYOUT_PROMPT.format(
        w=room.w, d=room.d, h=room.h, categories_table=self.categories_table,
        request_list=request_list, relationships=relationships, style=style, clearance=clearance
    )
        attempt = 0
        last_error = None
        while attempt < self.max_retries:
            attempt += 1
            raw = self.llm.generate(prompt, max_tokens=1200, temperature=0, model="deepseek-reasoner")
            if raw.startswith("```json"):
                raw = raw[7:][:-3].strip()
            elif raw.startswith("{"):
                raw = '[' + raw + ']'
            print(raw)
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
            manifest = SceneManifest(scene_id=scene_id, room=room, objects=[Placement(**p) for p in placements_checked], metadata={"scene_init_time":datetime.datetime.now().strftime('%m_%d__%H_%M_%S'), "provenance":[]})
            # attach repairs to provenance
            if success:
                for r in repairs:
                    manifest.add_provenance(
                        {"timestamp": r.get("timestamp", datetime.datetime.now().strftime('%m_%d__%H_%M_%S')),
                         "placement_id": r.get("placement_id"), "violation": r.get("violation"),
                         "attempted_fix": r.get("attempted_fix")})
                return {"ok": True, "manifest": manifest}
            # else failure: prepare error details and re-request LLM
            last_error = {"type":"verifier_failure", "violations": violations}
            # add a strict instruction to the prompt: describe violations and request a new layout
            prompt = ("\n\nThe deterministic verifier reports layout violations:\n" +
                       json.dumps(last_error, indent=2) +
                       "\n\nOld layout:\n" +
                       manifest.model_dump_json(indent=2) +
                       "\nPlease produce a new JSON array layout that avoids the reported violations. Keep placements within the room and maintain clearance. Output JSON array only.")
            # loop and retry
        # Exhausted retries
        return {"ok": False, "error": last_error}