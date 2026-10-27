# Writes world-space AABBs of Building_* objects (three.js Y-up coords) -> public/colliders.json
import bpy, json, sys
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]
boxes = []
dg = bpy.context.evaluated_depsgraph_get()
for o in bpy.data.objects:
    if not o.name.startswith("Building_") or o.type != "MESH": continue
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    # blender (x,y,z) -> three (x, z, -y)
    boxes.append([round(min(xs),2), round(min(zs),2), round(-max(ys),2), round(max(xs),2), round(max(zs),2), round(-min(ys),2)])
json.dump(boxes, open(out, "w"))
print("BOXES", len(boxes))
