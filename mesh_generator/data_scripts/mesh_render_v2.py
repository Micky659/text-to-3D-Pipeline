import numpy as np
import math
import torch
from pathlib import Path

# Target dimensions for testing (in meters) [W, D, H]
TARGET_DIMENSIONS = {
    "motorcycle bike": [0.8, 2.2, 1.2],
    "chair": [0.5, 0.5, 0.95],
    "lamp": [0.4, 0.4, 1.6],
    "bus autobus coach charabanc double-decker jitney motorbus motorcoach omnibus passenger vehi": [2.5, 12.0, 3.2],
    "ashcan trash can garbage can wastebin ash bin ash-bin ashbin dustbin trash barrel trash bin": [0.4, 0.2, 0.5],
    "sofa couch lounge": [2.2, 1.0, 0.9],
    "bench": [1.2, 0.4, 0.5],
    "bookshelf": [0.8, 0.3, 1.8],
    "microwave microwave oven": [0.5, 0.4, 0.3],
    "bottle": [0.08, 0.08, 0.25],
    "bag traveling bag travelling bag grip suitcase": [0.4, 0.2, 0.5],
    "pot flowerpot": [0.3, 0.3, 0.4],
    "loudspeaker speaker speaker unit loudspeaker system speaker system": [0.4, 0.4, 1.0],
    "birdhouse": [0.25, 0.25, 0.3],
    "file file cabinet filing cabinet": [0.6, 0.6, 1.2],
    "printer printing machine": [0.45, 0.45, 0.25],
    "bathtub bathing tub bath tub": [0.8, 1.6, 0.6],
    "piano pianoforte forte-piano": [1.5, 2.0, 1.2],
    "car auto automobile machine motorcar": [1.8, 4.5, 1.5],
    "mailbox letter box": [0.3, 0.3, 1.2],
    "table": [1.5, 0.8, 0.75],
    "tower": [5.0, 5.0, 30.0],
    "basket handbasket": [0.35, 0.35, 0.25],
    "stove": [0.6, 0.6, 0.9],
    "dishwasher dish washer dishwashing machine": [0.6, 0.6, 0.85],
    "skateboard": [0.25, 0.8, 0.12],
    "washer automatic washer washing machine": [0.6, 0.6, 0.85],
    "bed": [1.5, 2.0, 0.6],
    "cabinet": [0.9, 0.45, 1.2],
    "display video display": [0.6, 0.05, 0.4],
    "pillow": [0.6, 0.4, 0.15]
}



def orient_triangle_upward(v1, v2, v3):
    """Ensure triangle normal points upward"""
    edge1 = v2 - v1
    edge2 = v3 - v1
    normal = np.cross(edge1, edge2)
    normal = normal / (np.linalg.norm(normal) + 1e-8)

    up = np.array([0, 1, 0])
    if np.dot(normal, up) < 0:
        v1, v3 = v3, v1
    return v1, v2, v3


def get_angle(v1, v2, v3):
    """Calculate interior angle at v1"""
    v1, v2, v3 = orient_triangle_upward(v1, v2, v3)
    vec1 = v2 - v1
    vec2 = v3 - v1
    cos_angle = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2) + 1e-8)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle_rad = np.arccos(cos_angle)
    return math.degrees(angle_rad)


def extract_vertices_from_mesh(mesh_output):
    """Extract vertices from mesh (tensor, mask) format"""
    all_vertices = []

    mesh_list = mesh_output if isinstance(mesh_output, list) else [mesh_output]

    for mesh_item in mesh_list:
        tensor, mask = mesh_item

        for tensor_batch, mask_batch in zip(tensor, mask):
            vertices = tensor_batch[mask_batch].cpu().numpy().reshape(-1, 3)
            all_vertices.append(vertices)

    if all_vertices:
        return np.vstack(all_vertices)
    else:
        return np.array([]).reshape(0, 3)


def extract_vertices_faces_from_mesh(mesh_output):
    all_vertices = []
    all_faces = []

    mesh_list = mesh_output if isinstance(mesh_output, list) else [mesh_output]

    for mesh_item in mesh_list:
        tensor, mask = mesh_item
        for tensor_batch, mask_batch in zip(tensor, mask):
            vertices = tensor_batch[mask_batch].cpu().numpy().reshape(-1, 3)
            all_vertices.append(vertices)

    if not all_vertices:
        return np.array([]).reshape(0, 3), np.array([]).reshape(0, 3)

    vertices = np.vstack(all_vertices)
    num_vertices = len(vertices)
    if num_vertices % 3 != 0:
        num_faces = num_vertices // 3
        vertices = vertices[:num_faces * 3]
    else:
        num_faces = num_vertices // 3

    # Calculate mesh center for face orientation
    mesh_center = np.mean(vertices, axis=0)

    # Compute faces using the same logic you provided
    for i in range(0, len(vertices), 3):
        v1, v2, v3 = vertices[i], vertices[i + 1], vertices[i + 2]

        normal = np.cross(v2 - v1, v3 - v1)

        # Determine direction for face orientation
        if get_angle(v1, v2, v3) > 60:
            direction_vector = mesh_center - np.mean([v1, v2, v3], axis=0)
            direction_vector = -direction_vector
        else:
            direction_vector = np.array([0, 1, 0])

        # Reorder vertices if needed
        if np.dot(normal, direction_vector) > 0:
            order = [0, 1, 2]
        else:
            order = [0, 2, 1]

        reordered_vertices = [v1, v2, v3][order[0]], [v1, v2, v3][order[1]], [v1, v2, v3][order[2]]

        # Find indices of reordered vertices in the global vertex array
        indices = [
            np.where((vertices == vertex).all(axis=1))[0][0]
            for vertex in reordered_vertices
        ]

        all_faces.append(indices)

    faces = np.array(all_faces, dtype=np.int32)

    return vertices, faces


def scale_mesh_to_target(vertices, target_bbox):
    """
    Scale mesh to match target bounding box dimensions.

    Args:
        vertices: numpy array of shape (N, 3)
        target_bbox: [width, depth, height] in meters (X, Z, Y ordering)

    Returns:
        scaled vertices centered at origin
    """
    if len(vertices) == 0:
        return vertices

    # Calculate current bbox
    min_coords = np.min(vertices, axis=0)
    max_coords = np.max(vertices, axis=0)
    current_dims = max_coords - min_coords

    # Target dimensions in [X, Z, Y] order to match vertices [X, Y, Z]
    target_x = target_bbox[0]  # width
    target_z = target_bbox[1]  # depth
    target_y = target_bbox[2]  # height

    # Calculate scale factors
    scale_x = target_x / (current_dims[0] + 1e-8)
    scale_y = target_y / (current_dims[1] + 1e-8)
    scale_z = target_z / (current_dims[2] + 1e-8)

    # Center at origin before scaling
    center = (min_coords + max_coords) / 2
    vertices_centered = vertices - center

    # Apply scaling
    vertices_scaled = vertices_centered * np.array([scale_x, scale_y, scale_z])

    return vertices_scaled


def compute_mesh_metadata(vertices):
    """
    Compute metadata from vertices.

    Args:
        vertices: numpy array of shape (N, 3)

    Returns:
        dict with bbox, anchor, bbox_center, num_faces
    """
    if len(vertices) == 0:
        return {
            "bbox": [0.0, 0.0, 0.0],
            "anchor": [0.0, 0.0, 0.0],
            "bbox_center": [0.0, 0.0, 0.0],
            "num_faces": 0
        }

    # Get min and max
    min_coords = np.min(vertices, axis=0)
    max_coords = np.max(vertices, axis=0)

    # Compute bbox in W, D, H order (X, Z, Y)
    width = float(max_coords[0] - min_coords[0])
    depth = float(max_coords[2] - min_coords[2])
    height = float(max_coords[1] - min_coords[1])

    # Compute bbox center
    center_x = float((min_coords[0] + max_coords[0]) / 2)
    center_y = float((min_coords[1] + max_coords[1]) / 2)
    center_z = float((min_coords[2] + max_coords[2]) / 2)

    # Compute anchor: centroid of floor-contact vertices
    ys = vertices[:, 1]
    miny = float(np.min(ys))
    tol = 1e-3
    contact_idx = np.where(ys <= (miny + tol))[0]

    if contact_idx.size > 0:
        anchor_pt = vertices[contact_idx].mean(axis=0)
    else:
        anchor_pt = vertices.mean(axis=0)

    anchor_x = float(anchor_pt[0])
    anchor_y = float(anchor_pt[1])
    anchor_z = float(anchor_pt[2])

    num_faces = len(vertices) // 3

    return {
        "bbox": [round(width, 1), round(depth, 1), round(height, 1)],
        "anchor": [round(anchor_x, 1), round(anchor_y, 1), round(anchor_z, 1)],
        "bbox_center": [round(center_x, 1), round(center_y, 1), round(center_z, 1)],
        "num_faces": num_faces
    }


from difflib import get_close_matches

def get_target_dimensions(category, custom_target_dims=None):
    # 1. Direct override
    if custom_target_dims:
        return custom_target_dims

    # 2. Exact key match
    if category in TARGET_DIMENSIONS:
        return TARGET_DIMENSIONS[category]

    # 3. Substring or partial match
    for key in TARGET_DIMENSIONS.keys():
        if category.lower() in key.lower() or key.lower() in category.lower():
            return TARGET_DIMENSIONS[key]

    # 4. Fuzzy match (handles similar wording)
    best_match = get_close_matches(category.lower(), TARGET_DIMENSIONS.keys(), n=1, cutoff=0.6)
    if best_match:
        return TARGET_DIMENSIONS[best_match[0]]

    # 5. No match found
    return None




def save_mesh_for_scene(path, mesh_output, category, custom_target_dims=None):
    """
    Save mesh for scene generation pipeline with proper scaling and orientation.
    This is the function to use in your pipeline instead of mesh_render.save_rendering.

    Args:
        path: output file path
        mesh_output: (tensor, mask) tuple from transformer.generate()
        category: object category (e.g., 'bed', 'chair')
        custom_target_dims: optional [w, d, h] override, if None uses TARGET_DIMENSIONS

    Returns:
        dict with metadata: bbox, anchor, bbox_center, num_faces
    """
    # Extract vertices
    vertices = extract_vertices_from_mesh(mesh_output)

    if len(vertices) == 0:
        print(f"Warning: No vertices to save for {path}")
        return None

    # Get target dimensions
    # target_dims = get_target_dimensions(category, custom_target_dims)
    # target_dims = custom_target_dims if custom_target_dims else TARGET_DIMENSIONS.get(category, None)
    #
    # for key in TARGET_DIMENSIONS.keys():
    #     if key in category:
    #         target_dims = TARGET_DIMENSIONS.get(key, None)

    # Scale if target dimensions available
    # if target_dims is not None:
    #     vertices = scale_mesh_to_target(vertices, target_dims)
    # else:
    #     print(f"Warning: No target dimensions for category '{category}', saving unscaled")

    # Prepare OBJ content
    all_vertices = []
    all_faces = []

    # Write vertices
    for vertex in vertices:
        all_vertices.append(f"v {vertex[0]} {vertex[1]} {vertex[2]}\n")

    # Calculate mesh center for face orientation
    mesh_center = np.mean(vertices, axis=0)

    # Write faces with correct orientation
    for i in range(0, len(vertices), 3):
        v1 = vertices[i]
        v2 = vertices[i + 1]
        v3 = vertices[i + 2]

        normal = np.cross(v2 - v1, v3 - v1)

        # Determine direction for face orientation
        if get_angle(v1, v2, v3) > 60:
            direction_vector = mesh_center - np.mean([v1, v2, v3], axis=0)
            direction_vector = -direction_vector
        else:
            direction_vector = np.array([0, 1, 0])

        # Reorder vertices if needed
        if np.dot(normal, direction_vector) > 0:
            order = [0, 1, 2]
        else:
            order = [0, 2, 1]

        reordered_vertices = [v1, v2, v3][order[0]], [v1, v2, v3][order[1]], [v1, v2, v3][order[2]]
        indices = [np.where((vertices == vertex).all(axis=1))[0][0] + 1 for vertex in reordered_vertices]
        all_faces.append(f"f {indices[0]} {indices[1]} {indices[2]}\n")

    # Write to file
    obj_content = "".join(all_vertices) + "".join(all_faces)
    with open(path, "w") as file:
        file.write(obj_content)

    # Compute metadata
    metadata = compute_mesh_metadata(vertices)

    print(f"[save_mesh_for_scene] Saved '{category}' to {path}")
    # if target_dims:
    #     print(f"  Scaled to: W={target_dims[0]:.2f}m, D={target_dims[1]:.2f}m, H={target_dims[2]:.2f}m")
    # print(f"  BBox: {metadata['bbox']}, Anchor: {metadata['anchor']}")

    return metadata