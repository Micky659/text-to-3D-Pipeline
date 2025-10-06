from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum
import json
from dataclasses import dataclass, field
from layout_module.llm_client import LLMClient
from layout_module.asset_registry import load_categories, categories_table_text
import uuid

class Intent(str, Enum):
    GENERATE = "generate"
    EDIT = "edit"
    QUERY = "query"

class ObjectSpec(BaseModel):
    category: str
    count: int = 1
    preferred_bbox: Optional[List[float]] = None  # optional hint [w,d,h]
    constraints: Optional[str] = None

class Interpretation(BaseModel):
    user_text: str
    intent: Intent
    room: Optional[Dict[str, float]] = None  # {"w":.., "d":.., "h":..}
    objects: List[ObjectSpec] = field(default_factory=list)
    style: Optional[str] = None
    relationships: Optional[str] = None
    scene_id: Optional[str] = None
    raw_llm_output: Optional[str] = None

class InputInterpreterAgent:
    def __init__(self, llm: LLMClient, category_path: Optional[str] = None):
        self.llm = llm
        self.categories = load_categories(category_path)
        self.categories_table = categories_table_text(self.categories)

    PROMPT_TEMPLATE = """You are an Input Interpreter. Convert a user's natural-language scene request into a strict JSON schema.

Return ONLY valid JSON that parses to this schema:
{{
  "intent": "generate" | "edit" | "query",
  "room": {{ "w": float, "d": float, "h": float}},  
  "objects": [{{ "category": string, "count": int, "preferred_bbox": [w,d,h] | null }}],
  "style": string | null,
  "relationships": string | null,
  "scene_id": string | null
}}

Available categories: 
{categories_table}

Rules:
- If the user mentions room size, parse it into meters (e.g. '5m x 4m'). If no size given, propose values based on request. Always prefer a very big room size.
- Choose object names from available categories.
- If no style is suggested propose one based on the request.
- Add relationships based on the chosen objects.
- For 'edit' intent, ensure scene_id is populated if the user mentions it.
- Output counts as integers.
- No extra explanation — JSON only.

User input:
\"\"\"{user_text}\"\"\"
"""

    def interpret(self, user_text: str, max_tokens: int = 512, temperature: float = 0.0) -> Interpretation:
        prompt = self.PROMPT_TEMPLATE.format(
            categories_table=self.categories_table,
            user_text=user_text.strip()
        )
        raw = self.llm.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        # try parse
        # try:
        parsed = json.loads(raw)
        # normalize intent
        intent = parsed.get("intent","generate")
        if isinstance(intent, str):
            intent = intent.lower()
        if intent not in ("generate","edit","query"):
            intent = "generate"
        # normalize room -> ensure numeric or "auto"
        room = parsed.get("room", {})
        # coerce numbers and convert feet if present
        def _norm_room_field(v):
            if isinstance(v, str) and ("ft" in v or "'" in v):
                # remove ft/symbols then convert
                import re
                num = float(re.sub(r"[^\d\.]", "", v))
                return num * 0.3048
            if isinstance(v, (int,float)):
                return float(v)
            if isinstance(v, str) and v == "auto":
                return "auto"
            return "auto"
        room_norm = {}
        for k in ("w","d","h"):
            room_norm[k] = _norm_room_field(room.get(k,"auto"))
        # build objects
        objs = []
        for o in parsed.get("objects", []):
            cat = o.get("category")
            if cat not in self.categories:
                # attempt fuzzy match: find category that contains cat substring
                match = None
                for c in self.categories.keys():
                    if cat and cat.lower() in c.lower():
                        match = c
                        break
                cat = match or cat
            objs.append({
                "category": cat,
                "count": int(o.get("count",1)),
                "preferred_bbox": o.get("preferred_bbox", None),
                "constraints": o.get("constraints", None)
            })
        interp = Interpretation(
            user_text=user_text,
            intent=Intent(parsed.get("intent", "generate")),
            room=room_norm,
            objects=[o for o in objs],
            style=parsed.get("style"),
            relationships=parsed.get("relationships"),
            scene_id=parsed.get("scene_id"),
            raw_llm_output=raw
        )
        return interp
        # except Exception as exc:
        #     # fallback: simple heuristic parse
        #     return self._fallback_parse(user_text, raw)

    def _fallback_parse(self, user_text: str, raw_llm_output: str = None) -> Interpretation:
        # Very simple regex-based heuristics: count numbers + nouns from category list
        import re
        words = re.findall(r"\w+", user_text.lower())
        objs = []
        for cat in self.categories.keys():
            if cat in user_text.lower():
                # try to find number before category
                m = re.search(r"(\d+)\s+" + re.escape(cat), user_text.lower())
                count = int(m.group(1)) if m else 1
                objs.append({"category":cat, "count":count, "preferred_bbox":None, "constraints":None})
        # fallback default
        if not objs:
            # pick 1 chair if nothing recognized
            objs.append({"category":"chair", "count":1, "preferred_bbox":None, "constraints":None})
        return Interpretation(
            user_text=user_text,
            intent=Intent.GENERATE,
            room={"w":"auto","d":"auto","h":"auto"},
            objects=objs,
            style=None,
            relationships=None,
            scene_id=None,
            raw_llm_output=raw_llm_output
        )
