"""
Small registry mapping category -> canonical metadata (median bbox, canonical forward/up).
"""

import json
from typing import Dict

DEFAULT_CATEGORIES = {
    "sofa": {"bbox": [2.0, 0.95, 0.85], "forward": [0,0,1], "up": [0,1,0]},
    "armchair": {"bbox": [0.9,0.9,0.9], "forward":[0,0,1],"up":[0,1,0]},
    "coffee_table": {"bbox":[1.0,0.6,0.4],"forward":[0,0,1],"up":[0,1,0]},
    "tv": {"bbox":[1.2,0.15,0.75],"forward":[0,0,-1],"up":[0,1,0]},
    "rug": {"bbox":[2.0,2.0,0.01],"forward":[0,0,1],"up":[0,1,0]},
    "bookcase": {"bbox":[1.0,0.4,2.0],"forward":[0,0,-1],"up":[0,1,0]},
    "plant": {"bbox":[0.5,0.5,1.2],"forward":[0,0,1],"up":[0,1,0]},
    "floor_lamp": {"bbox":[0.3,0.3,1.8],"forward":[0,0,1],"up":[0,1,0]},
    "dining_table": {"bbox":[1.8,1.0,0.75],"forward":[0,0,1],"up":[0,1,0]},
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
        try:
            lines.append(f"{k}: bbox={v['bbox']}, forward={v['forward']}, up={v['up']}")
        except:
            lines.append(f"{k}: bbox={v['bbox']}")
    return "\n".join(lines)
