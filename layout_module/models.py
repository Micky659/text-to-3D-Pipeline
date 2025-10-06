from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from typing import List, Optional, Literal, Tuple, Dict

Coord3 = Tuple[float, float, float]
BBox = Tuple[float, float, float]  # width, depth, height

class Room(BaseModel):
    w: float
    d: float
    h: float
    units: str = "meters"

from typing import Any, Dict
class Placement(BaseModel):
    id: str
    category: str
    bbox: BBox
    position: Coord3
    rotation_yaw: float = Field(..., description="rotation yaw in degrees, 0 = +X")
    anchor: Literal["floor_center", "center", "bottom_back"] = "floor_center"
    notes: Optional[str] = None
    snap_policy: Optional[str] = "floor|align_front_to_dir"
    style_hint: Optional[str] = None
    asset: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    regenerate: bool = False
    retexture_input: Optional[str] = None


class SceneManifest(BaseModel):
    scene_id: str
    room: Room
    objects: List[Placement]
    metadata: dict = field(default_factory=dict)

    def add_provenance(self, record: Dict):
        prov = self.metadata.get("provenance", [])
        prov.append(record)
        self.metadata["provenance"] = prov

class RepairRecord(BaseModel):
    timestamp: float
    placement_id: str
    violation: str
    attempted_fix: Dict[str, Any]


