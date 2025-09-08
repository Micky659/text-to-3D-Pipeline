from shapely.geometry import box
from shapely.affinity import translate, rotate
from typing import List, Tuple
import math

def footprint_polygon(center_x: float, center_z: float, width: float, depth: float, yaw_deg: float):
    # Create axis aligned box centered at origin then rotate and translate
    half_w, half_d = width / 2.0, depth / 2.0
    poly = box(-half_w, -half_d, half_w, half_d)  # coords on XZ plane
    poly = rotate(poly, yaw_deg, origin=(0,0), use_radians=False)
    poly = translate(poly, xoff=center_x, yoff=center_z)
    return poly

def check_collisions(placements: List[dict], clearance: float = 0.6) -> List[Tuple[int,int]]:
    """
    Check pairwise footprint intersections. Return list of colliding index pairs.
    Each placement dict must contain: position [x,y,z], bbox [w,d,h], rotation_yaw
    """
    polys = []
    for p in placements:
        x,z = p["position"][0], p["position"][2]
        w,d,_ = p["bbox"]
        yaw = p.get("rotation_yaw", 0.0)
        # expand by clearance buffer
        w_eff = w + clearance
        d_eff = d + clearance
        polys.append(footprint_polygon(x, z, w_eff, d_eff, yaw))

    collisions = []
    n = len(polys)
    for i in range(n):
        for j in range(i+1, n):
            if polys[i].intersects(polys[j]):
                collisions.append((i,j))
    return collisions

def resolve_simple_nudge(placements: List[dict], collide_pair: Tuple[int,int], step=0.1, max_steps=20):
    """
    Very simple nudge: move the second object radially outward until no collision or max_steps.
    """
    i,j = collide_pair
    p_i = placements[i]
    p_j = placements[j]
    for s in range(max_steps):
        # compute vector from i to j in XZ
        dx = p_j["position"][0] - p_i["position"][0]
        dz = p_j["position"][2] - p_i["position"][2]
        if dx==0 and dz==0:
            dx, dz = 1.0, 0.0
        norm = math.hypot(dx, dz)
        nx, nz = dx/norm, dz/norm
        # move j outward along (nx,nz)
        p_j["position"][0] += nx * step
        p_j["position"][2] += nz * step
        if not footprint_polygon(p_j["position"][0], p_j["position"][2], *(p_j["bbox"][:2]), p_j["rotation_yaw"]).intersects(
           footprint_polygon(p_i["position"][0], p_i["position"][2], *(p_i["bbox"][:2]), p_i["rotation_yaw"])
        ):
            return True
    return False
