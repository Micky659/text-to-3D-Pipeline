# assemble_scene_simple_two_walls.py
# Usage:
# blender --background --python assemble_scene_simple_two_walls.py -- --manifest path/to/scene_manifest.json --out out.blend --export_glb out.glb

import bpy
import json
import sys
import math
import random
from pathlib import Path
from mathutils import Vector, Euler, Matrix


# --------------------------
# CLI arg parsing helper
# --------------------------
def parse_args():
    import argparse
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=False, default="output/scene_result.blend")
    p.add_argument("--export_glb", required=False, default=None)
    p.add_argument("--seed", required=False, type=int, default=None)
    p.add_argument("--iso_elev", required=False, type=float, default=55.0)
    p.add_argument("--iso_azim", required=False, type=float, default=45.0)
    p.add_argument("--ortho_scale", required=False, type=float, default=6.0)
    return p.parse_args(argv)


args = parse_args()
if args.seed is not None:
    random.seed(args.seed)

manifest_path = Path(args.manifest)
out_blend = Path(args.out)
export_glb = Path(args.export_glb) if args.export_glb else None

# asset folders (script's directory)
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
static_dir = BASE_DIR.parent / 'static'
WINDOWS_FOLDER = static_dir / "windows"
WALL_ART_FOLDER = static_dir / "wall_art"
DOORS_FOLDER = static_dir / "doors"


# --------------------------
# Utility: clear default scene
# --------------------------
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for coll in list(bpy.data.collections):
        if coll.name != "Collection":
            try:
                bpy.data.collections.remove(coll)
            except Exception:
                pass
    for block in list(bpy.data.meshes):
        if block.users == 0:
            try:
                bpy.data.meshes.remove(block)
            except Exception:
                pass


clear_scene()

# --------------------------
# Load manifest
# --------------------------
with open(manifest_path, "r") as f:
    manifest = json.load(f)

room = manifest.get("room")
objects = manifest.get("objects", [])


# --------------------------
# Helpers: coordinate conversions
# --------------------------
def manifest_to_blender(vec):
    # manifest: (x, y, z) with Y=up -> blender: (x, z, y) with Z=up
    return Vector((float(vec[0]), float(vec[2]), float(vec[1])))


def anchor_to_blender(vec):
    return manifest_to_blender(vec)


def yaw_to_blender_z(yaw_deg):
    # manifest yaw = degrees about up (Y). In Blender up is Z -> rotate about Z by same angle.
    return math.radians(float(yaw_deg))


def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def make_flat_shaded(obj):
    if obj and obj.type == 'MESH':
        for p in obj.data.polygons:
            p.use_smooth = False
        if not obj.data.materials:
            m = bpy.data.materials.new(obj.name + "_mat")
            m.use_nodes = True
            obj.data.materials.append(m)


def assign_solid_color(obj, rgb, name=None, roughness=0.6):
    if obj is None or obj.type != 'MESH':
        return
    matname = name or (obj.name + "_mat")
    mat = bpy.data.materials.new(matname)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    try:
        principled.inputs['Roughness'].default_value = roughness
    except Exception:
        pass
    links.new(principled.outputs['BSDF'], out.inputs['Surface'])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)


# --------------------------
# Room dims and geometry (ONLY TWO WALLS: Back + Side)
# --------------------------
room_w = float(room.get("w", 4.0))
room_d = float(room.get("d", 4.0))
room_h = float(room.get("h", 3.0))
wall_thickness = 0.12

# Floor
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "Floor"
floor.scale = (room_w, room_d, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
make_flat_shaded(floor)

# Back wall (along X at +Y/2)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, room_d / 2.0, room_h / 2.0))
back_wall = bpy.context.active_object
back_wall.name = "BackWall"
back_wall.scale = (room_w, wall_thickness, room_h)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
make_flat_shaded(back_wall)

# Side wall (along Y at -X/2)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-room_w / 2.0, 0.0, room_h / 2.0))
side_wall = bpy.context.active_object
side_wall.name = "SideWall"
side_wall.scale = (wall_thickness, room_d, room_h)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
make_flat_shaded(side_wall)

WALL_PALETTE = ["#8B7D6B", "#6B5D54", "#7C6A5B", "#5E5246"]  # warm taupes / browns
FLOOR_PALETTE = ["#4A3C28", "#5C4A3A", "#6B4F35"]  # dark wood tones
RUG_PALETTE = ["#6B655F", "#5A544D", "#7A746F"]  # muted browns / grays

back_col = hex_to_rgb(random.choice(WALL_PALETTE))
side_col = hex_to_rgb(random.choice([c for c in WALL_PALETTE if hex_to_rgb(c) != back_col]))
assign_solid_color(back_wall, back_col, name="BackWall_mat", roughness=0.55)
assign_solid_color(side_wall, side_col, name="SideWall_mat", roughness=0.55)
assign_solid_color(floor, hex_to_rgb(random.choice(FLOOR_PALETTE)), name="Floor_mat", roughness=0.6)

# Rug: scale relative to floor (centered in room)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, 0.01))
rug = bpy.context.active_object
rug.name = "Rug"
rug.scale = (room_w * 0.5, room_d * 0.5, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
assign_solid_color(rug, hex_to_rgb(random.choice(RUG_PALETTE)), name="RugMat", roughness=0.7)
make_flat_shaded(rug)


# --------------------------
# Fixed static asset placement function
# --------------------------
def place_one_asset_from_folder(folder_path, kind, wall=None):
    """
    Import one random glTF/glb from folder_path and place it on either back or side wall.
    kind: 'window', 'wall_art', 'door'
    """
    folder = Path(folder_path)
    if not folder.exists():
        print(f"[place] folder doesn't exist: {folder}")
        return None

    # # Find all subdirectories (each contains one asset)
    # asset_dirs = [d for d in folder.iterdir() if d.is_dir()]
    # if not asset_dirs:
    #     print(f"[place] no asset directories in {folder}")
    #     return None
    #
    # # Choose random asset directory
    # chosen_dir = random.choice(asset_dirs)
    chosen_dir = folder

    # Find glTF/GLB file
    gltf = None
    for name in ["scene.glb", "scene.gltf"]:
        p = chosen_dir / name
        if p.exists():
            gltf = p
            break

    if gltf is None:
        # Fallback: any .glb/.gltf file
        for p in chosen_dir.iterdir():
            if p.suffix.lower() in (".glb", ".gltf"):
                gltf = p
                break

    if gltf is None:
        print(f"[place] no glTF/GLB in {chosen_dir}")
        return None

    print(f"[place] importing {kind} from {gltf}")

    # Import the glTF
    try:
        # Store current selection
        prev_selected = list(bpy.context.selected_objects)
        bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.import_scene.gltf(filepath=str(gltf))
        imported = [o for o in bpy.context.selected_objects if o not in prev_selected]
    except Exception as e:
        print(f"Import failed: {e}")
        return None

    if not imported:
        print("[place] no objects imported")
        return None

    # Apply textures if needed
    # apply_textures_to_imported(imported, chosen_dir)

    # Create empty parent for easier manipulation
    root = bpy.data.objects.new(f"{kind}_root", None)
    bpy.context.scene.collection.objects.link(root)

    # Parent all imported objects to root
    for obj in imported:
        obj.parent = root

    # Get bounding box of imported objects
    def get_world_bbox(objs):
        coords = []
        for obj in objs:
            if obj.type == 'MESH':
                mesh = obj.data
                mw = obj.matrix_world
                coords.extend([mw @ v.co for v in mesh.vertices])
        if not coords:
            return Vector((0, 0, 0)), Vector((1, 1, 1))
        xs = [c.x for c in coords]
        ys = [c.y for c in coords]
        zs = [c.z for c in coords]
        return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))

    def clone_object_with_children(obj, collection=None):
        """Duplicate an object and all its children (for GLTF imports with empties)."""
        collection = collection or bpy.context.collection

        # Keep a map old→new so we can preserve parenting
        obj_map = {}

        def recursive_clone(o, parent_new=None):
            new_o = o.copy()
            if o.data:  # if it's a mesh/curve/etc
                new_o.data = o.data.copy()
            collection.objects.link(new_o)
            obj_map[o] = new_o
            if parent_new:
                new_o.parent = parent_new
            for child in o.children:
                recursive_clone(child, new_o)
            return new_o

        return recursive_clone(obj)

    # # Choose wall randomly
    # if wall is None:
    #     wall = random.choice(['back', 'side'])

    if kind == 'window':
        target_width = random.uniform(0.18 * room_w, 0.25 * room_w)
        target_height = random.uniform(0.5 * room_h, 0.7 * room_h)
        z_offset = random.uniform(0.35 * room_h, 0.40 * room_h)  # mid-height
    elif kind == 'wall_art':
        target_width = random.uniform(0.05 * room_w, 0.12 * room_w)
        target_height = random.uniform(0.15 * room_h, 0.25 * room_h)
        z_offset = random.uniform(0.4 * room_h, 0.6 * room_h)  # eye level
    else:  # door
        target_width = random.uniform(0.05 * room_w, 0.07 * room_w)
        target_height = min(0.7 * room_h, room_h - 0.4)
        z_offset = 0.0  # Doors at floor level

    # Get current bbox
    bb_min, bb_max = get_world_bbox(imported)
    current_size = bb_max - bb_min

    # Calculate scale to fit target dimensions
    scale_x = target_width / max(current_size.x, 0.01)
    scale_y = target_width / max(current_size.y, 0.01)  # Use width for depth too
    scale_z = target_height / max(current_size.z, 0.01)

    # Use uniform scale (smallest to maintain proportions)
    uniform_scale = min(scale_x, scale_y, scale_z)
    root.scale = (uniform_scale, uniform_scale, uniform_scale)

    # Position on wall
    margin = 0.3
    wall_offset = 0.01  # Small offset from wall

    if wall == 'back':
        if kind == 'door':
            rx = math.radians(-90.0)
            root.rotation_euler = (rx, 0, 0)
        else:
            root.rotation_euler = (0, 0, 0)
        # Back wall positioning
        root.location.y = room_d / 2.0 - wall_thickness / 2.0 - wall_offset
        # Random position along X
        max_x = room_w / 2.0 - target_width / 2.0 - margin
        min_x = -max_x
        center_x = random.uniform(min_x, max_x)
        root.location.x = center_x
        # No rotation needed for back wall
        # --- OPTIONAL: clone another object of the same type (e.g. window) ---
        if kind == 'window':
            spacing = random.uniform(1.5, 2.0)  # distance between windows
            half_span = spacing / 2 + target_width / 2  # left/right extents

            # compute safe X range to keep both windows inside wall
            max_x = room_w / 2.0 - half_span - margin
            min_x = -max_x
            center_x = random.uniform(min_x, max_x)

            # first window
            root.location.x = center_x - spacing / 2

            # 50% chance of second window
            # if random.random() < 0.5:
            clone = clone_object_with_children(root)
            clone.location.x = center_x + spacing / 2
            clone.location.y = root.location.y
            clone.location.z = z_offset
    else:
        if kind == 'door':
            rx = math.radians(-90.0)
            root.rotation_euler = (rx, 0, math.radians(90))
        else:
            root.rotation_euler = (0, 0, math.radians(90))
        # Side wall positioning
        root.location.x = -room_w / 2.0 + wall_thickness / 2.0 + wall_offset
        # Random position along Y
        max_y = room_d / 2.0 - target_width / 2.0 - margin
        min_y = -max_y
        root.location.y = random.uniform(min_y, max_y)
        # Rotate 90 degrees for side wall

    if kind == 'door':
        # Apply scale to update matrix_world
        bpy.context.view_layer.update()

        # Compute bottom of the door relative to its root origin
        bb_min_local = Vector((float('inf'), float('inf'), float('inf')))
        for obj in imported:
            if obj.type == 'MESH':
                for v in obj.data.vertices:
                    co_world = obj.matrix_world @ v.co
                    bb_min_local.x = min(bb_min_local.x, co_world.x)
                    bb_min_local.y = min(bb_min_local.y, co_world.y)
                    bb_min_local.z = min(bb_min_local.z, co_world.z)

        # Compute offset to bring bottom to z_offset (usually 0)
        z_bottom = z_offset
        delta_z = z_bottom - bb_min_local.z
        root.location.z += delta_z

    else:
        # Set Z position
        root.location.z = z_offset

    # Apply flat shading
    for obj in imported:
        if obj.type == 'MESH':
            make_flat_shaded(obj)

    print(f"[place] placed {kind} on {wall} wall at {root.location}")
    return root, wall


# Place static assets
placed_statics = []

if WINDOWS_FOLDER.exists():
    result, wall = place_one_asset_from_folder(WINDOWS_FOLDER, 'window', 'back')
    if result:
        placed_statics.append(result)

# if WALL_ART_FOLDER.exists():
#     result = place_one_asset_from_folder(WALL_ART_FOLDER, 'wall_art')
#     if result:
#         placed_statics.append(result)

if DOORS_FOLDER.exists():
    result = place_one_asset_from_folder(DOORS_FOLDER, 'door', 'side')
    if result:
        placed_statics.append(result)


# --------------------------
# Import and place generated assets from manifest
# --------------------------
def import_asset(path: str):
    path = Path(path)
    if not path.exists():
        print("Asset not found:", path)
        return None

    ext = path.suffix.lower()
    objs = []

    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
        objs = [o for o in bpy.context.selected_objects]
        # Create collection for organization
        coll = bpy.data.collections.new(path.stem)
        bpy.context.scene.collection.children.link(coll)
        for o in objs:
            if o.name in bpy.context.scene.collection.objects:
                try:
                    bpy.context.scene.collection.objects.unlink(o)
                except Exception:
                    pass
            if o.name not in coll.objects:
                coll.objects.link(o)
        return objs[0] if objs else None
    elif ext == ".obj":
        bpy.ops.import_scene.obj(filepath=str(path))
        objs = [o for o in bpy.context.selected_objects]
        return objs[0] if objs else None
    else:
        print("Unsupported asset ext:", ext)
        return None


placed_objects = []
for p in objects:
    asset_path = p.get("asset")
    meta = p.get("metadata", {}) or {}
    if not asset_path:
        print("No asset for object", p)
        continue

    obj_inst = import_asset(asset_path)
    if obj_inst is None:
        continue

    # Apply flat shading
    for mesh in [obj_inst] + list(obj_inst.children_recursive):
        if mesh.type == 'MESH':
            make_flat_shaded(mesh)

    # --- NEW: Scaling Logic ---
    # Get the target bounding box from the main object data
    target_bbox = p.get("bbox")
    # Get the original bounding box from the asset's metadata
    original_bbox = meta.get("bbox")

    if target_bbox and original_bbox:
        # Calculate the scale factor for each axis
        scale_x = target_bbox[0] / original_bbox[0]
        scale_y = target_bbox[1] / original_bbox[1]
        scale_z = target_bbox[2] / original_bbox[2]

        # Apply the new scale to the object instance
        obj_inst.scale = (scale_x, scale_y, scale_z)
    # --- End of NEW Scaling Logic ---

    # Position and rotate
    anchor = meta.get("anchor", [0.0, 0.0, 0.0])
    anchor_b = anchor_to_blender(anchor)
    pos = manifest_to_blender(p["position"])
    yaw = p.get("rotation_yaw", 0.0)
    yaw_r = yaw_to_blender_z(yaw)

    obj_inst.rotation_euler = Euler((0.0, 0.0, yaw_r), 'XYZ')

    # Apply anchor offset
    rot_mat = obj_inst.rotation_euler.to_matrix().to_4x4()
    anchor_vec_local = Vector((anchor_b[0], anchor_b[1], anchor_b[2], 1.0))
    rotated_anchor = rot_mat @ anchor_vec_local
    rotated_anchor_vec = Vector((rotated_anchor[0], rotated_anchor[1], rotated_anchor[2]))
    obj_inst.location = pos - rotated_anchor_vec

    placed_objects.append(obj_inst)


# --------------------------
# Lighting: Sun + area lights
# --------------------------


def add_sun(strength=2.8):
    bpy.ops.object.light_add(type='SUN', location=(room_w, -room_d, room_h * 1.5))
    sun = bpy.context.active_object
    sun.data.energy = strength
    sun.rotation_euler = Euler((math.radians(40), 0, math.radians(30)), 'XYZ')
    sun.data.angle = math.radians(2.0)
    return sun


def add_area(location, size=1.0, energy=120.0):
    bpy.ops.object.light_add(type='AREA', location=location)
    a = bpy.context.active_object
    a.data.size = size
    a.data.energy = energy
    return a

# Clear existing lights
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)


add_sun()
# add_area((room_w / 2.0, -room_d / 2.0, room_h * 1.2), size=2.5, energy=300.0)
add_area((-room_w / 3.0, room_d / 3.0, room_h * 0.9), size=1.2, energy=120.0)


# --------------------------
# Render engine setup
# --------------------------
def available_engines():
    try:
        enum_items = bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
        return [it.identifier for it in enum_items]
    except Exception:
        try:
            return [it.identifier for it in bpy.context.scene.bl_rna.properties['engine'].enum_items]
        except Exception:
            return []


engines = available_engines()
preferred = ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES', 'BLENDER_WORKBENCH']
chosen = None
for p in preferred:
    if p in engines:
        chosen = p
        break

if not chosen:
    chosen = engines[0] if engines else 'CYCLES'

try:
    bpy.context.scene.render.engine = chosen
except Exception:
    pass

# Configure Eevee settings
if bpy.context.scene.render.engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
    try:
        bpy.context.scene.eevee.use_gtao = True
        bpy.context.scene.eevee.taa_render_samples = 64
        try:
            bpy.context.scene.eevee.use_ssr = True
        except Exception:
            pass
    except Exception:
        pass


# --------------------------
# Camera setup
# --------------------------
def setup_isometric_camera(elev_deg=55.0, azim_deg=45.0, ortho_scale=6.0):
    theta = math.radians(azim_deg)
    phi = math.radians(elev_deg)
    r = max(room_w, room_d) * 2.5
    x = r * math.cos(theta) * math.cos(phi)
    y = r * math.sin(theta) * math.cos(phi)
    z = abs(r * math.sin(phi)) + room_h * 0.3

    bpy.ops.object.camera_add(location=(x, y, z))
    cam = bpy.context.active_object
    cam.name = "IsoCam"

    # Point camera at room center
    dir_vec = Vector((0.0, 0.0, room_h / 3.0)) - Vector((x, y, z))
    cam.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ortho_scale
    bpy.context.scene.camera = cam
    return cam


cam = setup_isometric_camera(elev_deg=args.iso_elev, azim_deg=args.iso_azim, ortho_scale=args.ortho_scale)

# --------------------------
# World environment
# --------------------------
world = bpy.data.worlds.get("World")
if world:
    world.use_nodes = True
    nodes = world.node_tree.nodes
    bg = nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.05, 1)  # dark gray instead of white
        bg.inputs[1].default_value = 1.0  # strength

# --------------------------
# Save scene and export
# --------------------------
out_blend = Path(args.out)
out_blend.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
print(f"Scene saved to: {out_blend}")

if export_glb:
    try:
        bpy.ops.export_scene.gltf(filepath=str(export_glb), export_format='GLB', export_apply=True)
        print(f"Exported GLB to: {export_glb}")
    except Exception as e:
        print(f"GLB export failed: {e}")

print("Scene assembly complete!")