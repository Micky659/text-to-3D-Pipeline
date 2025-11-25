import json, uuid, datetime
from typing import List, Dict, Any
from layout_module.llm_client import LLMClient
from layout_module.asset_registry import load_categories, required_categories_table_text
from layout_module.models import SceneManifest, Room, Placement
from layout_module.verifier import check_and_repair
from layout_module.config import settings


class LayoutPlannerAgent:
    def __init__(self, llm: LLMClient, categories: Dict = None, max_retries: int = 50):
        self.llm = llm
        self.categories = categories or load_categories()
        self.max_retries = max_retries

    IMPROVED_LAYOUT_PROMPT = """You are an expert 3D scene layout planner. Generate object placements as a JSON array.

COORDINATE SYSTEM
- Origin (0, 0, 0) is at room center
- X-axis: Left (-) to Right (+)
- Y-axis: Down (-) to Up (+) 
- Z-axis: Back (-) to Front (+)
- Rotation: 0° faces FORWARD (-Z direction), 90° faces RIGHT (+X), 180° faces BACK (+Z), 270° faces LEFT (-X)

ROOM SPECIFICATIONS
Dimensions: {w:.2f}m (width) × {d:.2f}m (depth) × {h:.2f}m (height)
Room bounds: X ∈ [{x_min:.2f}, {x_max:.2f}]m, Z ∈ [{z_min:.2f}, {z_max:.2f}]m
Style: {style}

CLEARANCE REQUIREMENTS
- Minimum {clearance:.2f}m between object surfaces (NOT centers)
- Minimum {wall_clearance:.2f}m from all walls
- Account for object rotation when computing clearances

PLACEMENT STRATEGY
Follow this step-by-step process:

1. ANCHOR OBJECTS: Start with largest/most important items
   - Place beds/sofas against walls for stability
   - Position desks near windows/walls
   - Consider focal points and natural flow

2. COMPUTE FOOTPRINTS: For each object, calculate actual space needed
   - For rotation 0°/180°: footprint = [bbox_width, bbox_depth]
   - For rotation 90°/270°: footprint = [bbox_depth, bbox_width]
   - Add clearance buffer: effective_footprint = footprint + 2×clearance

3. CHECK CLEARANCES: Ensure minimum distances
   - Wall clearance: distance from object edge to wall ≥ {wall_clearance:.2f}m
   - Object clearance: distance between object edges ≥ {clearance:.2f}m
   - Use worst-case bounds for rotated objects

4. FUNCTIONAL RELATIONSHIPS: {relationships}
   - "next to" = 0.3-0.8m apart
   - "in front of" = aligned on perpendicular axis, 0.5-1.5m apart
   - "across from" = opposite sides, maintaining clearance

OBJECT CATEGORIES
{categories_table}

NOTE: Each category has an "anchor" point (bottom center where position is measured from) and "bbox_center" (geometric center).
The position you specify will be placed at the anchor point, NOT the geometric center.

REQUIRED OUTPUT FORMAT
Generate a JSON array with these exact fields for each object:

{{
  "id": "unique_identifier",           // e.g., "bed_0", "chair_1"
  "category": "category_name",         // must match categories table
  "bbox": [width, depth, height],      // [X, Z, Y] dimensions in meters
  "position": [x, 0, z],               // anchor point position, y always 0
  "rotation_yaw": degrees,             // 0=forward(-Z), 90=right(+X), 180=back(+Z), 270=left(-X)
  "style_hint": "brief description",   // for texture generation
  "notes": "placement reasoning"       // explain your spatial decisions
}}

OBJECTS TO PLACE
{request_list}

WORKED EXAMPLE
[{{"id": "sofa_0","category": "sofa","position": [2.76, 0.39, 1.31],"bbox": [2.26, 0.94, 0.79],"rotation_yaw": 0.00}},
 {{ "id": "chair_0","category": "chair","position": [1.56, 0.30, 2.57],"bbox": [0.85, 0.78, 0.60],"rotation_yaw": 90.00}},
 {{ "id": "table_0","category": "table","position": [2.96, 0.25, 2.41],"bbox": [0.69, 0.69, 0.50],"rotation_yaw": 0.00}},
 {{ "id": "lamp_0","category": "lamp","position": [3.04, 2.59, 2.07],"bbox": [0.86, 0.85, 0.65],"rotation_yaw": 0.00}}]
CRITICAL REMINDERS
- Output ONLY the JSON array, no markdown, no explanations
- Every object must fit within room bounds INCLUDING clearances
- Consider rotated footprints when checking positions
- Place larger items first, then fill with smaller items
- Maintain functional relationships while respecting clearances

Generate the layout now:"""

    def plan(self, scene_id: str, user_input: str, texture_method: str, room: Room,
             request_list: List[str], relationships: str = "", style: str = "modern",
             clearance: float = None) -> Dict[str, Any]:

        clearance = clearance or settings.DEFAULT_CLEARANCE
        wall_clearance = settings.DEFAULT_WALL_CLEARANCE

        hw, hd = room.w / 2.0, room.d / 2.0
        x_min, x_max = -hw + wall_clearance, hw - wall_clearance
        z_min, z_max = -hd + wall_clearance, hd - wall_clearance

        categories_table = required_categories_table_text(self.categories, request_list)

        prompt = self.IMPROVED_LAYOUT_PROMPT.format(
            w=room.w, d=room.d, h=room.h,
            x_min=x_min, x_max=x_max,
            z_min=z_min, z_max=z_max,
            categories_table=categories_table,
            request_list=request_list,
            relationships=relationships or "Arrange naturally with good flow",
            style=style,
            clearance=clearance,
            wall_clearance=wall_clearance
        )

        attempt = 0
        last_error = None
        previous_layouts = []  # Track failed attempts

        while attempt < self.max_retries:
            attempt += 1

            # Use temperature=0.3 for some variation while maintaining consistency
            raw = self.llm.generate(prompt, max_tokens=2000, temperature=0.15)
            raw = self._clean_json_response(raw)

            try:
                arr = json.loads(raw)
                if not isinstance(arr, list):
                    raise ValueError("Response is not a JSON array")

                placements = self._normalize_placements(arr)
                print("Placements:", placements)

                if not placements:
                    raise ValueError("No valid placements generated")

                # Run verifier
                placements_copy = [dict(p) for p in placements]
                placements_checked, repairs, success, violations = check_and_repair(
                    placements_copy, room.w, room.d, clearance, wall_clearance
                )
                print("Placements checked:", placements_checked, repairs, success, violations)

                # Build manifest
                manifest = SceneManifest(
                    scene_id=scene_id,
                    user_input=user_input,
                    texture_method=texture_method,
                    room=room,
                    objects=[Placement(**p) for p in placements_checked],
                    metadata={
                        "scene_init_time": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                        "provenance": [],
                        "layout_attempts": attempt
                    }
                )

                if success:
                    # Add repair provenance
                    for r in repairs:
                        manifest.add_provenance({
                            "timestamp": r.get("timestamp"),
                            "placement_id": r.get("placement_id"),
                            "category": r.get("category"),
                            "violation": r.get("violation"),
                            "attempted_fix": r.get("attempted_fix")
                        })
                    return {"ok": True, "manifest": manifest}

                # Store failed layout for context
                previous_layouts.append({
                    "layout": placements,
                    "violations": violations
                })

                # Build detailed feedback
                prompt = self._build_retry_prompt(
                    violations, placements, previous_layouts[-3:],  # Last 3 attempts
                    room, clearance, wall_clearance, x_min, x_max, z_min, z_max,
                    request_list, relationships, style, categories_table
                )

            except Exception as e:
                last_error = {"error_type": "parse_error", "message": str(e), "raw": raw[:500]}
                prompt += f"\n\n[ERROR] Invalid JSON: {str(e)}. Output ONLY a valid JSON array."
                continue

        return {"ok": False, "error": last_error, "attempts": attempt}

    def _clean_json_response(self, raw: str) -> str:
        """Clean LLM response to extract JSON"""
        raw = raw.strip()

        # Remove markdown code blocks
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]

        raw = raw.strip()

        # Handle single object wrapped in array
        if raw.startswith("{") and not raw.startswith("["):
            raw = '[' + raw + ']'

        return raw

    def _normalize_placements(self, arr: List[Dict]) -> List[Dict]:
        """Normalize and validate placement objects"""
        placements = []

        for item in arr:
            # Skip invalid entries
            if "category" not in item and "type" not in item:
                continue

            category = item.get("category") or item.get("type")

            # Inject metadata from categories
            if category in self.categories:
                cat_meta = self.categories[category]
                item.setdefault("bbox", cat_meta.get("bbox", [1.0, 1.0, 1.0]))
                item["anchor"] = cat_meta.get("anchor", [0.0, 0.0, 0.0])
                item["bbox_center"] = cat_meta.get("bbox_center", [0.0, 0.0, 0.0])
            else:
                item.setdefault("bbox", [1.0, 1.0, 1.0])
                item["anchor"] = [0.0, 0.0, 0.0]
                item["bbox_center"] = [0.0, 0.0, 0.0]

            # Normalize fields
            item.setdefault("id", f"{category}_{uuid.uuid4().hex[:6]}")
            item["category"] = category
            item.setdefault("rotation_yaw", 0.0)
            item.setdefault("style_hint", "")
            item.setdefault("notes", "")

            if "position" not in item:
                continue

            placements.append(item)

        return placements

    def _build_retry_prompt(self, violations, placements, previous_layouts,
                            room, clearance, wall_clearance,
                            x_min, x_max, z_min, z_max,
                            request_list, relationships, style, categories_table):
        """Build detailed retry prompt with violation feedback"""

        prompt = f"""Previous layout attempt FAILED verification. Analyze the violations and generate a CORRECTED layout.

=== FAILED LAYOUT ===
{json.dumps(placements, indent=2)}

=== VIOLATIONS FOUND ===
"""

        for v_group in violations:
            if "out_of_bounds" in v_group:
                prompt += "\nOUT OF BOUNDS VIOLATIONS:\n"
                for v in v_group["out_of_bounds"]:
                    prompt += f"  • {v['id']} ({v['category']}): {v['details']}\n"
                    prompt += f"    → Move object toward center or reduce size\n"

            if "collisions" in v_group:
                prompt += "\nCOLLISION VIOLATIONS:\n"
                for v in v_group["collisions"]:
                    prompt += f"  • {v['ids'][0]} ↔ {v['ids'][1]}: {v['details']}\n"
                    prompt += f"    → Increase separation or reposition\n"

        if len(previous_layouts) > 1:
            prompt += f"\n=== PATTERN ANALYSIS ===\n"
            prompt += f"You've made {len(previous_layouts)} attempts. Common issues:\n"
            prompt += "  • Are you accounting for object rotation in footprint?\n"
            prompt += "  • Are you placing objects too close to walls?\n"
            prompt += "  • Are you leaving enough clearance between objects?\n"

        prompt += f"""

=== CORRECTION STRATEGY ===
1. Start with largest objects, place against walls with {wall_clearance:.2f}m clearance
2. For each object, compute rotated footprint:
   - rotation 0°/180°: use [bbox[0], bbox[1]]
   - rotation 90°/270°: use [bbox[1], bbox[0]] (SWAPPED)
3. Check position bounds: 
   - Left edge: position.x - footprint.width/2 ≥ {x_min:.2f}
   - Right edge: position.x + footprint.width/2 ≤ {x_max:.2f}
   - Back edge: position.z - footprint.depth/2 ≥ {z_min:.2f}
   - Front edge: position.z + footprint.depth/2 ≤ {z_max:.2f}
4. Maintain {clearance:.2f}m between all object pairs

=== REQUIRED OUTPUT ===
Generate a NEW corrected JSON array following the same format.
Objects needed: {request_list}
Relationships: {relationships}
Style: {style}

{categories_table}

Output ONLY the JSON array, no explanations:"""

        return prompt