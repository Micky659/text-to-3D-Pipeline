from shapely.geometry import Polygon, box, Point
from shapely.affinity import translate, rotate
import math
import datetime
from typing import List, Tuple, Dict, Any
import numpy as np


def room_polygon(width: float, depth: float):
    """Build axis-aligned room polygon centered at (0,0)"""
    hw, hd = width / 2.0, depth / 2.0
    return Polygon([(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)])


def footprint_polygon(center_x: float, center_z: float, width: float, depth: float, yaw_deg: float):
    """Create a rotated footprint polygon for an object"""
    half_w, half_d = width / 2.0, depth / 2.0
    poly = box(-half_w, -half_d, half_w, half_d)
    poly = rotate(poly, yaw_deg, origin=(0, 0), use_radians=False)
    poly = translate(poly, xoff=center_x, yoff=center_z)
    return poly


def get_object_center_from_anchor(position: List[float], anchor: List[float], bbox_center: List[float]) -> Tuple[
    float, float]:
    """
    Convert anchor-based position to bbox center position.

    Args:
        position: [x, y, z] - the position specified (assumed to be anchor point)
        anchor: [x, y, z] - the anchor point relative to object origin
        bbox_center: [x, y, z] - the bbox center relative to object origin

    Returns:
        (center_x, center_z) for footprint calculation
    """
    # Offset from anchor to bbox center
    offset_x = bbox_center[0] - anchor[0]
    offset_z = bbox_center[2] - anchor[2]

    # Apply offset to position
    center_x = position[0] + offset_x
    center_z = position[2] + offset_z

    return center_x, center_z


def check_out_of_bounds(placements: List[Dict], room_w: float, room_d: float, wall_clearance: float = 0.1) -> List[
    Dict[str, Any]]:
    """
    Check if objects extend beyond room boundaries (with optional wall clearance).

    Args:
        placements: List of object placement dictionaries
        room_w: Room width in meters
        room_d: Room depth in meters
        wall_clearance: Minimum distance from walls (default 0.1m)
    """
    # Create room polygon with wall clearance buffer
    poly_room = room_polygon(room_w - 2 * wall_clearance, room_d - 2 * wall_clearance)
    violations = []

    for i, p in enumerate(placements):
        x, z = p["position"][0], p["position"][2]
        w, d, _ = p["bbox"]
        yaw = p.get("rotation_yaw", 0.0)

        # Adjust position if anchor is specified
        if "anchor" in p and "bbox_center" in p:
            x, z = get_object_center_from_anchor(p["position"], p["anchor"], p["bbox_center"])

        poly = footprint_polygon(x, z, w, d, yaw)

        if not poly.within(poly_room):
            bounds = poly.bounds
            min_x, min_z, max_x, max_z = bounds
            room_hw, room_hd = (room_w - 2 * wall_clearance) / 2.0, (room_d - 2 * wall_clearance) / 2.0
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
                "category": p.get("category"),
                "violation": "out_of_bounds",
                "details": ", ".join(details) if details else "object outside room boundaries"
            })

    return violations


def check_collisions(placements: List[Dict], clearance: float = 0.6) -> List[Dict[str, Any]]:
    """
    Check if objects violate minimum clearance distance.

    Args:
        placements: List of object placement dictionaries
        clearance: Minimum clearance distance between objects (default 0.6m)
    """
    polys = []
    positions = []

    for p in placements:
        x, z = p["position"][0], p["position"][2]
        w, d, _ = p["bbox"]
        yaw = p.get("rotation_yaw", 0.0)

        # Adjust position if anchor is specified
        if "anchor" in p and "bbox_center" in p:
            x, z = get_object_center_from_anchor(p["position"], p["anchor"], p["bbox_center"])

        # Add clearance buffer to dimensions (FIXED: was subtracting 0.4)
        w_eff = w + clearance
        d_eff = d + clearance

        polys.append(footprint_polygon(x, z, w_eff, d_eff, yaw))
        positions.append((x, z))

    violations = []
    n = len(polys)

    for i in range(n):
        for j in range(i + 1, n):
            if polys[i].intersects(polys[j]):
                # Get actual polygons without clearance buffer
                x_i, z_i = positions[i]
                x_j, z_j = positions[j]

                actual_poly_i = footprint_polygon(
                    x_i, z_i,
                    placements[i]["bbox"][0], placements[i]["bbox"][1],
                    placements[i].get("rotation_yaw", 0.0)
                )
                actual_poly_j = footprint_polygon(
                    x_j, z_j,
                    placements[j]["bbox"][0], placements[j]["bbox"][1],
                    placements[j].get("rotation_yaw", 0.0)
                )

                actual_distance = actual_poly_i.distance(actual_poly_j)

                if actual_distance >= (clearance - 0.2):
                    continue  # Acceptable proximity, skip violation

                violation_amount = max(0, clearance - actual_distance)

                violations.append({
                    "indices": (i, j),
                    "ids": (placements[i].get("id"), placements[j].get("id")),
                    "categories": (placements[i].get("category"), placements[j].get("category")),
                    "violation": "collision",
                    "details": f"distance between objects is {actual_distance:.2f}m, required clearance is {clearance:.2f}m. Violation of {violation_amount:.2f}m."
                })

    return violations


def resolve_simple_nudge(placements: List[Dict], i: int, j: int, clearance: float = 0.6, step=0.05, max_steps=80):
    """Nudge object j away from object i to resolve collision"""
    p_i = placements[i]
    p_j = placements[j]

    # Get centers considering anchor points
    x_i, z_i = p_i["position"][0], p_i["position"][2]
    x_j, z_j = p_j["position"][0], p_j["position"][2]

    if "anchor" in p_i and "bbox_center" in p_i:
        x_i, z_i = get_object_center_from_anchor(p_i["position"], p_i["anchor"], p_i["bbox_center"])
    if "anchor" in p_j and "bbox_center" in p_j:
        x_j, z_j = get_object_center_from_anchor(p_j["position"], p_j["anchor"], p_j["bbox_center"])

    for s in range(max_steps):
        dx = x_j - x_i
        dz = z_j - z_i

        if abs(dx) < 1e-6 and abs(dz) < 1e-6:
            dx, dz = 1.0, 0.0

        norm = math.hypot(dx, dz)
        nx, nz = dx / norm, dz / norm

        # Update actual position (not center)
        p_j["position"][0] += nx * step
        p_j["position"][2] += nz * step

        # Recompute centers
        x_j_new = p_j["position"][0]
        z_j_new = p_j["position"][2]
        if "anchor" in p_j and "bbox_center" in p_j:
            x_j_new, z_j_new = get_object_center_from_anchor(p_j["position"], p_j["anchor"], p_j["bbox_center"])

        # Check if collision resolved with proper clearance
        poly_i = footprint_polygon(x_i, z_i, p_i["bbox"][0] + clearance, p_i["bbox"][1] + clearance,
                                   p_i.get("rotation_yaw", 0))
        poly_j = footprint_polygon(x_j_new, z_j_new, p_j["bbox"][0] + clearance, p_j["bbox"][1] + clearance,
                                   p_j.get("rotation_yaw", 0))

        if not poly_i.intersects(poly_j):
            return {"dx": nx * step * (s + 1), "dz": nz * step * (s + 1)}, True

    return {"dx": nx * step * max_steps, "dz": nz * step * max_steps}, False


def resolve_rotate(placements: List[Dict], i: int, j: int, clearance: float = 0.6, max_angle_deg=30, step_deg=5):
    """Try rotating object j to resolve collision with object i"""
    p_i = placements[i]
    p_j = placements[j]
    original = p_j.get("rotation_yaw", 0.0)

    # Get centers
    x_i, z_i = p_i["position"][0], p_i["position"][2]
    x_j, z_j = p_j["position"][0], p_j["position"][2]

    if "anchor" in p_i and "bbox_center" in p_i:
        x_i, z_i = get_object_center_from_anchor(p_i["position"], p_i["anchor"], p_i["bbox_center"])
    if "anchor" in p_j and "bbox_center" in p_j:
        x_j, z_j = get_object_center_from_anchor(p_j["position"], p_j["anchor"], p_j["bbox_center"])

    for sign in (+1, -1):
        angle = step_deg * sign
        while abs(angle) <= max_angle_deg:
            p_j["rotation_yaw"] = original + angle

            poly_i = footprint_polygon(x_i, z_i, p_i["bbox"][0] + clearance, p_i["bbox"][1] + clearance,
                                       p_i.get("rotation_yaw", 0))
            poly_j = footprint_polygon(x_j, z_j, p_j["bbox"][0] + clearance, p_j["bbox"][1] + clearance,
                                       p_j.get("rotation_yaw", 0))

            if not poly_i.intersects(poly_j):
                return {"angle_deg": angle}, True

            angle += step_deg * sign

    # Revert rotation
    p_j["rotation_yaw"] = original
    return {"angle_deg": 0}, False


def check_and_repair(placements: List[Dict], room_w: float, room_d: float, clearance: float = 0.6,
                     wall_clearance: float = 0.1, max_repair_steps: int = 5):
    """
    Check layout for violations and attempt repairs.

    Args:
        placements: List of object placements
        room_w: Room width in meters
        room_d: Room depth in meters
        clearance: Minimum clearance between objects (default 0.6m)
        wall_clearance: Minimum clearance from walls (default 0.1m)
        max_repair_steps: Maximum repair attempts (default 5)

    Returns:
        (placements, repairs, success, violations)
    """
    repairs = []
    attempted_violations = set()  # Track which violations we've tried to fix

    for attempt in range(max_repair_steps):
        out_of_bounds_violations = check_out_of_bounds(placements, room_w, room_d, wall_clearance)
        collision_violations = check_collisions(placements, clearance)

        if not out_of_bounds_violations and not collision_violations:
            return placements, repairs, True, []

        # Handle out_of_bounds by nudging toward center
        for violation in out_of_bounds_violations:
            idx = violation["index"]
            violation_key = f"oob_{idx}"

            if violation_key in attempted_violations:
                continue  # Already tried fixing this

            attempted_violations.add(violation_key)
            p = placements[idx]

            # Compute vector from center to object and nudge opposite direction
            cx, cz = 0.0, 0.0
            dx = p["position"][0] - cx
            dz = p["position"][2] - cz
            norm = math.hypot(dx, dz) or 1.0
            nx, nz = -dx / norm, -dz / norm

            oldpos = (p["position"][0], p["position"][2])
            p["position"][0] += nx * 0.2  # Nudge 20cm toward center
            p["position"][2] += nz * 0.2

            repairs.append({
                "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                "placement_id": p.get("id", ""),
                "category": p.get("category", ""),
                "violation": "out_of_bounds",
                "attempted_fix": {
                    "type": "nudge_into_room",
                    "old_pos": oldpos,
                    "new_pos": (p["position"][0], p["position"][2])
                }
            })

        # Handle collisions
        for violation in collision_violations:
            i, j = violation["indices"]
            violation_key = f"coll_{i}_{j}"

            if violation_key in attempted_violations:
                continue

            attempted_violations.add(violation_key)

            # Try nudge j away from i
            attempt_result, ok = resolve_simple_nudge(placements, i, j, clearance)
            if ok:
                repairs.append({
                    "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                    "placement_id": placements[j].get("id", ""),
                    "category": placements[j].get("category", ""),
                    "violation": "collision",
                    "attempted_fix": {
                        "type": "nudge_away",
                        "from": placements[i].get("id", ""),
                        "dx_dz": attempt_result
                    }
                })
                continue

            # Try rotate j
            attempt2, ok2 = resolve_rotate(placements, i, j, clearance)
            if ok2:
                repairs.append({
                    "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                    "placement_id": placements[j].get("id", ""),
                    "category": placements[j].get("category", ""),
                    "violation": "collision",
                    "attempted_fix": {
                        "type": "rotate",
                        "from": placements[i].get("id", ""),
                        "angle": attempt2
                    }
                })
                continue

            # Both failed
            repairs.append({
                "timestamp": datetime.datetime.now().strftime('%m_%d__%H_%M_%S'),
                "placement_id": placements[j].get("id", ""),
                "category": placements[j].get("category", ""),
                "violation": "collision_unresolved",
                "attempted_fix": {"type": "exhausted"}
            })

            # Break repair loop if we can't fix this collision
            break

    # Final check
    final_oob = check_out_of_bounds(placements, room_w, room_d, wall_clearance)
    final_coll = check_collisions(placements, clearance)

    if final_oob or final_coll:
        final_violations = {
            "out_of_bounds": final_oob,
            "collisions": final_coll
        }
        return placements, repairs, False, [final_violations]

    return placements, repairs, True, []