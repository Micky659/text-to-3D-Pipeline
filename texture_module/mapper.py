from pathlib import Path
import open3d as o3d
import numpy as np
from .config import settings
import traceback

def compute_planar_uvs(mesh_o3d: o3d.geometry.TriangleMesh, projection_plane="xz"):
    """
    Computes per-vertex UVs using planar projection onto projection_plane:
    - "xz": uses x->u, z->v (good when up=y)
    - "xy": uses x->u, y->v
    - "yz": uses y->u, z->v
    Returns triangle_uvs (3 * num_triangles x 2)
    """
    verts = np.asarray(mesh_o3d.vertices)
    if projection_plane == "xz":
        coords = verts[:, [0,2]]  # x,z
    elif projection_plane == "xy":
        coords = verts[:, [0,1]]
    else:
        coords = verts[:, [1,2]]
    # normalize to [0,1]
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    spans = maxs - mins
    spans[spans == 0] = 1.0
    norm = (coords - mins) / spans
    # build triangle_uvs
    triangles = np.asarray(mesh_o3d.triangles)
    tri_uvs = []
    for tri in triangles:
        for vi in tri:
            tri_uvs.append([float(norm[vi,0]), float(norm[vi,1])])
    return np.asarray(tri_uvs, dtype=np.float64)

def apply_texture_to_obj(obj_path: str, image_path: str, out_obj_path: str, projection_plane="xz"):
    """
    Loads OBJ with Open3D, computes planar UVs, assigns texture image and writes OBJ+MTL.
    Returns out_obj_path.
    """
    obj_path = str(Path(obj_path).resolve())
    out_obj_path = str(Path(out_obj_path).resolve())
    img_path = str(Path(image_path).resolve())

    # Load mesh
    mesh = o3d.io.read_triangle_mesh(obj_path)
    if mesh.is_empty():
        raise RuntimeError(f"Failed to read mesh from {obj_path}")

    if len(mesh.triangles) == 0:
        raise RuntimeError("Mesh has no triangles")

    if not mesh.has_vertex_normals():
        mesh.compute_vertex_normals()

    # Compute planar UVs (assuming you defined compute_planar_uvs)
    tri_uvs = compute_planar_uvs(mesh, projection_plane=projection_plane)
    mesh.triangle_uvs = o3d.utility.Vector2dVector(tri_uvs)

    # Load texture
    tex = o3d.io.read_image(img_path)
    mesh.textures = [tex]

    # Write OBJ (ensure write_triangle_uvs=True)
    print(out_obj_path)
    success = o3d.io.write_triangle_mesh(out_obj_path, mesh, write_triangle_uvs=True)
    if not success:
        raise RuntimeError(f"Open3D failed to write textured mesh to {out_obj_path}")
    return str(out_obj_path)
