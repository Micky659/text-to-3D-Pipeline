import trimesh
import numpy as np
from pathlib import Path
import json
from typing import Dict, Any


def save_obj_from_coords(coords_list, out_obj_path: Path):
    sample = coords_list[0]
    arr = None
    try:
        import numpy as np
        a = np.asarray(sample)
        if a.ndim == 3 and a.shape[1] in (3, 4):  # faces (triangles/quads)
            # build vertex list and face indices
            verts = []
            faces = []
            vid_map = {}
            vid = 0
            for f in a:
                face_idxs = []
                for v in f:
                    key = tuple(float(x) for x in v.tolist())
                    if key not in vid_map:
                        vid_map[key] = vid
                        verts.append(list(key))
                        vid += 1
                    face_idxs.append(vid_map[key])
                # if quad, triangulate
                if len(face_idxs) == 3:
                    faces.append(face_idxs)
                elif len(face_idxs) == 4:
                    faces.append([face_idxs[0], face_idxs[1], face_idxs[2]])
                    faces.append([face_idxs[0], face_idxs[2], face_idxs[3]])
            mesh = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)
            mesh.export(str(out_obj_path))
            return True
    except Exception:
        pass
    # Fallback: Write json with coords for manual handling and convert externally
    fallback = out_obj_path.with_suffix(".json")
    with open(fallback, "w") as f:
        json.dump({"coords_samples": coords_list}, f)
    return False


def load_mesh(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load_mesh(str(path), process=True)
    if isinstance(mesh, trimesh.Scene):
        # convert scene to single mesh by concatenation
        m = trimesh.util.concatenate([g for g in mesh.geometry.values()])
        return m
    return mesh

def compute_metadata(mesh: trimesh.Trimesh) -> Dict[str, Any]:
    metadata = {}
    extents = mesh.extents.tolist()  # [x_size, y_size, z_size]
    # metadata["bbox"] = [float(extents[0]), float(extents[2]), float(extents[1])]  # convert to w,d,h ordering (X,Z,Y)
    # canonical up is +Y and forward is -Z
    metadata["up"] = [0.0, 1.0, 0.0]
    metadata["forward"] = [0.0, 0.0, -1.0]


    verts = mesh.vertices.copy()


    # anchor: centroid of floor-contact vertices (min y tolerance)
    ys = verts[:, 1]
    miny = float(np.min(ys))
    tol = 1e-3
    contact_idx = np.where(ys <= (miny + tol))[0]
    if contact_idx.size > 0:
        anchor_pt = verts[contact_idx].mean(axis=0).tolist()
    else:
        anchor_pt = verts.mean(axis=0).tolist()
    metadata["anchor"] = [float(anchor_pt[0]), float(anchor_pt[1]), float(anchor_pt[2])]

    # bbox center and extents
    metadata["bbox_center"] = mesh.bounding_box.centroid.tolist()
    metadata["num_faces"] = int(len(mesh.faces))

    return metadata
