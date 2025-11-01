import json
from typing import Dict, List

DEFAULT_CATEGORIES = {
    "sofa": {"bbox": [2.0, 0.95, 0.85], "forward": [0,0,1], "up": [0,1,0]},
    "lamp": {"bbox":[0.3,0.3,1.8],"forward":[0,0,1],"up":[0,1,0]},
    "table": {"bbox":[1.8,1.0,0.75],"forward":[0,0,1],"up":[0,1,0]},
    "chair": {"bbox":[0.5,0.5,0.9],"forward":[0,0,1],"up":[0,1,0]}
}

def load_categories(path=None):
    if path:
        with open(path,'r') as f:
            return json.load(f)
    return DEFAULT_CATEGORIES

def categories_table_text(cat_map: Dict = None) -> str:
    cat_map = cat_map or DEFAULT_CATEGORIES
    lines = []
    for k,v in cat_map.items():
        lines.append(f"{k}: bbox={v['bbox']}")
    return "\n".join(lines)

def required_categories_table_text(cat_map: Dict = None, object_requirement_list: List = None) -> str:
    cat_map = cat_map or DEFAULT_CATEGORIES
    lines = []
    for k,v in cat_map.items():
        if k in object_requirement_list:
            lines.append(f"{k}: bbox={v['bbox']}, anchor={v['anchor']}")
    return "\n".join(lines)