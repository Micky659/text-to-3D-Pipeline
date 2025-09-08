import json
from layout_module.asset_registry import load_categories, categories_table_text


data = '''{
  "intent": "generate",
  "room": {
    "w": 7.315,
    "d": 3.048,
    "h": 2.4
  },
  "objects": [
    {
      "category": "bench",
      "count": 6,
      "constraints": null,
      "preferred_bbox": [1.8, 0.9, 0.75]
    },
    {
      "category": "plant",
      "count": 3,
      "constraints": null,
      "preferred_bbox": [null, null, null]
    },
    {
      "category": "desk",
      "count": 1,
      "constraints": null,
      "preferred_bbox": [1.8, 0.4, 2.4]
    }
  ],
  "style": null,
  "relationships": null,
  "scene_id": null
}
'''

data = str(data)

category_path = ""
categories = load_categories(category_path)
categories_table = categories_table_text(categories)

parsed = json.loads(data)
# normalize intent
intent = parsed.get("intent", "generate")
if isinstance(intent, str):
    intent = intent.lower()
if intent not in ("generate", "edit", "query"):
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
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v == "auto":
        return "auto"
    return "auto"


room_norm = {}
for k in ("w", "d", "h"):
    room_norm[k] = _norm_room_field(room.get(k, "auto"))
# build objects
objs = []
for o in parsed.get("objects", []):
    cat = o.get("category")
    if cat not in categories:
        # attempt fuzzy match: find category that contains cat substring
        match = None
        for c in categories.keys():
            if cat and cat.lower() in c.lower():
                match = c
                break
        cat = match or cat
    objs.append({
        "category": cat,
        "count": int(o.get("count", 1)),
        "preferred_bbox": o.get("preferred_bbox", None),
        "constraints": o.get("constraints", None)
    })

    print(objs)