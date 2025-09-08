# agents/orchestrator.py
from layout_module.llm_client import LLMClient
from layout_module.models import Room
from layout_module.utils import save_manifest
from layout_module.utils import load_manifest
from layout_module.asset_registry import load_categories
from layout_module.agents import LayoutPlannerAgent  # the planner we wrote earlier
from .input_interpreter import InputInterpreterAgent, Interpretation, Intent
import uuid
import os

class Orchestrator:
    def __init__(self, llm_base_url=None, llm_model=None, categories_path=None):
        self.llm_client = LLMClient(base_url=llm_base_url, model=llm_model)
        self.interpreter = InputInterpreterAgent(self.llm_client, category_path=categories_path)
        self.layout_planner = LayoutPlannerAgent(self.llm_client, categories=load_categories(categories_path))

    def handle_request(self, user_text: str, scene_id: str = None, save_to: str = None):
        interp: Interpretation = self.interpreter.interpret(user_text)
        print("INTERPRETATION:", interp.model_dump_json(indent=2))
        if interp.intent == Intent.GENERATE:
            # convert room to Room pydantic; if auto, default to heuristics
            room_dict = interp.room or {"w":"auto","d":"auto","h":"auto"}
            if room_dict.get("w") == "auto" or room_dict.get("d") == "auto" or room_dict.get("h") == "auto":
                # Heuristic defaults per style/scene scale
                room_defaults = {"w":6.0, "d":8.0, "h":3.5}
            else:
                room_defaults = {"w":float(room_dict.get("w",6.0)), "d":float(room_dict.get("d",8.0)), "h":float(room_dict.get("h",3.0))}
            room = Room(**room_defaults)
            # build request list flattening counts
            req_list = []
            for o in interp.objects:
                for i in range(o.count):
                    req_list.append(o.category)
            # relationships pass-through
            relationships = interp.relationships or ""
            scene_id = scene_id or interp.scene_id or f"scene_{uuid.uuid4().hex[:6]}"
            manifest = self.layout_planner.plan(scene_id, room, req_list, relationships=relationships, style=interp.style or "default")
            out_path = save_manifest(manifest)
            return {"status":"ok", "manifest_path": str(out_path)}
        elif interp.intent == Intent.EDIT:
            # For edit intent, try to load scene_id and produce an edit plan
            if not interp.scene_id:
                return {"status":"error", "reason":"no scene_id provided for edit intent"}
            # load manifest and apply simple edit instructions or return interpreted edit actions
            existing = load_manifest(os.path.join("output", f"{interp.scene_id}_scene_manifest.json"))
            # For now we return the interpreted edit actions so assembly module can apply them.
            return {"status":"ok", "scene_id": interp.scene_id, "edit_plan": interp.model_dump()}
        else:
            return {"status":"ok", "message":"query received", "interpretation": interp.model_dump()}
