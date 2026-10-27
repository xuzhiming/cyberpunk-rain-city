"""Export a web-friendly GLB from cyberpunk_city.blend (original untouched).
blender -b cyberpunk_city.blend -P blender/export_web.py -- city_raw.glb
- buildings joined into one mesh with metric window UVs (1 UV tile = 8x8 windows)
- neon tubes/panels/text joined per material, billboards with 0..1 UVs
- one hover-car template (JS clones and animates it); rain/fog/lights dropped (recreated in JS)
"""
import bpy, bmesh, sys, random
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]
random.seed(7)
D = bpy.data

def delete(obs):
    for o in list(obs):
        D.objects.remove(o, do_unlink=True)

# drop rain / fog / lights / cameras
delete([o for o in D.objects if o.name.startswith(("Rain", "Fog_", "SkyTraffic")) or o.type in ("LIGHT", "CAMERA")])
# keep a single car template
cars = [o for o in D.objects if o.name.startswith("HoverCar_") and o.type == "EMPTY"]
tmpl = D.objects["HoverCar_00"]
for c in cars:
    if c is not tmpl:
        delete(list(c.children) + [c])
delete([o for o in tmpl.children if "_Trail" in o.name])
tmpl.location = (0, 0, 0); tmpl.rotation_euler = (0, 0, 0); tmpl.scale = (1, 1, 1)
tmpl.name = "CarTemplate"

# convert text to mesh
bpy.ops.object.select_all(action="DESELECT")
for o in D.objects:
    if o.type == "FONT":
        o.data.resolution_u = 2; o.data.extrude = 0.0; o.data.bevel_depth = 0.0
        o.select_set(True); bpy.context.view_layer.objects.active = o
bpy.ops.object.convert(target="MESH")

def apply_tf(o):
    o.data = o.data.copy() if o.data.users > 1 else o.data
    o.data.transform(o.matrix_world); o.matrix_world.identity()

def set_uvs(o, fn):
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = fn(f, l.vert.co)
    bm.to_mesh(me); bm.free()

# building window UVs (world metres)
blds = [o for o in D.objects if o.name.startswith("Building_")]
for o in blds:
    apply_tf(o)
    du, dv = random.randint(0, 7) / 8, random.randint(0, 7) / 8
    def fn(f, co, du=du, dv=dv):
        n = f.normal
        if abs(n.z) > 0.5:
            return (0.001, 0.001)          # roof -> dark frame pixel
        u = co.y if abs(n.x) > abs(n.y) else co.x
        return (u / 12.8 + du, co.z / 26.4 + dv)
    set_uvs(o, fn)

# billboard UVs 0..1 on the big faces
for o in [o for o in D.objects if o.name.startswith("Billboard_")]:
    apply_tf(o)
    vs = [v.co for v in o.data.vertices]
    mn = Vector([min(v[i] for v in vs) for i in range(3)]); mx = Vector([max(v[i] for v in vs) for i in range(3)])
    sz = mx - mn
    ax = 1 if sz.y > sz.x else 0
    set_uvs(o, lambda f, co, ax=ax: ((co[ax] - mn[ax]) / max(sz[ax], 1e-3), (co.z - mn.z) / max(sz.z, 1e-3)))

def join(objs, name):
    objs = [o for o in objs if o.type == "MESH"]
    if not objs: return
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]

join(blds, "Buildings")
# group neon tubes/panels/signs by material
bymat = {}
for o in list(D.objects):
    if o.type == "MESH" and o.name.startswith(("NeonTubes_", "NeonPanels_", "Sign_")) and o.parent is None:
        bymat.setdefault(o.data.materials[0].name, []).append(o)
for m, objs in bymat.items():
    for o in objs: apply_tf(o)
    join(objs, "N_" + m)
bb = {}
for o in [o for o in D.objects if o.name.startswith("Billboard_")]:
    bb.setdefault(o.data.materials[0].name, []).append(o)
for m, objs in bb.items():
    join(objs, "BB_" + m)

# remove orphan data so it isn't exported
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_apply=True, export_lights=False,
                          export_cameras=False, export_texcoords=True, export_normals=True)
print("EXPORTED", out, [o.name for o in D.objects if o.parent is None])
