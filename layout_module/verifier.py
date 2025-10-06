# layout_planner/verifier.py
from shapely.geometry import Polygon, box, Point
from shapely.affinity import translate, rotate
import math
import time
from typing import List, Tuple, Dict, Any
import numpy as np


# Build axis-aligned room polygon (we treat room as rectangle [0..W] x [0..D] in XZ plane)
def room_polygon(width: float, depth: float):
    # center the room at (0,0), extents [-w/2, w/2], [-d/2, d/2]
    hw, hd = width / 2.0, depth / 2.0
    return Polygon([(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)])


def footprint_polygon(center_x: float, center_z: float, width: float, depth: float, yaw_deg: float):
    half_w, half_d = width / 2.0, depth / 2.0
    poly = box(-half_w, -half_d, half_w, half_d)  # axis aligned
    poly = rotate(poly, yaw_deg, origin=(0, 0), use_radians=False)
    poly = translate(poly, xoff=center_x, yoff=center_z)
    return poly


def check_out_of_bounds(placements: List[Dict], room_w: float, room_d: float) -> List[Dict[str, Any]]:
    """
    Checks for out-of-bounds placements and provides specific feedback.
    Returns a list of violation records.
    """
    poly_room = room_polygon(room_w, room_d)
    violations = []
    for i, p in enumerate(placements):
        x, z = p["position"][0], p["position"][2]
        w, d, _ = p["bbox"]
        yaw = p.get("rotation_yaw", 0.0)
        poly = footprint_polygon(x, z, w, d, yaw)

        if not poly.within(poly_room):
            # NEW: Provide specific feedback on how the object is out of bounds
            bounds = poly.bounds
            min_x, min_z, max_x, max_z = bounds
            room_hw, room_hd = room_w / 2.0, room_d / 2.0
            details = []
            if min_x < -room_hw:
                details.append(f"extends {abs(min_x + room_hw):.2f}m beyond the -X wall")
            if max_x > room_hw:
                details.append(f"extends {abs(max_x - room_hw):.2f}m beyond the +X wall")
            if min_z < -room_hd:
                details.append(f"extends {abs(min_z + room_hd):.2f}m beyond the -Z wall")
            if max_z > room_hd:
                details.append(f"extends {abs(max_z - room_hd):.2f}m beyond the +Z wall")

            violations.append({
                "index": i,
                "id": p.get("id"),
                "violation": "out_of_bounds",
                "details": ", ".join(details)
            })
    return violations


def check_collisions(placements: List[Dict], clearance: float = 0.6) -> List[Dict[str, Any]]:
    """
    Checks for collisions between placements and provides specific feedback.
    Returns a list of violation records.
    """
    polys = []
    for p in placements:
        x, z = p["position"][0], p["position"][2]
        w, d, _ = p["bbox"]
        yaw = p.get("rotation_yaw", 0.0)
        w_eff = w + clearance - 0.4
        d_eff = d + clearance - 0.4
        polys.append(footprint_polygon(x, z, w_eff, d_eff, yaw))

    violations = []
    n = len(polys)
    for i in range(n):
        for j in range(i + 1, n):
            if polys[i].intersects(polys[j]):
                # NEW: Calculate the distance and how much it violates the clearance
                p1 = Point(placements[i]["position"][0], placements[i]["position"][2])
                p2 = Point(placements[j]["position"][0], placements[j]["position"][2])
                distance = p1.distance(p2)

                # Get the actual object polygons without clearance for a more accurate distance check
                actual_poly_i = footprint_polygon(placements[i]["position"][0], placements[i]["position"][2],
                                                  placements[i]["bbox"][0], placements[i]["bbox"][1],
                                                  placements[i].get("rotation_yaw", 0.0))
                actual_poly_j = footprint_polygon(placements[j]["position"][0], placements[j]["position"][2],
                                                  placements[j]["bbox"][0], placements[j]["bbox"][1],
                                                  placements[j].get("rotation_yaw", 0.0))
                actual_distance = actual_poly_i.distance(actual_poly_j)

                violations.append({
                    "indices": (i, j),
                    "ids": (placements[i].get("id"), placements[j].get("id")),
                    "violation": "collision",
                    "details": f"distance between objects is {actual_distance:.2f}m, but required clearance is {clearance:.2f}m. Overlap of {clearance - actual_distance:.2f}m."
                })
    return violations


def resolve_simple_nudge(placements: List[Dict], i: int, j: int, step=0.05, max_steps=80):
    """
    Move j away from i incrementally until no intersection or max_steps.
    Returns attempted displacement vector and success flag.
    """
    p_i = placements[i]
    p_j = placements[j]
    for s in range(max_steps):
        dx = p_j["position"][0] - p_i["position"][0]
        dz = p_j["position"][2] - p_i["position"][2]
        if abs(dx) < 1e-6 and abs(dz) < 1e-6:
            dx, dz = 1.0, 0.0
        norm = math.hypot(dx, dz)
        nx, nz = dx / norm, dz / norm
        p_j["position"][0] += nx * step
        p_j["position"][2] += nz * step
        # recompute footprints
        if not footprint_polygon(p_i["position"][0], p_i["position"][2], p_i["bbox"][0], p_i["bbox"][1],
                                 p_i.get("rotation_yaw", 0)).intersects(
            footprint_polygon(p_j["position"][0], p_j["position"][2], p_j["bbox"][0], p_j["bbox"][1],
                              p_j.get("rotation_yaw", 0))
        ):
            return {"dx": nx * step * (s + 1), "dz": nz * step * (s + 1)}, True
    return {"dx": nx * step * max_steps, "dz": nz * step * max_steps}, False


def resolve_rotate(placements: List[Dict], i: int, j: int, max_angle_deg=30, step_deg=5):
    """
    Try rotating object j in +/- direction in steps up to max_angle_deg.
    Returns attempted angle and success flag.
    """
    p_i = placements[i]
    p_j = placements[j]
    original = p_j.get("rotation_yaw", 0.0)
    for sign in (+1, -1):
        angle = step_deg * sign
        while abs(angle) <= max_angle_deg:
            p_j["rotation_yaw"] = original + angle
            if not footprint_polygon(p_i["position"][0], p_i["position"][2], p_i["bbox"][0], p_i["bbox"][1],
                                     p_i.get("rotation_yaw", 0)).intersects(
                footprint_polygon(p_j["position"][0], p_j["position"][2], p_j["bbox"][0], p_j["bbox"][1],
                                  p_j.get("rotation_yaw", 0))
            ):
                return {"angle_deg": angle}, True
            angle += step_deg * sign
    # revert rotation
    p_j["rotation_yaw"] = original
    return {"angle_deg": 0}, False


def check_and_repair(placements: List[Dict], room_w: float, room_d: float, clearance: float = 0.6,
                     max_repair_steps: int = 5):
    """
    Runs full deterministic checks and attempts repairs. Returns:
    - placements (possibly modified)
    - repairs: list of repair records {placement_id, violation, attempted_fix, timestamp}
    - success: bool (True if all checks passed after repairs)
    - violations: list of failure descriptions if persistent
    """
    repairs = []

    for attempt in range(max_repair_steps):
        out_of_bounds_violations = check_out_of_bounds(placements, room_w, room_d)
        collision_violations = check_collisions(placements, clearance)

        if not out_of_bounds_violations and not collision_violations:
            return placements, repairs, True, []

        # attempt repairs: handle out_of_bounds by nudging toward center
        for violation in out_of_bounds_violations:
            idx = violation["index"]
            p = placements[idx]
            # compute vector from center to object and nudge opposite direction into room
            cx, cz = 0.0, 0.0
            dx = p["position"][0] - cx
            dz = p["position"][2] - cz
            norm = math.hypot(dx, dz) or 1.0
            nx, nz = -dx / norm, -dz / norm
            # try incremental nudge
            oldpos = (p["position"][0], p["position"][2])
            p["position"][0] += nx * 0.2  # coarse nudge
            p["position"][2] += nz * 0.2
            repairs.append({"timestamp": time.time(), "placement_id": p.get("id", ""), "violation": "out_of_bounds",
                            "attempted_fix": {"type": "nudge_into_room", "old_pos": oldpos,
                                              "new_pos": (p["position"][0], p["position"][2])}})

        # handle collisions
        for violation in collision_violations:
            i, j = violation["indices"]
            # try nudge j away from i
            attempt, ok = resolve_simple_nudge(placements, i, j)
            if ok:
                repairs.append({"timestamp": time.time(), "placement_id": placements[j].get("id", ""),
                                "violation": "collision",
                                "attempted_fix": {"type": "nudge_away", "from": placements[i].get("id", ""),
                                                  "dx_dz": attempt}})
                continue
            # else try rotate j
            attempt2, ok2 = resolve_rotate(placements, i, j)
            if ok2:
                repairs.append({"timestamp": time.time(), "placement_id": placements[j].get("id", ""),
                                "violation": "collision",
                                "attempted_fix": {"type": "rotate", "from": placements[i].get("id", ""),
                                                  "angle": attempt2}})
                continue
            # if both fail, mark persistent violation and break -> escalate
            repairs.append({"timestamp": time.time(), "placement_id": placements[j].get("id", ""),
                            "violation": "collision_unresolved",
                            "attempted_fix": {"type": "exhausted"}})

    # final check
    final_oob = check_out_of_bounds(placements, room_w, room_d)
    final_coll = check_collisions(placements, clearance)

    final_violations = []
    if final_oob or final_coll:
        final_violations.append({"out_of_bounds": final_oob, "collisions": final_coll})
        return placements, repairs, False, final_violations

    return placements, repairs, True, []