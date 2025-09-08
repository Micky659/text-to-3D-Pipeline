from typing import List
import json

BASE_LAYOUT_PROMPT = """You are a scene layout planner. Produce a JSON array of object placements for a room.
Constraints:
- Output MUST be valid JSON and nothing else.
- Room dimensions: W={w:.2f}m, D={d:.2f}m, H={h:.2f}m.
- Return one array of objects, each with fields:
    id, category, bbox [w,d,h] in meters, position [x,y,z] in meters (x right, y up, z forward),
    rotation_yaw (degrees, 0 aligns +X), anchor ('floor_center'|'center'), notes (optional).
- Maintain at least {clearance:.2f}m walking clearance between furniture clusters and between furniture and doors.
- Snap objects to floor (y=0) unless otherwise noted.
- Use the provided available_categories table exactly.
- Aim for a visually balanced layout for the style '{style}'.

Available categories (example):\n{categories_table}

Rules:
1) Place the requested items: {request_list}
2) Ensure key relationships: {relationships}
3) If item is "tv", place it against a wall with minimal glare (i.e., avoid facing large windows).
4) Do not put objects intersecting walls or each other.

Return JSON array only. Example item:
{{"id":"sofa_0","category":"sofa","bbox":[2.0,0.95,0.85],"position":[1.5,0,1.2],"rotation_yaw":0,"anchor":"floor_center","notes":"faces coffee_table"}}"""

def build_prompt(w: float, d: float, h: float, categories_table: str,
                 request_list: str, relationships: str, style: str, clearance: float) -> str:
    return BASE_LAYOUT_PROMPT.format(
        w=w, d=d, h=h, categories_table=categories_table,
        request_list=request_list, relationships=relationships, style=style, clearance=clearance
    )
