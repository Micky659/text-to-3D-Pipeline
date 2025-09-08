from typing import List, Dict, Any
from .llm_client import LLMClient
from .asset_registry import load_categories, categories_table_text
from .prompts import build_prompt
from .models import SceneManifest, Room, Placement
from .verifier import check_collisions, resolve_simple_nudge
from .config import settings
import json
import uuid

class BaseAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

class LayoutPlannerAgent(BaseAgent):
    def __init__(self, llm: LLMClient, categories: Dict = None):
        super().__init__(llm)
        self.categories = categories or load_categories()
        self.categories_table = categories_table_text(self.categories)

    def plan(self, scene_id: str, room: Room, request_list: List[str],
             relationships: str = "", style: str = "modern", clearance: float = None) -> SceneManifest:
        clearance = clearance or settings.DEFAULT_CLEARANCE
        # build prompt
        prompt = build_prompt(
            w=room.w, d=room.d, h=room.h,
            categories_table=self.categories_table,
            request_list=", ".join(request_list),
            relationships=relationships or "none",
            style=style,
            clearance=clearance
        )
        print(prompt)
        raw = self.llm.generate(prompt, max_tokens=1024, temperature=0.15)
        print(raw)
        # Expect raw to be JSON array; attempt parse
        try:
            arr = json.loads(raw)
            # sanitize entries: ensure ids and required keys
            placements = []
            for item in arr:
                # fill missing id
                if "id" not in item:
                    item["id"] = f"{item.get('category','obj')}_{uuid.uuid4().hex[:6]}"
                # enforce anchor default
                item.setdefault("anchor","floor_center")
                # default rotation
                item.setdefault("rotation_yaw", 0.0)
                placements.append(item)
        except Exception as exc:
            # If parsing failed, fallback to a deterministic simple placer
            print("LLM returned non-JSON or parsing failed:", exc)
            placements = self._fallback_placer(room, request_list)

        # verify & resolve collisions
        collisions = check_collisions(placements, clearance=clearance)
        if collisions:
            for pair in collisions:
                resolved = resolve_simple_nudge(placements, pair)
                if not resolved:
                    # if cannot resolve, mark note for human review
                    i,j = pair
                    placements[j]["notes"] = "collision_unresolved"

        manifest = SceneManifest(
            scene_id=scene_id,
            room=room,
            objects=[Placement(**p) for p in placements],
            metadata={"planner":"llm_layout_v1", "clearance": clearance}
        )
        return manifest

    def _fallback_placer(self, room: Room, request_list: List[str]):
        # Simple grid placer left-to-right, front-to-back
        placements = []
        x_cursor = 0.5
        z_cursor = 0.5
        row_depth = 0.0
        for idx, cat in enumerate(request_list):
            meta = self.categories.get(cat, {"bbox":[0.5,0.5,0.5]})
            w,d,h = meta["bbox"]
            if x_cursor + w/2 > room.w:
                x_cursor = 0.5
                z_cursor += row_depth + 0.5
                row_depth = 0.0
            placements.append({
                "id": f"{cat}_{idx}",
                "category": cat,
                "bbox": meta["bbox"],
                "position": [x_cursor + w/2, 0.0, z_cursor + d/2],
                "rotation_yaw": 0.0,
                "anchor": "floor_center"
            })
            x_cursor += w + 0.3
            row_depth = max(row_depth, d)
        return placements
