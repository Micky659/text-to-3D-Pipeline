import json, uuid, time
import datetime
from typing import List, Dict, Any
from layout_module.llm_client import LLMClient
from layout_module.asset_registry import load_categories, required_categories_table_text
from layout_module.models import SceneManifest, Room, Placement
from layout_module.verifier import check_and_repair
from layout_module.config import settings
import re


class LayoutPlannerAgent:
    def __init__(self, llm: LLMClient, categories: Dict = None, max_retries: int = 20):
        self.llm = llm
        self.categories = categories or load_categories()
        self.max_retries = max_retries

    BASE_LAYOUT_PROMPT = """You are a scene layout planner. Produce a JSON array of object placements for a room.

    IMPORTANT INSTRUCTIONS:
    - First, think step-by-step about how you will place the objects to satisfy all constraints. Consider the room dimensions, clearances, and relationships.
    - Output MUST be valid JSON array in the exact format as describe and nothing else (no markdown, no explanations).
    - The room is centered at origin. Canonical up is +Y, forward is -Z, right is +X.
    
    OUTPUT REQUIREMENTS:
    Each object entry must include the following keys with the same label names and datatypes:
    - id (string): unique identifier (e.g., "bed_0", "chair_1")
    - category (string): object class from the categories table
    - bbox (list) [w, d, h]: bounding box dimensions in meters [width, depth, height] (X, Z, Y ordering)
    - position (list) [x, y, z]: anchor point position in meters
      * x: horizontal position (right/left), must be within [{x_min:.2f}, {x_max:.2f}]
      * y: vertical position (always 0)
      * z: forward/back position, must be within [{z_min:.2f}, {z_max:.2f}]
    - rotation_yaw (float): rotation in degrees, 0° = facing +X direction
    - style_hint (string): single short phrase for texture
    - notes (optional string): placement notes

    CLEARANCE POLICY:
    - Maintain at least {clearance:.2f}m clearance between objects (measured from object surfaces, not centers)
    - Maintain at least {wall_clearance:.2f}m clearance from all walls
    - Objects must NOT overlap or collide with each other
    - Objects must NOT extend beyond room boundaries

    ROOM SPECIFICATIONS:
    - Room dimensions: Width={w:.2f}m, Depth={d:.2f}m, Height={h:.2f}m
    - Room center: (0, 0, 0)
    - Valid placement area (accounting for wall clearance):
      * X range: [{x_min:.2f}m, {x_max:.2f}m]
      * Z range: [{z_min:.2f}m, {z_max:.2f}m]
    - Scene style: {style}

    PLACEMENT RULES:
    1) Place the requested items: {request_list}
    2) Ensure key relationships: {relationships}
    3) Use object metadata from the categories table below for bbox dimensions and category string
    4) When positioning objects consider object dimensions (bbox) and rotation_yaw
    5) Make sure the output includes the following entries for each object: id, category, bbox, position , rotation_yaw, style_hint, notes


    Categories Metadata Table:
    {categories_table}

    EXPECTED FORMAT:
    [
      {{"id":"bed_0","category":"bed","bbox":[1.5,2.0,0.6],"position":[-1.5,0,0.5],"rotation_yaw":0,"style_hint":"light oak wood, matte finish","notes":"against left wall"}},
      {{"id":"lamp_0","category":"lamp","bbox":[0.4, 0.4, 1.6],"position":[-0.5,0,0.5],"rotation_yaw":0,"style_hint":"metal","notes":"beside bed"}}
    ]
"""

    def plan(self, scene_id: str, user_input: str, texture_method: str, room: Room, request_list: List[str],
             relationships: str = "", style: str = "modern", clearance: float = None) -> Dict[str, Any]:

        clearance = clearance or settings.DEFAULT_CLEARANCE
        wall_clearance = settings.DEFAULT_WALL_CLEARANCE

        # Calculate room bounds for the prompt
        hw, hd = room.w / 2.0, room.d / 2.0
        x_min, x_max = -hw + wall_clearance, hw - wall_clearance
        z_min, z_max = -hd + wall_clearance, hd - wall_clearance

        categories_table = required_categories_table_text(self.categories, request_list)

        prompt = self.BASE_LAYOUT_PROMPT.format(
            w=room.w, d=room.d, h=room.h,
            x_min=x_min, x_max=x_max,
            z_min=z_min, z_max=z_max,
            categories_table=categories_table,
            request_list=request_list,
            relationships=relationships,
            style=style,
            clearance=clearance,
            wall_clearance=wall_clearance
        )

        print(prompt)

        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            attempt += 1
            raw = self.llm.generate(prompt, max_tokens=1200, temperature=0)
            raw = raw.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

            if raw.startswith("{") and not raw.startswith("["):
                raw = '[' + raw + ']'

            print(f"LLM Response (cleaned):\n{raw[:500]}...")

            # try parse JSON array
            try:
                arr = json.loads(raw)
                if not isinstance(arr, list):
                    raise ValueError("Response is not a JSON array")

                print(f"Parsed {len(arr)} objects from LLM response")

                placements = []
                for item in arr:
                    # Validate required fields
                    if "category" not in item and "type" not in item:
                        print(f"Warning: Object missing 'category' field, skipping: {item}")
                        continue

                    category = item["category"] if "category" in item else item["type"]

                    # Inject metadata from categories table
                    if category in self.categories:
                        cat_meta = self.categories[category]

                        # Use provided bbox or default from metadata
                        if "bbox" not in item or not item["bbox"]:
                            item["bbox"] = cat_meta.get("bbox", [1.0, 1.0, 1.0])

                        # CRITICAL: Inject anchor and bbox_center from metadata
                        # These are needed by the verifier for accurate collision detection
                        item["anchor"] = cat_meta.get("anchor", [0.0, 0.0, 0.0])
                        item["bbox_center"] = cat_meta.get("bbox_center", [0.0, 0.0, 0.0])
                    else:
                        print(f"Warning: Unknown category '{category}', using defaults")
                        item.setdefault("bbox", [1.0, 1.0, 1.0])
                        item["anchor"] = [0.0, 0.0, 0.0]
                        item["bbox_center"] = [0.0, 0.0, 0.0]

                    # Normalize fields
                    if "id" not in item or not item["id"]:
                        item["id"] = f"{category}_{uuid.uuid4().hex[:6]}"

                    item.setdefault("rotation_yaw", 0.0)
                    item.setdefault("style_hint", "")
                    item.setdefault("notes", "")

                    # Ensure position has 3 coordinates
                    if "position" not in item:
                        raise ValueError("Object missing 'position' field")

                    placements.append(item)

                if not placements:
                    raise ValueError("No valid placements generated")
            except Exception as e:
                # invalid LLM output -> ask LLM to output strictly JSON only in next iteration
                last_error = {"error_type":"parse_error","message":str(e),"raw": raw}
                # augment prompt with explicit instruction and retry
                prompt += "\n\nNOTE: Your last response could not be parsed as JSON. Please reply with valid JSON array only."
                continue

            # run deterministic checks and repairs
            print(f"\nRunning verifier with clearance={clearance}m, wall_clearance={wall_clearance}m...")
            placements_copy = [dict(p) for p in placements]  # Ensure mutable
            placements_checked, repairs, success, violations = check_and_repair(
                placements_copy, room.w, room.d, clearance, wall_clearance
            )

            # Build manifest
            manifest = SceneManifest(scene_id=scene_id, user_input=user_input, texture_method=texture_method, room=room, objects=[Placement(**p) for p in placements_checked], metadata={"scene_init_time":datetime.datetime.now().strftime('%m_%d__%H_%M_%S'), "provenance":[]})

            if success:
                print(f"✓ Layout verification successful!")
                if repairs:
                    print(f"  Applied {len(repairs)} automatic repairs")

                # Attach repairs to provenance
                for r in repairs:
                    manifest.add_provenance({
                        "timestamp": r.get("timestamp", datetime.datetime.now().strftime('%m_%d__%H_%M_%S')),
                        "placement_id": r.get("placement_id"),
                        "category": r.get("category"),
                        "violation": r.get("violation"),
                        "attempted_fix": r.get("attempted_fix")
                    })

                return {"ok": True, "manifest": manifest}

                # Verification failed - prepare detailed feedback for LLM
            print(f"✗ Layout verification failed")
            print(f"  Violations: {json.dumps(violations, indent=2)}")

            last_error = {"error_type": "verifier_failure", "violations": violations}

            # Build detailed error message for LLM
            violation_details = []
            for v_group in violations:
                if "out_of_bounds" in v_group and v_group["out_of_bounds"]:
                    violation_details.append("\nOUT OF BOUNDS VIOLATIONS:")
                    for v in v_group["out_of_bounds"]:
                        violation_details.append(
                            f"  - {v.get('id')} ({v.get('category')}): {v.get('details')}"
                        )

                if "collisions" in v_group and v_group["collisions"]:
                    violation_details.append("\nCOLLISION VIOLATIONS:")
                    for v in v_group["collisions"]:
                        violation_details.append(
                            f"  - {v.get('ids')[0]} and {v.get('ids')[1]} "
                            f"({v.get('categories')[0]} and {v.get('categories')[1]}): {v.get('details')}"
                        )

            # Create new prompt with violations feedback
            prompt = """You are a scene layout planner. Produce a JSON array of object placements for a room.

    IMPORTANT INSTRUCTIONS:
    - First, think step-by-step about how you will place the objects to satisfy all constraints. Consider the room dimensions, clearances, and relationships. The output should follow the provided output format.
    - Output MUST be valid JSON array in the exact format as describe in the end and nothing else (no markdown, no explanations).
    - The room is centered at origin. Canonical up is +Y, forward is -Z, right is +X.
"""

            prompt += "PREVIOUS ATTEMPT HAD VIOLATIONS:\n"
            prompt += "\n".join(violation_details)
            prompt += f"\n\nPrevious layout:\n{json.dumps(placements, indent=2)}"
            prompt += "\n\nPlease produce a NEW JSON array layout that FIXES these violations:"
            prompt += f"\n- Keep objects within room bounds (X: [{x_min:.2f}, {x_max:.2f}], Z: [{z_min:.2f}, {z_max:.2f}])"
            prompt += f"\n- Maintain {clearance:.2f}m clearance between objects"
            prompt += f"\n- Maintain {wall_clearance:.2f}m clearance from walls"
            prompt += "\n- Consider object dimensions when positioning"
            prompt += "\n\nOutput JSON array only. Make sure each object have the following entries: id, category, bbox, position , rotation_yaw, style_hint, notes."

            # Exhausted retries
        print(f"\n✗ Failed to generate valid layout after {self.max_retries} attempts")
        return {"ok": False, "error": last_error}